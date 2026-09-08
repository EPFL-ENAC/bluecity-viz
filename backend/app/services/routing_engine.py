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
from typing import Dict, List, Optional, Sequence, Union

import numpy as np

from app.models.route import NodePair, Route

logger = logging.getLogger(__name__)


@dataclass
class PairArrays:
    """OD pairs as two flat arrays of NetworkX node ids.

    76,400 pydantic NodePair objects cost about 40 MB and every area would
    keep its own set. The same pairs as two int64 arrays cost 1.2 MB. Route
    objects are still built at the API boundary, for the few pairs a response
    really returns.
    """

    origins: np.ndarray  # (R,) int64
    destinations: np.ndarray  # (R,) int64

    def __len__(self) -> int:
        return len(self.origins)

    def __iter__(self):
        """Yield NodePair objects, for the code that still wants them."""
        for o, d in zip(self.origins, self.destinations):
            yield NodePair(origin=int(o), destination=int(d))

    @property
    def n_origins(self) -> int:
        return int(len(np.unique(self.origins))) if len(self.origins) else 0

    def prefix(self, n: int) -> "PairArrays":
        """The first n pairs, sharing the parent arrays (no copy)."""
        n = min(n, len(self))
        return PairArrays(origins=self.origins[:n], destinations=self.destinations[:n])

    def subset(self, indices: np.ndarray) -> "PairArrays":
        """The pairs at these indices, keeping their order."""
        idx = np.asarray(indices, dtype=np.int64)
        return PairArrays(origins=self.origins[idx], destinations=self.destinations[idx])

    def cache_key(self) -> bytes:
        """A short, stable key for memoisation (the arrays can be huge)."""
        import hashlib

        h = hashlib.blake2b(digest_size=16)
        h.update(np.ascontiguousarray(self.origins).tobytes())
        h.update(np.ascontiguousarray(self.destinations).tobytes())
        return h.digest()

    @classmethod
    def from_nodepairs(cls, pairs: Sequence[NodePair]) -> "PairArrays":
        return cls(
            origins=np.fromiter((p.origin for p in pairs), dtype=np.int64, count=len(pairs)),
            destinations=np.fromiter(
                (p.destination for p in pairs), dtype=np.int64, count=len(pairs)
            ),
        )

    def to_nodepairs(self) -> List[NodePair]:
        return list(self)

    @classmethod
    def coerce(cls, pairs: Union["PairArrays", Sequence[NodePair]]) -> "PairArrays":
        """Accept either form, so the API layer can still pass NodePair lists."""
        if isinstance(pairs, PairArrays):
            return pairs
        return cls.from_nodepairs(list(pairs))


@dataclass
class RouteSet:
    """A set of routes stored as flat arrays.

    edges/offsets is the usual "ragged array" layout: the edge ids of route i
    are ``edges[offsets[i]:offsets[i + 1]]``. A route that was not found has an
    empty slice and ``found[i] is False``.
    """

    origins: np.ndarray  # (R,) NetworkX node ids
    destinations: np.ndarray  # (R,)
    edges: np.ndarray  # (total,) igraph edge ids, int32
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


def route_pairs(mirror, pairs, weights: np.ndarray) -> RouteSet:
    """Shortest path for every OD pair, one Dijkstra per origin.

    `pairs` is a PairArrays or a list of NodePair. `weights` is a per-edge
    array; an edge with weight +inf is never used, which is how a removed edge
    is modelled.

    Route i always describes pair i. Internally the pairs are grouped by
    origin so one igraph call serves many destinations, then the results are
    put back in the caller's order. Callers rely on that: the impact
    statistics compare route j of the new set with route `affected_idx[j]` of
    the old one.
    """
    t0 = time.perf_counter()
    pa = PairArrays.coerce(pairs)
    n = len(pa)

    # Vertex id per pair, -1 when the node is not in this graph.
    o_ig = np.fromiter(
        (mirror.node_index.get(int(x), -1) for x in pa.origins), dtype=np.int64, count=n
    )
    d_ig = np.fromiter(
        (mirror.node_index.get(int(x), -1) for x in pa.destinations), dtype=np.int64, count=n
    )

    # Group by origin, first-seen order, keeping the input order inside a group.
    groups: Dict[int, List[int]] = defaultdict(list)
    dropped: List[int] = []
    for i in range(n):
        if o_ig[i] >= 0 and d_ig[i] >= 0:
            groups[int(o_ig[i])].append(i)
        else:
            dropped.append(i)
    missing = len(dropped)

    # Results are produced in this order, then permuted back to pair order.
    seq_index: List[int] = []
    seq_lengths: List[int] = []
    seq_found: List[bool] = []
    flat: List[int] = []

    for origin_ig, members in groups.items():
        targets = [int(d_ig[i]) for i in members]
        with warnings.catch_warnings():
            # igraph warns once per call when a destination is unreachable.
            # That is normal here (removed edges, disconnected corners).
            warnings.simplefilter("ignore", RuntimeWarning)
            paths = mirror.h.get_shortest_paths(
                v=origin_ig, to=targets, weights=weights, output="epath"
            )
        for i, path in zip(members, paths):
            seq_index.append(i)
            if path:
                flat.extend(path)
                seq_lengths.append(len(path))
                seq_found.append(True)
            else:
                seq_lengths.append(0)
                seq_found.append(False)

    for i in dropped:
        seq_index.append(i)
        seq_lengths.append(0)
        seq_found.append(False)

    rs = _reorder(pa, np.asarray(seq_index, dtype=np.int64), seq_lengths, seq_found, flat)

    if missing:
        logger.warning("[ROUTING] %d pairs had a node outside the graph", missing)
    logger.debug(
        "[ROUTING] %d pairs, %d origins, %d found, %.0f ms",
        n,
        len(groups),
        rs.n_found,
        (time.perf_counter() - t0) * 1000,
    )
    return rs


def _reorder(
    pa: PairArrays,
    seq_index: np.ndarray,
    seq_lengths: List[int],
    seq_found: List[bool],
    flat: List[int],
) -> RouteSet:
    """Turn the grouped results into a RouteSet in pair order."""
    n = len(pa)
    lengths_seq = np.asarray(seq_lengths, dtype=np.int64)
    edges_seq = np.asarray(flat, dtype=np.int32)

    lengths = np.zeros(n, dtype=np.int64)
    lengths[seq_index] = lengths_seq
    found = np.zeros(n, dtype=bool)
    found[seq_index] = np.asarray(seq_found, dtype=bool)

    offsets = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])

    # Where each pair's block sits in the grouped array.
    seq_offsets = np.zeros(len(lengths_seq) + 1, dtype=np.int64)
    np.cumsum(lengths_seq, out=seq_offsets[1:])
    start_in_seq = np.zeros(n, dtype=np.int64)
    start_in_seq[seq_index] = seq_offsets[:-1]

    total = int(offsets[-1])
    if total:
        # For every slot of the output, the slot to read in the grouped array:
        # block start + offset inside the block.
        block_start = np.repeat(start_in_seq, lengths)
        inside = np.arange(total, dtype=np.int64) - np.repeat(offsets[:-1], lengths)
        edges = edges_seq[block_start + inside]
    else:
        edges = np.empty(0, dtype=np.int32)

    return RouteSet(
        origins=pa.origins,
        destinations=pa.destinations,
        edges=edges,
        offsets=offsets,
        found=found,
    )


def routed_pairs_subset(pairs, indices: np.ndarray) -> PairArrays:
    """Pick the OD pairs at these indices, keeping their order."""
    return PairArrays.coerce(pairs).subset(indices)


def build_route_edge_index(routes: List[Route]) -> Dict[tuple, list]:
    """Inverted index edge -> route indices. Kept for callers outside the hot path."""
    edge_index: Dict[tuple, list] = {}
    for i, route in enumerate(routes):
        for j in range(len(route.path) - 1):
            key = (route.path[j], route.path[j + 1])
            edge_index.setdefault(key, []).append(i)
    return edge_index
