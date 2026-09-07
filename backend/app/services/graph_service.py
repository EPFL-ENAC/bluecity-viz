"""Graph service: routing and edge modification analysis.

The service owns the NetworkX graph (kept for CVRP and for the GeoJSON
endpoints) and a GraphMirror, the igraph + numpy view used for all routing.

A recalculate request builds its own weight arrays from the mirror's base
arrays and never writes to shared state, so requests cannot corrupt each
other. The lock is still taken because the NetworkX graph is shared with
CVRP and with the sampling code.

Delegates to:
  graph_mirror    - persistent igraph topology and per-edge arrays
  routing_engine  - one-to-many Dijkstra, RouteSet
  bpr             - BPR congestion model and betweenness centrality
  graph_helpers   - modification arrays, usage rows, graph serialization
  sampling/       - research-based OD pair generation
"""

import functools
import logging
import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import anyio.to_thread
import numpy as np
import osmnx as ox

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
from app.services.graph_helpers import (
    build_edge_usage_rows,
    get_edge_geometries,
    get_graph_data,
    modifications_to_arrays,
)
from app.services.graph_mirror import GraphMirror
from app.services.impact_calculator import compute_impact_statistics_arrays
from app.services.routing_engine import RouteSet, route_pairs
from app.services.utils.timing import timed

logger = logging.getLogger(__name__)
# main.py has no logging setup and belongs to another branch right now, so the
# app keeps configuring its own handler here, as it did before.
logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger("osmnx")
ox_logger.setLevel(logging.INFO)

# Route sets are a few hundred MB each at 76,400 pairs, so keep very few.
ROUTE_CACHE_SIZE = 3
# Betweenness costs about 450 ms and is the same for the same modifications.
BC_CACHE_SIZE = 16


@dataclass
class Baseline:
    """The unmodified network: computed once at startup, never rebuilt."""

    pairs: List[NodePair]
    routes: RouteSet
    counts: np.ndarray  # per igraph edge
    counts_group: np.ndarray  # per (u, v) group
    bc: np.ndarray  # per igraph edge, veh/day
    bc_group: np.ndarray
    co2_per_km: np.ndarray  # per igraph edge, congested
    co2_group: np.ndarray
    usage_rows: list = field(default_factory=list)


class GraphService:
    """Road network graph, routing and edge modification analysis."""

    def __init__(self, graph_path: Optional[str] = None):
        self.graph = None
        self.mirror: Optional[GraphMirror] = None
        self.graph_path = graph_path
        self.baseline: Optional[Baseline] = None
        self.default_pairs: Optional[List[NodePair]] = None
        self.od_nodes = None  # pd.Series {NX node id: weight}, pool for resampling
        self.sampling_config = None
        self._bc_sample_vertices: List[int] = []
        # Bounded caches. Both are pure memoisation: dropping an entry only
        # costs time, never correctness.
        self.route_cache: "OrderedDict[tuple, RouteSet]" = OrderedDict()
        self._bc_cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        # Guards the shared NetworkX graph, which CVRP copies and the sampling
        # code writes weight attributes to. Re-entrant so a locked method can
        # call another one.
        self.lock = threading.RLock()

        if graph_path:
            self.load_graph(graph_path)

    # ── Graph loading ─────────────────────────────────────────────────────────

    def load_graph(self, graph_path: str):
        """Load the GraphML file, make sure speeds are present, build the mirror."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)
        total = len(self.graph.edges)

        if (
            sum(1 for _, _, d in self.graph.edges(data=True) if d.get("speed_kph", 0) > 0)
            < total * 0.9
        ):
            self.graph = ox.routing.add_edge_speeds(self.graph)
        if (
            sum(1 for _, _, d in self.graph.edges(data=True) if d.get("travel_time", 0) > 0)
            < total * 0.9
        ):
            self.graph = ox.routing.add_edge_travel_times(self.graph)

        self._precompute_graph_metrics()
        self.mirror = GraphMirror(self.graph)
        self.base_co2_g = CO2Calculator.edge_co2_array(
            self.mirror.length, self.mirror.speed_co2, self.mirror.elev_gain
        )
        length_km = self.mirror.length / 1000.0
        self.base_co2_per_km = np.where(
            length_km > 0, self.base_co2_g / np.where(length_km > 0, length_km, 1.0), 0.0
        )
        logger.info("[STARTUP] graph loaded: %d nodes, %d edges", len(self.graph.nodes), total)

    def _precompute_graph_metrics(self):
        """Write elevation_gain and co2_g on the NetworkX edges.

        The mirror does not need this, but CVRP and the GeoJSON endpoints read
        the NetworkX graph, so the attributes stay where they were.
        """
        if not self.graph:
            return

        for u, v, _k, data in self.graph.edges(keys=True, data=True):
            elevation_gain = data.get("elevation_gain")
            if elevation_gain is None:
                elevation_gain = 0.0
                if "elevation" in self.graph.nodes[u] and "elevation" in self.graph.nodes[v]:
                    diff = self.graph.nodes[v]["elevation"] - self.graph.nodes[u]["elevation"]
                    if diff > 0:
                        elevation_gain = diff
                data["elevation_gain"] = elevation_gain

            t = data.get("travel_time", 0)
            length_m = data.get("length", 0)
            s = data.get("speed_kph") or ((length_m / 1000) / (t / 3600) if t > 0 else None)
            data["co2_g"] = CO2Calculator.calculate_edge_co2(
                length=length_m, speed_kph=s, elevation_gain=elevation_gain
            )

    # ── Startup: OD pairs and baseline ────────────────────────────────────────

    async def initialize_default_routes(
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Await-able wrapper: runs the sync startup work in a worker thread.

        main.py calls this with `await` during the FastAPI lifespan. The work
        is pure CPU, so it runs off the event loop.
        """
        await anyio.to_thread.run_sync(
            functools.partial(
                self.initialize_default_routes_sync,
                count=count,
                radius_km=radius_km,
                seed=seed,
                sampling_method=sampling_method,
                sampling_config=sampling_config,
            )
        )

    def initialize_default_routes_sync(
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Generate the default OD pairs and compute the baseline once."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        from app.services.sampling.config import SamplingConfig

        config = sampling_config or SamplingConfig()
        self.sampling_config = config

        if sampling_method == "research":
            from app.services.node_sampling_service import generate_research_based_pairs

            # main.py still passes count=500, which the old sampler ignored: the
            # real size was n_origins x n_destinations_per_origin. The size is a
            # setting now. Drop the argument in main.py when that file is free.
            n_pairs = settings.od_pairs
            if count != n_pairs:
                logger.info("[STARTUP] ignoring count=%s, using OD_PAIRS=%d", count, n_pairs)
            with self.lock:
                self.default_pairs, self.od_nodes = generate_research_based_pairs(
                    self.graph, n_pairs=n_pairs, config=config, seed=seed, return_nodes=True
                )
        else:
            logger.info("[STARTUP] simple random sampling, %d OD pairs", count)
            self.default_pairs = self.generate_random_pairs(
                count=count, seed=seed, radius_km=radius_km
            )

        logger.info("[STARTUP] %d OD pairs generated", len(self.default_pairs))
        self._build_baseline(config, seed)

    def _build_baseline(self, config, seed: int) -> None:
        """Route the default pairs, compute betweenness and congested CO2."""
        mirror = self.mirror
        t0 = time.perf_counter()

        routes = route_pairs(mirror, self.default_pairs, mirror.travel_time)
        routes.compute_metrics(mirror, mirror.travel_time, self.base_co2_g)
        logger.info("[STARTUP] %d routes in %.1f s", routes.n_found, time.perf_counter() - t0)

        rng = random.Random(seed)
        n = min(config.n_nodes_preprocess, mirror.n_nodes)
        self._bc_sample_vertices = sorted(rng.sample(range(mirror.n_nodes), n))

        t0 = time.perf_counter()
        bc = bpr.compute_betweenness(mirror, mirror.travel_time, self._bc_sample_vertices, config)
        logger.info("[STARTUP] betweenness in %.1f s", time.perf_counter() - t0)

        # CO2 per km at the baseline congested speeds, not at free flow.
        speed_cong = bpr.congested_speed(mirror, bc, mirror.speed_free, config)
        co2_per_km = bpr.co2_per_km(mirror, speed_cong)
        self.base_co2_per_km = co2_per_km

        counts = routes.edge_counts(mirror.n_edges)
        counts_group = mirror.group_sum(counts)
        bc_group = mirror.group_sum(bc)
        co2_group = mirror.group_max(co2_per_km)

        self.baseline = Baseline(
            pairs=self.default_pairs,
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
        logger.info("[STARTUP] baseline ready, %d usage rows", len(self.baseline.usage_rows))

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Generate random OD pairs within a radius of the Lausanne centre."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if seed is not None:
            random.seed(seed)

        center_lat, center_lon = 46.5225, 6.6328

        def distance_km(node):
            lat_km = (node["y"] - center_lat) * 111.0
            lon_km = (node["x"] - center_lon) * 111.0 * 0.7
            return (lat_km**2 + lon_km**2) ** 0.5

        nodes_in_radius = [
            n for n in self.graph.nodes() if distance_km(self.graph.nodes[n]) <= radius_km
        ]
        if len(nodes_in_radius) < 2:
            nodes_in_radius = list(self.graph.nodes())

        min_dist, pairs, attempts = 0.3, [], 0
        while len(pairs) < count and attempts < count * 10:
            attempts += 1
            o, d = random.sample(nodes_in_radius, 2)
            o_node, d_node = self.graph.nodes[o], self.graph.nodes[d]
            lat_km = (o_node["y"] - d_node["y"]) * 111.0
            lon_km = (o_node["x"] - d_node["x"]) * 111.0 * 0.7
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

    def _route_set_for(self, pairs: List[NodePair]) -> RouteSet:
        """RouteSet of the unmodified network for these pairs, memoised."""
        key = tuple((p.origin, p.destination) for p in pairs)
        cached = self.route_cache.get(key)
        if cached is not None:
            self.route_cache.move_to_end(key)
            return cached
        rs = route_pairs(self.mirror, pairs, self.mirror.travel_time)
        rs.compute_metrics(self.mirror, self.mirror.travel_time, self.base_co2_g)
        self.route_cache[key] = rs
        while len(self.route_cache) > ROUTE_CACHE_SIZE:
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
        while len(self._bc_cache) > BC_CACHE_SIZE:
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

        pairs = pairs or self.default_pairs
        if pairs is None:
            raise RuntimeError("No pairs available")
        edge_modifications = edge_modifications or []

        with timed("cache_lookup", timing):
            if pairs is self.default_pairs:
                base = self.baseline
                original = base.routes
                original_counts_group = base.counts_group
            else:
                original = self._route_set_for(pairs)
                base = None
                original_counts_group = mirror.group_sum(original.edge_counts(mirror.n_edges))

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

    # ── Graph data and utilities ──────────────────────────────────────────────

    def baseline_payload(self) -> dict:
        """The unmodified edge usage, as served by GET /routes/baseline."""
        if self.baseline is None:
            raise RuntimeError("Baseline not computed")
        return {
            "total_routes": self.baseline.routes.n_found,
            "od_pairs": len(self.baseline.pairs),
            "edge_usage": self.baseline.usage_rows,
        }

    def get_graph_info(self) -> dict:
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        with self.lock:
            return {
                "node_count": len(self.graph.nodes),
                "edge_count": len(self.graph.edges),
                "sample_nodes": list(self.graph.nodes())[:20],
                "od_pairs": len(self.default_pairs) if self.default_pairs else 0,
                "od_origins": len({p.origin for p in self.default_pairs})
                if self.default_pairs
                else 0,
                "n_destinations_per_origin": (
                    self.sampling_config.n_destinations_per_origin if self.sampling_config else None
                ),
            }

    def get_edge_geometries(self, limit: Optional[int] = None) -> List[dict]:
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        with self.lock:
            return get_edge_geometries(self.graph, limit)

    def get_graph_data(self):
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        with self.lock:
            return get_graph_data(self.graph)

    def clear_route_cache(self):
        """Drop the memoised route sets and betweenness. The baseline stays."""
        self.route_cache.clear()
        self._bc_cache.clear()
