"""igraph one-to-many Dijkstra routing over the persistent graph mirror.

Routes are kept in a RouteSet: flat numpy arrays instead of one object per
route. With 76,400 OD pairs, building pydantic Route objects on every request
costs more than the routing itself, and we only ever need aggregates (edge
counts, per-route totals). Route objects are built on demand, for the routes
the caller really returns.

A route is stored as the list of igraph edge ids it uses (igraph "epath"), so
parallel edges stay distinct and metrics are exact.
"""

import logging
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from app.models.route import NodePair, Route

logger = logging.getLogger(__name__)


def group_pairs_by_origin(pairs: List[NodePair]) -> dict:
    """Group OD pairs by origin, so one Dijkstra call serves many destinations."""
    origin_groups = defaultdict(list)
    for pair in pairs:
        origin_groups[pair.origin].append((pair.destination, pair))
    return origin_groups


@dataclass
class RouteSet:
    """A set of routes stored as flat arrays.

    edges/offsets is the usual "ragged array" layout: the edge ids of route i
    are ``edges[offsets[i]:offsets[i + 1]]``. A route that was not found has an
    empty slice and ``found[i] is False``.
    """

    origins: np.ndarray  # (R,) NetworkX node ids
    destinations: np.ndarray  # (R,)
    edges: np.ndarray  # (total,) igraph edge ids
    offsets: np.ndarray  # (R + 1,)
    found: np.ndarray  # (R,) bool
    travel_time: Optional[np.ndarray] = None
    distance: Optional[np.ndarray] = None
    elevation_gain: Optional[np.ndarray] = None
    co2: Optional[np.ndarray] = None
    _route_of_position: Optional[np.ndarray] = None

    def __len__(self) -> int:
        return len(self.origins)

    @property
    def n_found(self) -> int:
        return int(self.found.sum())

    @property
    def lengths(self) -> np.ndarray:
        """Number of edges of each route."""
        return np.diff(self.offsets)

    def edge_counts(self, n_edges: int) -> np.ndarray:
        """How many routes use each igraph edge."""
        return np.bincount(self.edges, minlength=n_edges).astype(np.float64)

    def route_of_position(self) -> np.ndarray:
        """For each entry of `edges`, the route it belongs to (cached)."""
        if self._route_of_position is None:
            self._route_of_position = np.repeat(np.arange(len(self)), self.lengths)
        return self._route_of_position

    def routes_using(self, edge_ids: np.ndarray) -> np.ndarray:
        """Indices of the routes that use at least one of these igraph edges."""
        if len(edge_ids) == 0 or len(self.edges) == 0:
            return np.empty(0, dtype=np.int64)
        hit = np.isin(self.edges, edge_ids)
        if not hit.any():
            return np.empty(0, dtype=np.int64)
        return np.unique(self.route_of_position()[hit])

    def sum_over(self, per_edge: np.ndarray) -> np.ndarray:
        """Sum a per-edge value along each route."""
        out = np.zeros(len(self), dtype=np.float64)
        lengths = self.lengths
        nonempty = lengths > 0
        if nonempty.any():
            values = per_edge[self.edges]
            out[nonempty] = np.add.reduceat(values, self.offsets[:-1][nonempty])
        return out

    def compute_metrics(self, mirror, travel_time: np.ndarray, co2_g: np.ndarray) -> None:
        """Fill the per-route totals from per-edge arrays."""
        self.travel_time = self.sum_over(travel_time)
        self.distance = self.sum_over(mirror.length)
        self.elevation_gain = self.sum_over(mirror.elev_gain)
        self.co2 = self.sum_over(co2_g)

    def counts_for(self, indices: np.ndarray, n_edges: int) -> np.ndarray:
        """Edge counts over a subset of the routes."""
        if len(indices) == 0:
            return np.zeros(n_edges, dtype=np.float64)
        starts = self.offsets[indices]
        stops = self.offsets[indices + 1]
        picked = np.concatenate(
            [self.edges[a:b] for a, b in zip(starts, stops)]
            or [np.empty(0, dtype=self.edges.dtype)]
        )
        return np.bincount(picked, minlength=n_edges).astype(np.float64)

    def prefix(self, n: int) -> "RouteSet":
        """The first n routes, sharing the parent arrays (no copy).

        Pairs are nested by construction: the set of n pairs is the first n of
        the full sample, so this is the route set of that smaller run.
        """
        n = min(n, len(self))
        end = int(self.offsets[n])
        cut = lambda a: a[:n] if a is not None else None  # noqa: E731
        return RouteSet(
            origins=self.origins[:n],
            destinations=self.destinations[:n],
            edges=self.edges[:end],
            offsets=self.offsets[: n + 1],
            found=self.found[:n],
            travel_time=cut(self.travel_time),
            distance=cut(self.distance),
            elevation_gain=cut(self.elevation_gain),
            co2=cut(self.co2),
        )

    def node_path(self, mirror, i: int) -> List[int]:
        """Rebuild the NetworkX node path of one route."""
        path_edges = self.edges[self.offsets[i] : self.offsets[i + 1]]
        if len(path_edges) == 0:
            return []
        nodes = [int(mirror.edge_u[path_edges[0]])]
        nodes.extend(int(v) for v in mirror.edge_v[path_edges])
        return nodes

    def to_routes(self, mirror, indices: Optional[np.ndarray] = None) -> List[Route]:
        """Build pydantic Route objects (only for endpoints that return paths)."""
        if indices is None:
            indices = np.arange(len(self))
        routes = []
        for i in indices:
            i = int(i)
            if not self.found[i]:
                continue
            routes.append(
                Route(
                    origin=int(self.origins[i]),
                    destination=int(self.destinations[i]),
                    path=self.node_path(mirror, i),
                    travel_time=float(self.travel_time[i])
                    if self.travel_time is not None
                    else None,
                    distance=float(self.distance[i]) if self.distance is not None else None,
                    elevation_gain=(
                        float(self.elevation_gain[i])
                        if self.elevation_gain is not None and self.elevation_gain[i] > 0
                        else None
                    ),
                    co2_emissions=float(self.co2[i]) if self.co2 is not None else None,
                )
            )
        return routes


def route_pairs(mirror, pairs: List[NodePair], weights: np.ndarray) -> RouteSet:
    """Shortest path for every OD pair, one Dijkstra per origin.

    `weights` is a per-edge array; an edge with weight +inf is never used, which
    is how a removed edge is modelled.
    """
    t0 = time.perf_counter()
    origin_groups = group_pairs_by_origin(pairs)

    origins: List[int] = []
    destinations: List[int] = []
    found: List[bool] = []
    # One flat python list, turned into an array once at the end. Building a
    # small ndarray per route costs more than the routing itself at 76k pairs.
    flat: List[int] = []
    offsets: List[int] = [0]
    total = 0
    missing = 0

    for origin_nx, dest_pairs in origin_groups.items():
        origin_ig = mirror.vertex_of(origin_nx)
        dest_ig = []
        kept = []
        for dest_nx, _pair in dest_pairs:
            v = mirror.vertex_of(dest_nx)
            if origin_ig is not None and v is not None:
                dest_ig.append(v)
                kept.append(dest_nx)
            else:
                missing += 1
                origins.append(origin_nx)
                destinations.append(dest_nx)
                found.append(False)
                offsets.append(total)

        if not dest_ig:
            continue

        with warnings.catch_warnings():
            # igraph warns once per call when a destination is unreachable.
            # That is normal here (removed edges, disconnected corners).
            warnings.simplefilter("ignore", RuntimeWarning)
            paths = mirror.h.get_shortest_paths(
                v=origin_ig, to=dest_ig, weights=weights, output="epath"
            )
        for path, dest_nx in zip(paths, kept):
            origins.append(origin_nx)
            destinations.append(dest_nx)
            if path:
                flat.extend(path)
                total += len(path)
                found.append(True)
            else:
                found.append(False)
            offsets.append(total)

    rs = RouteSet(
        origins=np.asarray(origins, dtype=np.int64),
        destinations=np.asarray(destinations, dtype=np.int64),
        edges=np.asarray(flat, dtype=np.int64),
        offsets=np.asarray(offsets, dtype=np.int64),
        found=np.asarray(found, dtype=bool),
    )
    if missing:
        logger.warning("[ROUTING] %d pairs had a node outside the graph", missing)
    logger.debug(
        "[ROUTING] %d pairs, %d origins, %d found, %.0f ms",
        len(pairs),
        len(origin_groups),
        rs.n_found,
        (time.perf_counter() - t0) * 1000,
    )
    return rs


def routed_pairs_subset(pairs: List[NodePair], indices: np.ndarray) -> List[NodePair]:
    """Pick the OD pairs at these indices, keeping their order."""
    return [pairs[int(i)] for i in indices]


def build_route_edge_index(routes: List[Route]) -> Dict[tuple, list]:
    """Inverted index edge -> route indices. Kept for callers outside the hot path."""
    edge_index: Dict[tuple, list] = {}
    for i, route in enumerate(routes):
        for j in range(len(route.path) - 1):
            key = (route.path[j], route.path[j + 1])
            edge_index.setdefault(key, []).append(i)
    return edge_index
