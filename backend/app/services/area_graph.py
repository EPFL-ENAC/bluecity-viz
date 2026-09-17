"""One routing graph and everything computed on it.

An AreaGraph is the unit the app caches and evicts: the igraph mirror, the OD
pairs, the baseline, the memoised route sets and the serialised payloads of
one area. Lausanne is one of them, built from the GraphML file and pinned, so
the default experience is an area like any other.

Nothing here touches NetworkX. The mirror comes either from a NetworkX graph
(Lausanne) or from plain arrays (an area cut out of the Swiss graph store),
and everything after that is numpy and igraph.

A request never mutates an area: it builds its own weight arrays from the base
ones, so two requests on the same area cannot corrupt each other.
"""

import logging
import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import numpy as np

from app.config import settings
from app.models.route import (
    NodePair,
    Route,
)
from app.services.betweenness import edge_betweenness
from app.services.co2_calculator import CO2Calculator
from app.services.graph_mirror import GraphMirror
from app.services.payload_cache import PayloadCache
from app.services.routing_engine import PairArrays, RouteSet, route_pairs
from app.services.usage_rows import build_edge_usage_rows

logger = logging.getLogger(__name__)

# The area every request falls back to, and the only one built from GraphML.
DEFAULT_AREA_ID = "lausanne"

# Route sets are a few hundred MB each at 76,400 pairs, so keep very few.
ROUTE_CACHE_SIZE = 3
# Betweenness costs about 450 ms and is the same for the same modifications.
# It does not depend on the OD pairs, so its key does not carry N.
BC_CACHE_SIZE = 16
# One entry per OD pair count a client asks for.
BASELINE_CACHE_SIZE = 8

# An area the user drew is smaller and there are many of them, so it keeps
# less. Lausanne is pinned and answers most requests, so it keeps the old
# sizes.
DYNAMIC_ROUTE_CACHE_SIZE = 1
DYNAMIC_BASELINE_CACHE_SIZE = 2
DYNAMIC_BC_CACHE_SIZE = 8

# Rough cost of one usage row (a small dict of 9 numbers) in CPython.
USAGE_ROW_BYTES = 300

# How the OD sampler weighs the nodes. "uniform" is every junction alike,
# "population" follows the residents and jobs of the graph store.
NodeWeighting = Literal["uniform", "population"]
NODE_WEIGHTINGS = ("uniform", "population")
# The SamplingConfig.node_weight_col each weighting runs with.
NODE_WEIGHT_COL = {"uniform": "dummy", "population": "population"}


class NoPopulationData(ValueError):
    """The area has no residents and no jobs, so there is nothing to weigh by."""

    code = "no_population_data"


@dataclass
class AreaMeta:
    """What the API says about an area. The geometry stays empty for the
    default area, which is a whole GraphML file, not a shape."""

    id: str
    name: str = ""
    circle: Optional[dict] = None
    bbox: Optional[list] = None
    scc_fraction: float = 1.0
    build_ms: float = 0.0


@dataclass
class Baseline:
    """The unmodified network: computed once per area, never rebuilt."""

    pairs: PairArrays
    routes: RouteSet
    counts: np.ndarray  # per igraph edge
    counts_group: np.ndarray  # per (u, v) group
    bc: np.ndarray  # per igraph edge, veh/day
    bc_group: np.ndarray
    co2_per_km_group: np.ndarray  # per (u, v) group, g/km of the traffic on it
    usage_rows: list = field(default_factory=list)


@dataclass
class OdSet:
    """One OD sample of an area and the baselines routed on it.

    An area has one per node weighting. They share the graph, the betweenness
    and the CO2 per km (none of those depend on the pairs), and differ in the
    pairs, the candidate pool and the edge counts.
    """

    pairs: Optional[PairArrays] = None
    nodes: object = None  # pd.Series {node id: weight}, pool for resampling
    baseline: Optional[Baseline] = None
    by_n: "OrderedDict[int, Baseline]" = field(default_factory=OrderedDict)


def _nbytes(*arrays) -> int:
    return sum(a.nbytes for a in arrays if a is not None)


class AreaGraph:
    """One routing graph, its OD pairs, its baseline and its caches."""

    def __init__(self, meta: AreaMeta, mirror: GraphMirror, dynamic: bool = False):
        self.meta = meta
        self.mirror = mirror
        self.dynamic = dynamic

        # Grams of CO2 for one vehicle over each edge. The routes sum it, and
        # times the edge counts it is the CO2 of the traffic on each edge.
        self.base_co2_g = CO2Calculator.edge_co2_array(
            mirror.length, mirror.speed_kph, mirror.elev_gain
        )
        # 1 / km per edge, 0 for an edge with no length
        self._inv_km = np.divide(
            1000.0, mirror.length, out=np.zeros(len(mirror.length)), where=mirror.length > 0
        )

        # One OD sample per node weighting. The uniform one is built with the
        # area, the population one on the first request that asks for it.
        self.od: Dict[str, OdSet] = {"uniform": OdSet()}
        self._od_lock = threading.Lock()
        self._seed = 42
        self.sampling_config = None
        # The junctions betweenness is computed over, and the baseline
        # betweenness itself, both set by the first OD draw.
        self._bc_vertices: List[int] = []
        self._sampled_bc: Optional[np.ndarray] = None

        # Bounded caches. All three are pure memoisation: dropping an entry
        # only costs time, never correctness. The route cache is keyed by the
        # content of the pairs, so two OD samples never share an entry.
        self.route_cache: "OrderedDict[bytes, RouteSet]" = OrderedDict()
        self._bc_cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self.payloads = PayloadCache(label=meta.id)

    # ── Construction ──────────────────────────────────────────────────────────

    @classmethod
    def from_networkx(cls, graph, area_id: str = DEFAULT_AREA_ID, name: str = "") -> "AreaGraph":
        """The area of a whole NetworkX graph, which is how Lausanne is loaded."""
        return cls(AreaMeta(id=area_id, name=name or area_id), GraphMirror(graph))

    # The uniform sample under its old names: the startup code, the areas API
    # and the tests read and write these.

    @property
    def pairs(self) -> Optional[PairArrays]:
        return self.od["uniform"].pairs

    @pairs.setter
    def pairs(self, value: Optional[PairArrays]) -> None:
        self.od["uniform"].pairs = value

    @property
    def od_nodes(self):
        return self.od["uniform"].nodes

    @od_nodes.setter
    def od_nodes(self, value) -> None:
        self.od["uniform"].nodes = value

    @property
    def baseline(self) -> Optional[Baseline]:
        return self.od["uniform"].baseline

    @baseline.setter
    def baseline(self, value: Optional[Baseline]) -> None:
        self.od["uniform"].baseline = value

    @property
    def route_cache_size(self) -> int:
        return DYNAMIC_ROUTE_CACHE_SIZE if self.dynamic else ROUTE_CACHE_SIZE

    @property
    def baseline_cache_size(self) -> int:
        return DYNAMIC_BASELINE_CACHE_SIZE if self.dynamic else BASELINE_CACHE_SIZE

    @property
    def bc_cache_size(self) -> int:
        return DYNAMIC_BC_CACHE_SIZE if self.dynamic else BC_CACHE_SIZE

    # ── OD pairs and startup ──────────────────────────────────────────────────

    def sample_research_pairs(
        self, n_pairs: int, config, seed: int, node_weighting: NodeWeighting = "uniform"
    ) -> None:
        """Draw the OD pairs of this area with the research-based sampler."""
        from app.services.sampling.od_sampler import generate_research_based_pairs_mirror

        if node_weighting not in NODE_WEIGHTINGS:
            raise ValueError(f"node_weighting must be one of {NODE_WEIGHTINGS}")
        if node_weighting == "population" and not self.mirror.has_population:
            raise NoPopulationData(f"area {self.meta.id} has no residents and no jobs")

        if node_weighting == "uniform":
            self.sampling_config = config
            self._seed = seed
        run_config = config.model_copy(update={"node_weight_col": NODE_WEIGHT_COL[node_weighting]})
        od = self.od.setdefault(node_weighting, OdSet())
        # The pool is the same for every weighting (drawn uniformly, same
        # seed), so its betweenness is computed by the first draw and reused.
        sample = generate_research_based_pairs_mirror(
            self.mirror,
            n_pairs=n_pairs,
            config=run_config,
            seed=seed,
            betweenness=self._sampled_bc,
        )
        od.pairs, od.nodes = sample.pairs, sample.nodes
        if self._sampled_bc is None:
            # Betweenness runs on the same junctions the demand does, so the
            # map and the sampler talk about the same network.
            self._sampled_bc = sample.betweenness
            self._bc_vertices = [self.mirror.node_index[int(n)] for n in od.nodes.index]

    def od_set(self, node_weighting: NodeWeighting = "uniform") -> OdSet:
        """The OD sample of this weighting, drawn and routed on first use.

        The population sample costs one sampling run and one routing of the
        pairs, a few seconds on a large area. Its betweenness is the uniform
        baseline's: it depends on the graph, not on the pairs.
        """
        if node_weighting not in NODE_WEIGHTINGS:
            raise ValueError(f"node_weighting must be one of {NODE_WEIGHTINGS}")
        od = self.od.get(node_weighting)
        if od is not None and od.baseline is not None:
            return od
        if node_weighting == "uniform":
            raise RuntimeError("Baseline not computed")
        if self.mirror is None or not self.mirror.has_population:
            raise NoPopulationData(f"area {self.meta.id} has no residents and no jobs")

        with self._od_lock:
            od = self.od.get(node_weighting)
            if od is not None and od.baseline is not None:
                return od
            uniform = self.od["uniform"]
            if uniform.baseline is None or self.sampling_config is None:
                raise RuntimeError("Baseline not computed")

            t0 = time.perf_counter()
            self.sample_research_pairs(
                len(uniform.pairs), self.sampling_config, self._seed, node_weighting
            )
            od = self.od[node_weighting]
            ref = uniform.baseline
            od.baseline = self._route_baseline(
                od.pairs,
                bc=ref.bc,
                bc_group=ref.bc_group,
            )
            logger.info(
                "[AREA %s] %s OD sample ready in %.1f s",
                self.meta.id,
                node_weighting,
                time.perf_counter() - t0,
            )
            return od

    def memory_bytes(self) -> int:
        """Roughly what this area holds, for the registry budget.

        Counted: the mirror arrays, the pairs, the baseline and its route set,
        the memoised route sets and betweenness, and the serialised payloads.
        The usage rows are python dicts, so they are estimated.
        """
        mirror = self.mirror
        total = _nbytes(
            mirror.length,
            mirror.travel_time,
            mirror.lanes,
            mirror.speed_kph,
            mirror.elev_gain,
            mirror.edge_u,
            mirror.edge_v,
            mirror.edge_key,
            mirror.uv_group,
            mirror.uv_u,
            mirror.uv_v,
            mirror.node_ids,
            mirror.node_x,
            mirror.node_y,
            mirror.street_count,
            mirror.residents,
            mirror.jobs_fte,
            self.base_co2_g,
        )
        # igraph topology and the python side maps, measured at about 100 B
        # per edge and per node on Lausanne.
        total += 100 * (mirror.n_edges + mirror.n_nodes)

        def route_set_bytes(rs):
            return _nbytes(
                rs.edges,
                rs.offsets,
                rs.origins,
                rs.destinations,
                rs.found,
                rs.travel_time,
                rs.distance,
                rs.elevation_gain,
                rs.co2,
                rs._route_of_position,
            )

        for weighting, od in self.od.items():
            if od.pairs is not None:
                total += _nbytes(od.pairs.origins, od.pairs.destinations)
            if od.baseline is not None:
                b = od.baseline
                total += route_set_bytes(b.routes)
                total += _nbytes(b.counts, b.counts_group, b.co2_per_km_group)
                if weighting == "uniform":
                    # the other samples point at these same arrays
                    total += _nbytes(b.bc, b.bc_group)
                total += USAGE_ROW_BYTES * len(b.usage_rows)
            for small in od.by_n.values():
                # the route set is a view on the baseline one, only the rows are new
                total += _nbytes(small.counts, small.counts_group, small.co2_per_km_group)
                total += USAGE_ROW_BYTES * len(small.usage_rows)
        for rs in self.route_cache.values():
            total += route_set_bytes(rs)
        for bc in self._bc_cache.values():
            total += _nbytes(bc)
        total += self.payloads.nbytes()
        return int(total)

    def graph_info(self) -> dict:
        """What GET /routes/graph-info says about this area."""
        return {
            "area_id": self.meta.id,
            "bbox": self.meta.bbox,
            "scc_fraction": self.meta.scc_fraction,
            "node_count": self.mirror.n_nodes,
            "edge_count": self.mirror.n_edges,
            "sample_nodes": [int(n) for n in self.mirror.node_ids[:20]],
            "od_pairs": len(self.pairs) if self.pairs else 0,
            "od_pairs_default": settings.od_pairs,
            "od_pairs_max": settings.od_pairs_max,
            "od_origins": self.pairs.n_origins if self.pairs else 0,
            "n_destinations_per_origin": (
                self.sampling_config.n_destinations_per_origin if self.sampling_config else None
            ),
        }

    def clear_route_cache(self) -> None:
        """Drop the memoised route sets and betweenness.

        The baselines stay: they are the unmodified network, they only change
        when the graph or the OD sample changes, which means a restart.
        """
        self.route_cache.clear()
        self._bc_cache.clear()

    # ── Baseline ──────────────────────────────────────────────────────────────

    def traffic_co2_per_km(self, co2_g: np.ndarray, counts: np.ndarray) -> np.ndarray:
        """CO2 of the traffic per km, per (u, v) group.

        One vehicle over the edge times the number of routes on it, divided by
        the length. Parallel edges add up, like two lanes of one street.
        """
        return self.mirror.group_sum(co2_g * counts * self._inv_km)

    def baseline_for(self, n_pairs: int, node_weighting: NodeWeighting = "uniform") -> Baseline:
        """Baseline restricted to the first n_pairs OD pairs of one OD sample.

        The pair sets are nested, so this is a prefix of the full route set:
        no rerouting, only counting again. Cached per N, per sample.
        """
        od = self.od_set(node_weighting)
        full = od.baseline
        n = min(n_pairs, len(full.pairs))
        if n >= len(full.pairs):
            return full

        cached = od.by_n.get(n)
        if cached is not None:
            od.by_n.move_to_end(n)
            return cached

        mirror = self.mirror
        routes = full.routes.prefix(n)
        counts = routes.edge_counts(mirror.n_edges)
        counts_group = mirror.group_sum(counts)
        # the CO2 follows the traffic, so a smaller set has its own values
        co2_per_km_group = self.traffic_co2_per_km(self.base_co2_g, counts)
        small = Baseline(
            pairs=full.pairs.prefix(n),
            routes=routes,
            counts=counts,
            counts_group=counts_group,
            bc=full.bc,  # betweenness is a property of the graph, not of the OD set
            bc_group=full.bc_group,
            co2_per_km_group=co2_per_km_group,
        )
        small.usage_rows = build_edge_usage_rows(
            mirror,
            counts_group,
            routes.n_found,
            co2_per_km_group,
            betweenness=full.bc_group,
        )
        od.by_n[n] = small
        while len(od.by_n) > self.baseline_cache_size:
            od.by_n.popitem(last=False)
        logger.info(
            "[BASELINE] %s built for %d pairs, %d rows", node_weighting, n, len(small.usage_rows)
        )
        return small

    def build_baseline(self, config, seed: int) -> None:
        """Route the default pairs, compute betweenness and the CO2 per edge."""
        mirror = self.mirror
        self._seed = seed

        if self._sampled_bc is not None:
            # The OD draw already computed it, over the same junctions.
            bc = self._sampled_bc
        else:
            # No research sampling ran (the simple random pairs of the tests).
            rng = random.Random(seed)
            n = min(config.n_nodes_preprocess, mirror.n_nodes)
            self._bc_vertices = sorted(rng.sample(range(mirror.n_nodes), n))
            t0 = time.perf_counter()
            bc = edge_betweenness(
                mirror, mirror.travel_time, self._bc_vertices, config.daily_km_driven
            )
            logger.info("[AREA %s] betweenness in %.1f s", self.meta.id, time.perf_counter() - t0)

        self.baseline = self._route_baseline(
            self.pairs,
            bc=bc,
            bc_group=mirror.group_sum(bc),
        )
        # Freezing lives in main.py now: it is only right for the objects that
        # stay until the process ends, and an area can be evicted.
        logger.info(
            "[AREA %s] baseline ready, %d usage rows", self.meta.id, len(self.baseline.usage_rows)
        )

    def _route_baseline(
        self,
        pairs: PairArrays,
        *,
        bc: np.ndarray,
        bc_group: np.ndarray,
    ) -> Baseline:
        """Route `pairs` on the unmodified network.

        The betweenness is given, not computed: it depends on the graph only,
        so every OD sample of the area shares it. The CO2 per km follows the
        traffic, so each sample has its own.
        """
        mirror = self.mirror
        t0 = time.perf_counter()
        routes = route_pairs(mirror, pairs, mirror.travel_time)
        routes.compute_metrics(mirror, mirror.travel_time, self.base_co2_g)
        logger.info(
            "[AREA %s] %d routes in %.1f s", self.meta.id, routes.n_found, time.perf_counter() - t0
        )

        counts = routes.edge_counts(mirror.n_edges)
        counts_group = mirror.group_sum(counts)
        # Same grams as the routes, so times the length the edges add up to
        # the route totals.
        co2_per_km_group = self.traffic_co2_per_km(self.base_co2_g, counts)
        baseline = Baseline(
            pairs=pairs,
            routes=routes,
            counts=counts,
            counts_group=counts_group,
            bc=bc,
            bc_group=bc_group,
            co2_per_km_group=co2_per_km_group,
        )
        baseline.usage_rows = build_edge_usage_rows(
            mirror,
            counts_group,
            routes.n_found,
            co2_per_km_group,
            betweenness=bc_group,
        )
        return baseline

    # ── OD pairs ──────────────────────────────────────────────────────────────

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Random OD pairs within a radius of the middle of the area.

        Same draws as before: the mirror keeps the nodes in NetworkX order, so
        `random.sample` picks the same ones for the same seed.
        """
        if seed is not None:
            random.seed(seed)

        mirror = self.mirror
        center_lat = float(mirror.node_y.mean())
        center_lon = float(mirror.node_x.mean())
        lat_km = (mirror.node_y - center_lat) * 111.0
        lon_km = (mirror.node_x - center_lon) * 111.0 * 0.7
        inside = np.sqrt(lat_km**2 + lon_km**2) <= radius_km

        nodes_in_radius = [int(n) for n in mirror.node_ids[inside]]
        if len(nodes_in_radius) < 2:
            nodes_in_radius = [int(n) for n in mirror.node_ids]

        min_dist, pairs, attempts = 0.3, [], 0
        while len(pairs) < count and attempts < count * 10:
            attempts += 1
            o, d = random.sample(nodes_in_radius, 2)
            oi, di = mirror.node_index[o], mirror.node_index[d]
            lat_km = (mirror.node_y[oi] - mirror.node_y[di]) * 111.0
            lon_km = (mirror.node_x[oi] - mirror.node_x[di]) * 111.0 * 0.7
            if (lat_km**2 + lon_km**2) ** 0.5 >= min_dist:
                pairs.append(NodePair(origin=o, destination=d))
        return pairs

    # ── Routing ───────────────────────────────────────────────────────────────

    def _weights_for(self, weight: str) -> np.ndarray:
        """The per-edge cost a /calculate request wants to minimise."""
        if weight == "length":
            return self.mirror.length
        if weight != "travel_time":
            logger.warning("Unknown weight %r, using travel_time", weight)
        return self.mirror.travel_time

    def calculate_routes(self, pairs: List[NodePair], weight: str = "travel_time") -> List[Route]:
        """Shortest paths for the given OD pairs, as Route objects."""
        if not self.mirror or not pairs:
            return []
        rs = route_pairs(self.mirror, pairs, self._weights_for(weight))
        rs.compute_metrics(self.mirror, self.mirror.travel_time, self.base_co2_g)
        return rs.to_routes(self.mirror)

    def route_set_for(self, pairs) -> RouteSet:
        """RouteSet of the unmodified network for these pairs, memoised."""
        pairs = PairArrays.coerce(pairs)
        # A hash of the arrays: the pair list itself can be 76k entries long.
        key = pairs.cache_key()
        cached = self.route_cache.get(key)
        if cached is not None:
            self.route_cache.move_to_end(key)
            return cached
        rs = route_pairs(self.mirror, pairs, self.mirror.travel_time)
        rs.compute_metrics(self.mirror, self.mirror.travel_time, self.base_co2_g)
        self.route_cache[key] = rs
        while len(self.route_cache) > self.route_cache_size:
            self.route_cache.popitem(last=False)
        return rs

    @property
    def seed(self) -> int:
        """The seed this area was sampled with, reused by elastic demand."""
        return self._seed

    def betweenness_for(self, scenario) -> np.ndarray:
        """Betweenness of a modified network, memoised by scenario.

        It does not depend on the OD sample, only on the graph and the
        scenario, so its key carries neither the pair count nor the weighting.
        """
        return self._betweenness(scenario.travel_time, scenario.key)

    def _betweenness(self, travel_time: np.ndarray, key: tuple) -> np.ndarray:
        cached = self._bc_cache.get(key)
        if cached is not None:
            self._bc_cache.move_to_end(key)
            return cached
        bc = edge_betweenness(
            self.mirror,
            travel_time,
            self._bc_vertices,
            self.sampling_config.daily_km_driven,
            label="delta-BC",
        )
        self._bc_cache[key] = bc
        while len(self._bc_cache) > self.bc_cache_size:
            self._bc_cache.popitem(last=False)
        return bc

    # ── Recalculation ─────────────────────────────────────────────────────────

    def recalculate_with_modifications(self, **kwargs) -> dict:
        """Run one scenario on this area. See services/recalculate.py."""
        from app.services.recalculate import recalculate

        return recalculate(self, **kwargs)

    # ── Payloads ──────────────────────────────────────────────────────────────

    def baseline_payload(
        self, od_pairs: Optional[int] = None, node_weighting: NodeWeighting = "uniform"
    ) -> dict:
        """The unmodified edge usage for N pairs, as served by GET /routes/baseline."""
        od = self.od_set(node_weighting)
        n = min(od_pairs or settings.od_pairs, len(od.baseline.pairs))
        base = self.baseline_for(n, node_weighting)
        return {
            "total_routes": base.routes.n_found,
            "od_pairs": len(base.pairs),
            "edge_usage": base.usage_rows,
        }
