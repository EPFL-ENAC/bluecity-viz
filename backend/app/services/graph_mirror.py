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
"""

import logging
from typing import Dict, List, Optional, Tuple

import igraph as ig
import numpy as np

logger = logging.getLogger(__name__)

# Speed used when an edge has no usable speed_kph.
# Two different values on purpose: they reproduce what the old code did.
CO2_FALLBACK_SPEED_KPH = 40.0  # CO2Calculator.DEFAULT_SPEED_KPH
BPR_FALLBACK_SPEED_KPH = 30.0  # bpr.write_bc_duration / apply_congestion_weights


def parse_lanes(value, default: int = 2) -> int:
    """Read a lane count from an OSM attribute, which can be a list or a string."""
    if isinstance(value, list):
        value = value[0] if value else default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class GraphMirror:
    """Immutable igraph + numpy view of a NetworkX MultiDiGraph.

    Attributes (all arrays are indexed by igraph edge id, length ``n_edges``):
        h            igraph.Graph, topology only, no edge attributes
        node_ids     (n_nodes,) NetworkX node id per igraph vertex
        node_index   {NetworkX node id: igraph vertex id}
        edge_u/v/key (n_edges,) the NetworkX (u, v, key) of each igraph edge
        length       metres
        travel_time  free-flow seconds
        speed_free   km/h used by the BPR formula
        speed_co2    km/h used by the CO2 model
        lanes        int
        elev_gain    metres of climb
        co2_g        free-flow CO2 for the whole edge, grams
        uv_group     (n_edges,) index into the (u, v) groups
        uv_u, uv_v   (n_groups,) the (u, v) of each group
    """

    def __init__(self, graph):
        nodes = list(graph.nodes())
        self.node_ids = np.asarray(nodes, dtype=np.int64)
        self.node_index: Dict[int, int] = {n: i for i, n in enumerate(nodes)}
        self.n_nodes = len(nodes)

        edges = list(graph.edges(keys=True, data=True))
        self.n_edges = len(edges)

        ig_edges = [(self.node_index[u], self.node_index[v]) for u, v, _k, _d in edges]
        self.h = ig.Graph(n=self.n_nodes, edges=ig_edges, directed=True)

        self.edge_u = np.asarray([u for u, _v, _k, _d in edges], dtype=np.int64)
        self.edge_v = np.asarray([v for _u, v, _k, _d in edges], dtype=np.int64)
        self.edge_key = np.asarray([k for _u, _v, k, _d in edges], dtype=np.int64)

        self.length = np.asarray(
            [float(d.get("length") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
        )
        self.travel_time = np.asarray(
            [float(d.get("travel_time") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
        )
        self.lanes = np.asarray(
            [parse_lanes(d.get("lanes", 2)) for _u, _v, _k, d in edges], dtype=np.float64
        )

        speed_raw = np.asarray(
            [float(d.get("speed_kph") or 0.0) for _u, _v, _k, d in edges], dtype=np.float64
        )
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

        self.elev_gain = np.asarray(
            [self._elevation_gain(graph, u, v, d) for u, v, _k, d in edges], dtype=np.float64
        )

        self.uv_group, self.uv_u, self.uv_v = self._build_uv_groups()
        self.n_groups = len(self.uv_u)

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
