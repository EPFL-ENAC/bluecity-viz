"""Persistent igraph mirror of the road network.

The mirror is built once, when the graph is loaded, and never changes after
that. It holds three things:

  * the topology in igraph (fast Dijkstra and betweenness)
  * one numpy array per edge attribute we need in the hot path
  * the index maps between NetworkX ids and igraph ids

A request never touches the mirror or the NetworkX graph. It builds its own
weight arrays (travel time, CO2 per km) from the base arrays and passes them
to igraph as ``weights=``. Removing an edge is a weight of ``+inf``, which
igraph treats as "never use this edge", so there is nothing to roll back and
two requests cannot corrupt each other.

Parallel edges (same u and v, different key) keep their own igraph edge id.
Statistics are grouped back to (u, v) through ``uv_group``, because that is
the key the API and the frontend use.

Two ways to build one: ``GraphMirror(graph)`` from a NetworkX MultiDiGraph,
and ``GraphMirror.from_arrays(...)`` from plain numpy arrays. The second one
is what an area cut out of the Swiss graph store uses, so a routing graph can
exist without NetworkX at all.
"""

import logging
from typing import Dict, List, Optional, Tuple

import igraph as ig
import numpy as np

from app.services.osm_values import parse_lanes, parse_street_count

__all__ = ["GraphMirror"]

logger = logging.getLogger(__name__)

# Speed used when an edge has no usable speed_kph.
# Two different values on purpose: they reproduce what the old code did.
CO2_FALLBACK_SPEED_KPH = 40.0  # CO2Calculator.DEFAULT_SPEED_KPH
BPR_FALLBACK_SPEED_KPH = 30.0  # bpr.write_bc_duration / apply_congestion_weights


class GraphMirror:
    """Immutable igraph + numpy view of a road network.

    Attributes (all arrays are indexed by igraph edge id, length ``n_edges``):
        h            igraph.Graph, topology only, no edge attributes
        node_ids     (n_nodes,) NetworkX node id per igraph vertex
        node_index   {NetworkX node id: igraph vertex id}
        node_x/y     (n_nodes,) longitude and latitude
        street_count (n_nodes,) number of streets at the node, 0 when unknown
        edge_u/v/key (n_edges,) the NetworkX (u, v, key) of each igraph edge
        length       metres
        travel_time  free-flow seconds
        speed_raw    km/h as the data gives it, 0 when missing
        speed_free   km/h used by the BPR formula
        speed_co2    km/h used by the CO2 model
        lanes        int
        elev_gain    metres of climb
        uv_group     (n_edges,) index into the (u, v) groups
        uv_u, uv_v   (n_groups,) the (u, v) of each group
        last_of_group (n_groups,) the last igraph edge id of each (u, v) group
    """

    def __init__(self, graph):
        nodes = list(graph.nodes())
        edges = list(graph.edges(keys=True, data=True))

        node_data = [graph.nodes[n] for n in nodes]
        elev_gain = np.asarray(
            [self._elevation_gain(graph, u, v, d) for u, v, _k, d in edges], dtype=np.float64
        )

        self._init_from_arrays(
            node_ids=np.asarray(nodes, dtype=np.int64),
            node_x=np.asarray([float(d.get("x") or 0.0) for d in node_data], dtype=np.float64),
            node_y=np.asarray([float(d.get("y") or 0.0) for d in node_data], dtype=np.float64),
            street_count=np.asarray(
                [parse_street_count(d.get("street_count")) for d in node_data], dtype=np.int64
            ),
            edge_u=np.asarray([u for u, _v, _k, _d in edges], dtype=np.int64),
            edge_v=np.asarray([v for _u, v, _k, _d in edges], dtype=np.int64),
            edge_key=np.asarray([k for _u, _v, k, _d in edges], dtype=np.int64),
            length=np.asarray(
                [float(d.get("length") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
            ),
            travel_time=np.asarray(
                [float(d.get("travel_time") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
            ),
            lanes=np.asarray(
                [parse_lanes(d.get("lanes", 2)) for _u, _v, _k, d in edges], dtype=np.float64
            ),
            speed_raw=np.asarray(
                [float(d.get("speed_kph") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
            ),
            elev_gain=elev_gain,
        )

    @classmethod
    def from_arrays(
        cls,
        node_ids: np.ndarray,
        edge_u: np.ndarray,
        edge_v: np.ndarray,
        *,
        length: np.ndarray,
        travel_time: np.ndarray,
        speed_raw: np.ndarray,
        lanes: np.ndarray,
        elev_gain: np.ndarray,
        edge_key: Optional[np.ndarray] = None,
        node_x: Optional[np.ndarray] = None,
        node_y: Optional[np.ndarray] = None,
        street_count: Optional[np.ndarray] = None,
    ) -> "GraphMirror":
        """Build a mirror from columnar data, without NetworkX.

        `edge_u` / `edge_v` are node ids, not vertex indices: they are looked
        up in `node_ids` exactly like the NetworkX path does.
        """
        mirror = cls.__new__(cls)
        mirror._init_from_arrays(
            node_ids=np.asarray(node_ids, dtype=np.int64),
            node_x=node_x,
            node_y=node_y,
            street_count=street_count,
            edge_u=np.asarray(edge_u, dtype=np.int64),
            edge_v=np.asarray(edge_v, dtype=np.int64),
            edge_key=edge_key,
            length=np.asarray(length, dtype=np.float64),
            travel_time=np.asarray(travel_time, dtype=np.float64),
            lanes=np.asarray(lanes, dtype=np.float64),
            speed_raw=np.asarray(speed_raw, dtype=np.float64),
            elev_gain=np.asarray(elev_gain, dtype=np.float64),
        )
        return mirror

    def _init_from_arrays(
        self,
        *,
        node_ids: np.ndarray,
        edge_u: np.ndarray,
        edge_v: np.ndarray,
        edge_key: Optional[np.ndarray],
        length: np.ndarray,
        travel_time: np.ndarray,
        lanes: np.ndarray,
        speed_raw: np.ndarray,
        elev_gain: np.ndarray,
        node_x: Optional[np.ndarray] = None,
        node_y: Optional[np.ndarray] = None,
        street_count: Optional[np.ndarray] = None,
    ) -> None:
        self.node_ids = node_ids
        self.node_index: Dict[int, int] = {int(n): i for i, n in enumerate(node_ids)}
        self.n_nodes = len(node_ids)

        zeros_n = np.zeros(self.n_nodes, dtype=np.float64)
        self.node_x = zeros_n if node_x is None else np.asarray(node_x, dtype=np.float64)
        self.node_y = zeros_n if node_y is None else np.asarray(node_y, dtype=np.float64)
        self.street_count = (
            np.zeros(self.n_nodes, dtype=np.int64)
            if street_count is None
            else np.asarray(street_count, dtype=np.int64)
        )

        self.edge_u = edge_u
        self.edge_v = edge_v
        self.n_edges = len(edge_u)
        self.edge_key = (
            np.zeros(self.n_edges, dtype=np.int64)
            if edge_key is None
            else np.asarray(edge_key, dtype=np.int64)
        )

        ig_edges = [
            (self.node_index[int(u)], self.node_index[int(v)]) for u, v in zip(edge_u, edge_v)
        ]
        self.h = ig.Graph(n=self.n_nodes, edges=ig_edges, directed=True)

        self.length = length
        self.travel_time = travel_time
        self.lanes = lanes
        self.elev_gain = elev_gain
        self.speed_raw = speed_raw

        with np.errstate(divide="ignore", invalid="ignore"):
            derived = np.where(
                self.travel_time > 0,
                (self.length / 1000.0) / (self.travel_time / 3600.0),
                0.0,
            )
        have = speed_raw > 0
        self.speed_free = np.where(have, speed_raw, BPR_FALLBACK_SPEED_KPH)
        self.speed_co2 = np.where(
            have, speed_raw, np.where(derived > 0, derived, CO2_FALLBACK_SPEED_KPH)
        )

        self.uv_group, self.uv_u, self.uv_v = self._build_uv_groups()
        self.n_groups = len(self.uv_u)

        # Last igraph edge of each (u, v) group. The OD sampler needs it: it
        # used to key betweenness by (u, v) in a dict, so the last parallel
        # edge won and the others read back as 0.
        self.last_of_group = np.zeros(self.n_groups, dtype=np.int64)
        self.last_of_group[self.uv_group] = np.arange(self.n_edges, dtype=np.int64)

        by_uv: Dict[Tuple[int, int], list] = {}
        for i in range(self.n_edges):
            by_uv.setdefault((int(self.edge_u[i]), int(self.edge_v[i])), []).append(i)
        self._edge_ids_by_uv: Dict[Tuple[int, int], np.ndarray] = {
            key: np.asarray(ids, dtype=np.int64) for key, ids in by_uv.items()
        }

        logger.info(
            "[MIRROR] %d nodes, %d edges, %d (u, v) groups",
            self.n_nodes,
            self.n_edges,
            self.n_groups,
        )

    @staticmethod
    def _elevation_gain(graph, u, v, data) -> float:
        """Climb in metres, pre-computed on the edge or derived from node elevations."""
        gain = data.get("elevation_gain")
        if gain is not None:
            return float(gain)
        nu, nv = graph.nodes[u], graph.nodes[v]
        if "elevation" in nu and "elevation" in nv:
            diff = nv["elevation"] - nu["elevation"]
            if diff > 0:
                return float(diff)
        return 0.0

    def _build_uv_groups(self):
        """Map every igraph edge to a (u, v) group, keeping first-seen order."""
        group_of: Dict[Tuple[int, int], int] = {}
        uv_group = np.empty(self.n_edges, dtype=np.int64)
        us: List[int] = []
        vs: List[int] = []
        for i in range(self.n_edges):
            key = (int(self.edge_u[i]), int(self.edge_v[i]))
            g = group_of.get(key)
            if g is None:
                g = len(us)
                group_of[key] = g
                us.append(key[0])
                vs.append(key[1])
            uv_group[i] = g
        self.group_of_uv = group_of
        return uv_group, np.asarray(us, dtype=np.int64), np.asarray(vs, dtype=np.int64)

    # ── lookups ───────────────────────────────────────────────────────────────

    def edge_ids_for(self, u: int, v: int) -> Optional[np.ndarray]:
        """All igraph edge ids between u and v (several if the graph has parallel edges)."""
        return self._edge_ids_by_uv.get((u, v))

    def has_edge(self, u: int, v: int) -> bool:
        return (u, v) in self._edge_ids_by_uv

    def vertex_of(self, nx_node: int) -> Optional[int]:
        return self.node_index.get(nx_node)

    def group_sum(self, per_edge: np.ndarray) -> np.ndarray:
        """Sum a per-edge array into per-(u, v)-group values."""
        return np.bincount(self.uv_group, weights=per_edge, minlength=self.n_groups)

    def group_max(self, per_edge: np.ndarray) -> np.ndarray:
        """Largest value per (u, v) group (used for values that must not be summed)."""
        out = np.zeros(self.n_groups, dtype=np.float64)
        np.maximum.at(out, self.uv_group, per_edge)
        return out
