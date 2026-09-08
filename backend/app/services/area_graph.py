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
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from app.config import settings
from app.models.route import (
    EdgeModification,
    ImpactStatistics,
    NodePair,
    Route,
    TimingStats,
)
from app.services import bpr, routing_engine
from app.services.co2_calculator import CO2Calculator
from app.services.graph_helpers import build_edge_usage_rows, modifications_to_arrays
from app.services.graph_mirror import GraphMirror
from app.services.impact_calculator import compute_impact_statistics_arrays
from app.services.payload_cache import PayloadCache
from app.services.routing_engine import PairArrays, RouteSet, route_pairs
from app.services.utils.timing import timed

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


@dataclass
class AreaMeta:
    """What the API says about an area. The geometry fields stay empty for
    the default area, which is a whole GraphML file, not a shape."""

    id: str
    kind: str = "default"  # default | circle | polygon
    name: str = ""
    circle: Optional[dict] = None
    polygon: Optional[list] = None
    bbox: Optional[list] = None
    node_count: int = 0
    edge_count: int = 0
    scc_fraction: float = 1.0
    build_ms: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class Baseline:
    """The unmodified network: computed once per area, never rebuilt."""

    pairs: PairArrays
    routes: RouteSet
    counts: np.ndarray  # per igraph edge
    counts_group: np.ndarray  # per (u, v) group
    bc: np.ndarray  # per igraph edge, veh/day
    bc_group: np.ndarray
    co2_per_km: np.ndarray  # per igraph edge, congested
    co2_group: np.ndarray
    usage_rows: list = field(default_factory=list)


def _nbytes(*arrays) -> int:
    return sum(a.nbytes for a in arrays if a is not None)


class AreaGraph:
    """One routing graph, its OD pairs, its baseline and its caches."""

    def __init__(self, meta: AreaMeta, mirror: GraphMirror, dynamic: bool = False):
        self.meta = meta
        self.mirror = mirror
        self.dynamic = dynamic

        self.base_co2_g = CO2Calculator.edge_co2_array(
            mirror.length, mirror.speed_co2, mirror.elev_gain
        )
        length_km = mirror.length / 1000.0
        self.base_co2_per_km = np.where(
            length_km > 0, self.base_co2_g / np.where(length_km > 0, length_km, 1.0), 0.0
        )

        self.pairs: Optional[PairArrays] = None
        self.od_nodes = None  # pd.Series {node id: weight}, pool for resampling
        self.sampling_config = None
        self.baseline: Optional[Baseline] = None
        self._bc_sample_vertices: List[int] = []

        # Bounded caches. All three are pure memoisation: dropping an entry
        # only costs time, never correctness.
        self.route_cache: "OrderedDict[bytes, RouteSet]" = OrderedDict()
        self._baseline_by_n: "OrderedDict[int, Baseline]" = OrderedDict()
        self._bc_cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self.payloads = PayloadCache(label=meta.id)

        self.meta.node_count = mirror.n_nodes
        self.meta.edge_count = mirror.n_edges
        self.last_used = time.time()

    # ── Construction ──────────────────────────────────────────────────────────

    @classmethod
    def from_networkx(
        cls,
        graph,
        area_id: str = DEFAULT_AREA_ID,
        name: str = "",
        kind: str = "default",
    ) -> "AreaGraph":
        """The area of a whole NetworkX graph, which is how Lausanne is loaded."""
        meta = AreaMeta(id=area_id, kind=kind, name=name or area_id)
        return cls(meta, GraphMirror(graph))

    @property
    def route_cache_size(self) -> int:
        return DYNAMIC_ROUTE_CACHE_SIZE if self.dynamic else ROUTE_CACHE_SIZE

    @property
    def baseline_cache_size(self) -> int:
        return DYNAMIC_BASELINE_CACHE_SIZE if self.dynamic else BASELINE_CACHE_SIZE

    @property
    def bc_cache_size(self) -> int:
        return DYNAMIC_BC_CACHE_SIZE if self.dynamic else BC_CACHE_SIZE

    def touch(self) -> None:
        """Mark the area as used, so the registry evicts it last."""
        self.last_used = time.time()

    # ── OD pairs and startup ──────────────────────────────────────────────────

    def sample_research_pairs(self, n_pairs: int, config, seed: int) -> None:
        """Draw the OD pairs of this area with the research-based sampler."""
        from app.services.sampling.od_sampler import generate_research_based_pairs_mirror

        self.sampling_config = config
        self.pairs, self.od_nodes = generate_research_based_pairs_mirror(
            self.mirror, n_pairs=n_pairs, config=config, seed=seed, return_nodes=True
        )

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
            mirror.speed_raw,
            mirror.speed_free,
            mirror.speed_co2,
            mirror.elev_gain,
            mirror.edge_u,
            mirror.edge_v,
            mirror.edge_key,
            mirror.uv_group,
            mirror.uv_u,
            mirror.uv_v,
            mirror.last_of_group,
            mirror.node_ids,
            mirror.node_x,
            mirror.node_y,
            mirror.street_count,
            self.base_co2_g,
            self.base_co2_per_km,
        )
        # igraph topology and the python side maps, measured at about 100 B
        # per edge and per node on Lausanne.
        total += 100 * (mirror.n_edges + mirror.n_nodes)

        if self.pairs is not None:
            total += _nbytes(self.pairs.origins, self.pairs.destinations)

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

        if self.baseline is not None:
            b = self.baseline
            total += route_set_bytes(b.routes)
            total += _nbytes(b.counts, b.counts_group, b.bc, b.bc_group, b.co2_per_km, b.co2_group)
            total += USAGE_ROW_BYTES * len(b.usage_rows)

        for small in self._baseline_by_n.values():
            # the route set is a view on the baseline one, only the rows are new
            total += _nbytes(small.counts, small.counts_group)
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

    def baseline_for(self, n_pairs: int) -> Baseline:
        """Baseline restricted to the first n_pairs OD pairs.

        The pair sets are nested, so this is a prefix of the full route set:
        no rerouting, only counting again. Cached per N.
        """
        if self.baseline is None:
            raise RuntimeError("Baseline not computed")
        n = min(n_pairs, len(self.baseline.pairs))
        if n >= len(self.baseline.pairs):
            return self.baseline

        cached = self._baseline_by_n.get(n)
        if cached is not None:
            self._baseline_by_n.move_to_end(n)
            return cached

        mirror = self.mirror
        routes = self.baseline.routes.prefix(n)
        counts = routes.edge_counts(mirror.n_edges)
        counts_group = mirror.group_sum(counts)
        small = Baseline(
            pairs=self.baseline.pairs.prefix(n),
            routes=routes,
            counts=counts,
            counts_group=counts_group,
            bc=self.baseline.bc,  # betweenness is a property of the graph, not of the OD set
            bc_group=self.baseline.bc_group,
            co2_per_km=self.baseline.co2_per_km,
            co2_group=self.baseline.co2_group,
        )
        small.usage_rows = build_edge_usage_rows(
            mirror,
            counts_group,
            routes.n_found,
            self.baseline.co2_group,
            betweenness=self.baseline.bc_group,
        )
        self._baseline_by_n[n] = small
        while len(self._baseline_by_n) > self.baseline_cache_size:
            self._baseline_by_n.popitem(last=False)
        logger.info("[BASELINE] built for %d pairs, %d rows", n, len(small.usage_rows))
        return small

    def build_baseline(self, config, seed: int) -> None:
        """Route the default pairs, compute betweenness and congested CO2."""
        mirror = self.mirror
        t0 = time.perf_counter()

        routes = route_pairs(mirror, self.pairs, mirror.travel_time)
        routes.compute_metrics(mirror, mirror.travel_time, self.base_co2_g)
        logger.info(
            "[AREA %s] %d routes in %.1f s", self.meta.id, routes.n_found, time.perf_counter() - t0
        )

        rng = random.Random(seed)
        n = min(config.n_nodes_preprocess, mirror.n_nodes)
        self._bc_sample_vertices = sorted(rng.sample(range(mirror.n_nodes), n))

        t0 = time.perf_counter()
        bc = bpr.compute_betweenness(mirror, mirror.travel_time, self._bc_sample_vertices, config)
        logger.info("[AREA %s] betweenness in %.1f s", self.meta.id, time.perf_counter() - t0)

        # CO2 per km at the baseline congested speeds, not at free flow.
        speed_cong = bpr.congested_speed(mirror, bc, mirror.speed_free, config)
        co2_per_km = bpr.co2_per_km(mirror, speed_cong)
        self.base_co2_per_km = co2_per_km

        counts = routes.edge_counts(mirror.n_edges)
        counts_group = mirror.group_sum(counts)
        bc_group = mirror.group_sum(bc)
        co2_group = mirror.group_max(co2_per_km)

        self.baseline = Baseline(
            pairs=self.pairs,
            routes=routes,
            counts=counts,
            counts_group=counts_group,
            bc=bc,
            bc_group=bc_group,
            co2_per_km=co2_per_km,
            co2_group=co2_group,
        )
        self.baseline.usage_rows = build_edge_usage_rows(
            mirror,
            counts_group,
            routes.n_found,
            co2_group,
            betweenness=bc_group,
        )
        # Freezing lives in main.py now: it is only right for the objects that
        # stay until the process ends, and an area can be evicted.
        logger.info(
            "[AREA %s] baseline ready, %d usage rows", self.meta.id, len(self.baseline.usage_rows)
        )

    # ── OD pairs ──────────────────────────────────────────────────────────────

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Random OD pairs within a radius of the Lausanne centre.

        Same draws as before: the mirror keeps the nodes in NetworkX order, so
        `random.sample` picks the same ones for the same seed.
        """
        if seed is not None:
            random.seed(seed)

        mirror = self.mirror
        center_lat, center_lon = 46.5225, 6.6328
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
        """Map a weight name to a per-edge array."""
        if weight == "length":
            return self.mirror.length
        if weight not in ("travel_time", "duration_bc"):
            logger.warning("Unknown weight %r, using travel_time", weight)
        return self.mirror.travel_time

    def calculate_routes(
        self,
        pairs: List[NodePair],
        weight: str = "travel_time",
        use_parallel: bool = None,
    ) -> List[Route]:
        """Shortest paths for the given OD pairs, as Route objects."""
        if not self.mirror or not pairs:
            return []
        rs = route_pairs(self.mirror, pairs, self._weights_for(weight))
        rs.compute_metrics(self.mirror, self.mirror.travel_time, self.base_co2_g)
        return rs.to_routes(self.mirror)

    def _route_set_for(self, pairs) -> RouteSet:
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

    def _betweenness(self, travel_time: np.ndarray, key: tuple) -> np.ndarray:
        """Betweenness on a modified network, memoised by modification set."""
        cached = self._bc_cache.get(key)
        if cached is not None:
            self._bc_cache.move_to_end(key)
            return cached
        bc = bpr.compute_betweenness(
            self.mirror,
            travel_time,
            self._bc_sample_vertices,
            self.sampling_config,
            label="delta-BC",
        )
        self._bc_cache[key] = bc
        while len(self._bc_cache) > self.bc_cache_size:
            self._bc_cache.popitem(last=False)
        return bc

    # ── Recalculation ─────────────────────────────────────────────────────────

    def recalculate_with_modifications(
        self,
        pairs: Optional[List[NodePair]] = None,
        edge_modifications: List[EdgeModification] = None,
        weight: str = "travel_time",
        use_congestion: bool = False,
        congestion_iterations: int = 1,
        resample_destinations: bool = False,
        include_baseline: bool = True,
        od_pairs: Optional[int] = None,
    ) -> dict:
        """Recalculate routes after edge modifications and return usage statistics.

        Three strategies:
          default            targeted reroute of the affected pairs, on
                             betweenness-derived congested times
          use_congestion     volume model, all pairs, iterated toward equilibrium
          resample_destinations  elastic demand, destinations are drawn again

        The graph is never modified: a removed edge is an infinite weight in
        this request's own weight array.
        """
        if not self.mirror:
            raise RuntimeError("Graph not loaded")
        if self.baseline is None:
            raise RuntimeError("Baseline not computed")

        mirror = self.mirror
        t_total = time.perf_counter()
        timing: dict = {}

        edge_modifications = edge_modifications or []

        with timed("cache_lookup", timing):
            if pairs:
                # The client gave its own pairs: N does not apply.
                pairs = PairArrays.coerce(pairs)
                n_pairs = len(pairs)
                original = self._route_set_for(pairs)
                base = None
                original_counts_group = mirror.group_sum(original.edge_counts(mirror.n_edges))
            else:
                if self.pairs is None:
                    raise RuntimeError("No pairs available")
                n_pairs = min(od_pairs or settings.od_pairs, len(self.pairs))
                base = self.baseline_for(n_pairs)
                pairs = base.pairs
                original = base.routes
                original_counts_group = base.counts_group

        with timed("apply_modifications", timing):
            (
                applied,
                travel_time,
                speed,
                co2_per_km,
                co2_g,
                blocked,
                changed_ids,
            ) = modifications_to_arrays(
                mirror,
                mirror.travel_time,
                mirror.speed_free,
                self.base_co2_per_km,
                self.base_co2_g,
                edge_modifications,
            )
            mods_key = tuple(sorted((m.u, m.v, m.action, m.speed_kph) for m in applied))

        resampled = False
        if resample_destinations and self.od_nodes is not None and self.sampling_config:
            new_routes, affected_idx, delta_bc_group = self._strategy_resample(
                pairs, travel_time, co2_g, timing
            )
            resampled = True
        elif use_congestion:
            new_routes, affected_idx, delta_bc_group = self._strategy_volume_model(
                pairs,
                travel_time,
                speed,
                blocked,
                co2_g,
                congestion_iterations,
                changed_ids,
                mods_key,
                timing,
            )
        else:
            new_routes, affected_idx, delta_bc_group = self._strategy_targeted_bc(
                pairs,
                original,
                travel_time,
                speed,
                blocked,
                co2_g,
                changed_ids,
                mods_key,
                timing,
            )

        with timed("impact_stats", timing):
            if resampled:
                impact_stats = self._elastic_impact(original, new_routes)
            else:
                impact_stats = compute_impact_statistics_arrays(original, new_routes, affected_idx)

        with timed("edge_usage", timing):
            new_counts = self._new_counts(original, new_routes, affected_idx, base)
            new_counts_group = mirror.group_sum(new_counts)
            co2_group = mirror.group_max(co2_per_km)
            total_routes = original.n_found

            if not include_baseline:
                # The baseline never changes. A client that already has it from
                # GET /routes/baseline saves about 1 MB per request.
                original_rows = []
            elif base is not None:
                original_rows = base.usage_rows
            else:
                original_rows = build_edge_usage_rows(
                    mirror,
                    original_counts_group,
                    total_routes,
                    co2_group,
                    betweenness=self.baseline.bc_group,
                )
            new_rows = build_edge_usage_rows(
                mirror,
                new_counts_group,
                total_routes,
                co2_group,
                original_counts=original_counts_group,
                betweenness=self.baseline.bc_group,
                delta_betweenness=delta_bc_group,
            )

        timing["total"] = (time.perf_counter() - t_total) * 1000
        ts = self._timing_stats(timing)
        logger.debug(
            "[TIMING] recalculate | %s",
            " ".join(f"{k}={v:.1f}ms" for k, v in timing.items()),
        )

        return {
            "od_pairs": n_pairs,
            "applied_modifications": [m.model_dump() for m in applied],
            "original_edge_usage": original_rows,
            "new_edge_usage": new_rows,
            "impact_statistics": impact_stats.model_dump(),
            "timing": ts.model_dump(),
            "_timing_raw": timing,
        }

    def _strategy_targeted_bc(
        self,
        pairs,
        original: RouteSet,
        travel_time,
        speed,
        blocked,
        co2_g,
        changed_ids,
        mods_key,
        timing,
    ):
        """Reroute only the pairs that used a modified edge.

        Congested times come from the betweenness of the modified network, so
        roads that absorb the rerouted traffic look slower and attract less.
        """
        mirror = self.mirror

        with timed("affected_routes", timing):
            affected_idx = original.routes_using(changed_ids)

        with timed("delta_bc", timing):
            delta_bc_group = None
            weights = travel_time
            if len(changed_ids) > 0:
                bc_new = self._betweenness(travel_time, mods_key)
                delta_bc_group = mirror.group_sum(bc_new - self.baseline.bc)
                weights = bpr.congested_travel_time(mirror, bc_new, speed, blocked)

        with timed("route_calculation", timing):
            new_routes = route_pairs(
                mirror, routing_engine.routed_pairs_subset(pairs, affected_idx), weights
            )
            new_routes.compute_metrics(mirror, travel_time, co2_g)

        return new_routes, affected_idx, delta_bc_group

    def _strategy_volume_model(
        self,
        pairs,
        travel_time,
        speed,
        blocked,
        co2_g,
        congestion_iterations,
        changed_ids,
        mods_key,
        timing,
    ):
        """Measure the real route volumes, apply BPR, iterate toward equilibrium.

        Every pair is rerouted, not only the affected ones, because congestion
        moves load across the whole network.
        """
        mirror = self.mirror

        with timed("delta_bc", timing):
            delta_bc_group = None
            if len(changed_ids) > 0:
                bc_new = self._betweenness(travel_time, mods_key)
                delta_bc_group = mirror.group_sum(bc_new - self.baseline.bc)

        with timed("route_calculation", timing):
            new_routes = bpr.run_congestion_routing(
                mirror,
                pairs,
                travel_time,
                speed,
                blocked,
                congestion_iterations,
                self.sampling_config,
            )
            new_routes.compute_metrics(mirror, travel_time, co2_g)

        return new_routes, np.arange(len(pairs)), delta_bc_group

    def _strategy_resample(self, pairs, travel_time, co2_g, timing):
        """Elastic demand: draw new destinations on the modified network."""
        from app.services.sampling.od_sampler import resample_od_destinations

        mirror = self.mirror
        with timed("od_resampling", timing):
            new_pairs = resample_od_destinations(
                pairs, self.od_nodes, mirror, travel_time, self.sampling_config
            )

        with timed("route_calculation", timing):
            new_routes = route_pairs(mirror, new_pairs, travel_time)
            new_routes.compute_metrics(mirror, travel_time, co2_g)

        return new_routes, np.arange(len(new_pairs)), None

    def _new_counts(
        self,
        original: RouteSet,
        new_routes: RouteSet,
        affected_idx: np.ndarray,
        base: Optional[Baseline],
    ) -> np.ndarray:
        """Edge counts after the change.

        When most routes were recalculated, count them directly. Otherwise
        patch the baseline counts: remove the old paths of the rerouted pairs
        and add the new ones.
        """
        mirror = self.mirror
        if len(new_routes) >= len(original) * 0.9:
            return new_routes.edge_counts(mirror.n_edges)

        counts = (base.counts if base is not None else original.edge_counts(mirror.n_edges)).copy()
        counts -= original.counts_for(affected_idx, mirror.n_edges)
        counts += new_routes.edge_counts(mirror.n_edges)
        return np.maximum(counts, 0.0)

    def _elastic_impact(self, original: RouteSet, new_routes: RouteSet) -> ImpactStatistics:
        """Aggregate comparison for elastic demand (per-route pairing is meaningless)."""
        failed = int((~new_routes.found).sum())
        return ImpactStatistics(
            total_routes=original.n_found,
            affected_routes=0,
            failed_routes=failed,
            total_distance_increase_km=float(
                (new_routes.distance.sum() - original.distance.sum()) / 1000
            ),
            total_time_increase_minutes=float(
                (new_routes.travel_time.sum() - original.travel_time.sum()) / 60
            ),
            total_co2_increase_grams=float(new_routes.co2.sum() - original.co2.sum()),
        )

    @staticmethod
    def _timing_stats(timing: dict) -> TimingStats:
        def ms(key):
            return round(timing[key], 1) if key in timing else None

        return TimingStats(
            cache_lookup_ms=ms("cache_lookup") or 0.0,
            graph_copy_ms=0.0,
            apply_modifications_ms=ms("apply_modifications") or 0.0,
            od_resampling_ms=ms("od_resampling"),
            affected_routes_ms=ms("affected_routes"),
            delta_bc_ms=ms("delta_bc"),
            route_calculation_ms=ms("route_calculation") or 0.0,
            impact_stats_ms=ms("impact_stats") or 0.0,
            edge_usage_stats_ms=ms("edge_usage") or 0.0,
            total_ms=round(timing["total"], 1),
        )

    # ── Payloads ──────────────────────────────────────────────────────────────

    def baseline_payload(self, od_pairs: Optional[int] = None) -> dict:
        """The unmodified edge usage for N pairs, as served by GET /routes/baseline."""
        if self.baseline is None:
            raise RuntimeError("Baseline not computed")
        n = min(od_pairs or settings.od_pairs, len(self.baseline.pairs))
        base = self.baseline_for(n)
        return {
            "total_routes": base.routes.n_found,
            "od_pairs": len(base.pairs),
            "edge_usage": base.usage_rows,
        }
