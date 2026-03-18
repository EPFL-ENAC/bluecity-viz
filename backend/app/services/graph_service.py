"""Graph service — thin orchestrator for routing and edge modification analysis.

Delegates to specialised modules:
  routing_engine  — igraph one-to-many Dijkstra routing
  bpr             — BPR congestion model and betweenness centrality
  graph_helpers   — edge stats, modification helpers, graph serialization
  sampling/       — research-based OD pair generation
"""

import logging
import time
from pathlib import Path
from typing import List, Optional
import random

import osmnx as ox

from app.models.route import (
    EdgeModification,
    ImpactStatistics,
    NodePair,
    RecalculateResponse,
    Route,
    TimingStats,
)
from app.services import bpr, routing_engine
from app.services.co2_calculator import CO2Calculator
from app.services.graph_helpers import (
    apply_edge_modifications,
    build_edge_usage_stats,
    count_edge_usage,
    get_edge_geometries,
    get_graph_data,
    restore_edge_modifications,
)
from app.services.impact_calculator import compute_impact_statistics
from app.services.utils.timing import timed

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger("osmnx")
ox_logger.setLevel(logging.INFO)


class GraphService:
    """Service for managing the road network graph and calculating routes.

    State caches (all keyed by (u, v) edge tuples):
        _edge_co2_cache     — CO2 in g/km (updated with BC-congested speeds at startup)
        _edge_metrics_cache — (travel_time, distance, elevation_gain, co2_g)
        _edge_bc_cache      — normalised betweenness centrality in veh/day
        _route_edge_index   — inverted index: pairs_key → {edge: [route_indices]}
    """

    # ── Graph Loading & Initialisation ────────────────────────────────────────

    def __init__(self, graph_path: Optional[str] = None):
        self.graph = None
        self.graph_path = graph_path
        self.route_cache = {}
        self.pairs_cache = None
        self.default_pairs = None
        self.default_routes = None
        self._edge_co2_cache: dict = {}
        self._edge_metrics_cache: dict = {}
        self._route_edge_index: dict = {}
        self._edge_bc_cache: dict = {}
        self._bc_sample_nodes: list = []
        self.od_nodes = None  # pd.Series {NX node ID → weight} — candidate pool for resampling
        self.sampling_config = None

        if graph_path:
            self.load_graph(graph_path)

    def load_graph(self, graph_path: str):
        """Load graph from GraphML and ensure speed/travel_time attributes are present."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)
        total = len(self.graph.edges)

        if sum(1 for _, _, d in self.graph.edges(data=True) if d.get("speed_kph", 0) > 0) < total * 0.9:
            self.graph = ox.routing.add_edge_speeds(self.graph)
        if sum(1 for _, _, d in self.graph.edges(data=True) if d.get("travel_time", 0) > 0) < total * 0.9:
            self.graph = ox.routing.add_edge_travel_times(self.graph)

        print(f"Loaded graph: {len(self.graph.nodes)} nodes, {total} edges")
        self._precompute_graph_metrics()

    def _precompute_graph_metrics(self):
        """Pre-compute CO2 and elevation for all edges; build flat lookup caches.

        Flat caches avoid repeated NetworkX attribute lookups in the hot routing path.
        """
        if not self.graph:
            return

        logging.info("Pre-computing graph metrics (CO2, elevation)...")
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            elevation_gain = data.get("elevation_gain")
            if elevation_gain is None:
                elevation_gain = 0.0
                if "elevation" in self.graph.nodes[u] and "elevation" in self.graph.nodes[v]:
                    diff = self.graph.nodes[v]["elevation"] - self.graph.nodes[u]["elevation"]
                    if diff > 0:
                        elevation_gain = diff
                data["elevation_gain"] = elevation_gain

            t = data.get("travel_time", 0)
            l = data.get("length", 0)
            s = data.get("speed_kph") or ((l / 1000) / (t / 3600) if t > 0 else None)
            data["co2_g"] = CO2Calculator.calculate_edge_co2(
                length=l, speed_kph=s, elevation_gain=elevation_gain
            )

        self._edge_co2_cache = {}
        self._edge_metrics_cache = {}
        for u, v, data in self.graph.edges(data=True):
            co2_g = data.get("co2_g") or 0.0
            length = data.get("length", 1) or 1
            length_km = length / 1000
            self._edge_co2_cache[(u, v)] = co2_g / length_km if length_km > 0 else 0.0
            self._edge_metrics_cache[(u, v)] = (
                data.get("travel_time", 0.0),
                length,
                data.get("elevation_gain", 0.0),
                co2_g,
            )

    # ── OD Pair Generation ────────────────────────────────────────────────────

    async def initialize_default_routes(
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Generate default OD pairs and pre-calculate baseline routes.

        Research-based sampling uses betweenness centrality and lognormal
        travel-time weighting to produce realistic trip distributions.
        After routing, computes baseline BC and updates CO2/km with congested speeds.
        """
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if sampling_method == "research":
            from app.services.node_sampling_service import SamplingConfig, generate_research_based_pairs
            config = sampling_config or SamplingConfig()
            self.sampling_config = config
            print(f"[STARTUP] Using research-based sampling with {count} OD pairs")
            self.default_pairs, self.od_nodes = generate_research_based_pairs(
                self.graph, n_pairs=count, config=config, seed=seed, return_nodes=True
            )
        else:
            print(f"[STARTUP] Using simple random sampling with {count} OD pairs")
            self.default_pairs = self.generate_random_pairs(count=count, seed=seed, radius_km=radius_km)

        self.default_routes = await self.calculate_routes(self.default_pairs, weight="travel_time")

        pairs_key = tuple((p.origin, p.destination) for p in self.default_pairs)
        self.pairs_cache = pairs_key
        self.route_cache[pairs_key] = self.default_routes
        self._route_edge_index[pairs_key] = routing_engine.build_route_edge_index(self.default_routes)
        print(f"[STARTUP] Pre-calculated {len(self.default_routes)} routes")

        logging.info("[STARTUP] Computing betweenness centrality...")
        self._edge_bc_cache, self._bc_sample_nodes = bpr.compute_betweenness(
            self.graph, self._bc_sample_nodes, sampling_config
        )
        logging.info(f"[STARTUP] BC computed for {len(self._edge_bc_cache)} edges")

        logging.info("[STARTUP] Updating CO2/km with BC-derived congested speeds...")
        bpr.update_co2_with_congestion(
            self.graph, self._edge_bc_cache, self._edge_co2_cache, sampling_config
        )
        logging.info("[STARTUP] CO2/km congestion update complete")

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Generate random OD pairs within a radius from Lausanne centre."""
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
            n for n in self.graph.nodes()
            if distance_km(self.graph.nodes[n]) <= radius_km
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

    async def calculate_routes(
        self,
        pairs: List[NodePair],
        weight: str = "travel_time",
        use_parallel: bool = None,
    ) -> List[Route]:
        """Calculate shortest paths for given OD pairs (weight = edge attribute to minimise)."""
        if not self.graph or not pairs:
            return []
        origin_groups = routing_engine.group_pairs_by_origin(pairs)
        logger.info(
            f"[ROUTING] {len(pairs)} pairs → {len(origin_groups)} origins "
            f"(avg {len(pairs)/len(origin_groups):.1f} dest/origin)"
        )
        routes = await routing_engine.calculate_routes_igraph(
            self.graph, self._edge_metrics_cache, origin_groups, weight
        )
        logger.info(f"[ROUTING] Calculated {len(routes)} routes")
        return routes

    # ── Edge Modifications & Recalculation ────────────────────────────────────

    async def _strategy_volume_model(
        self,
        pairs: List[NodePair],
        congestion_iterations: int,
        effective_modified_set: set,
        timing: dict,
    ) -> tuple:
        """Volume model: measure actual route loads, apply BPR, iterate toward Wardrop UE.

        All pairs are rerouted through the modified graph (not just affected ones),
        since congestion redistributes load globally.
        """
        with timed("delta_bc", timing):
            delta_bc = None
            if self._edge_bc_cache and effective_modified_set:
                new_bc, self._bc_sample_nodes = bpr.compute_betweenness(
                    self.graph, self._bc_sample_nodes, label="delta-BC"
                )
                delta_bc = {
                    (u, v): new_bc.get((u, v), 0.0) - self._edge_bc_cache.get((u, v), 0.0)
                    for (u, v) in set(new_bc) | set(self._edge_bc_cache)
                }

        with timed("route_calculation", timing):
            new_routes = await bpr.run_congestion_routing(
                self.graph, self._edge_metrics_cache, pairs, congestion_iterations
            )

        new_routes_by_index = {i: route for i, route in enumerate(new_routes)}
        affected_indices = list(range(len(new_routes)))
        return new_routes_by_index, delta_bc, affected_indices

    async def _strategy_targeted_bc(
        self,
        pairs: List[NodePair],
        pairs_key: tuple,
        effective_modified_set: set,
        timing: dict,
    ) -> tuple:
        """Default model (Marco's): theoretical BC → duration_bc → route only affected pairs.

        Only pairs whose original path used a modified edge are rerouted.
        Congested travel times (duration_bc) are derived from the new theoretical BC
        of the modified graph via the BPR formula.

        This is computationally efficient and theoretically grounded: roads that
        absorb rerouted traffic appear slower and attract fewer new routes.
        """
        with timed("affected_routes", timing):
            edge_index = self._route_edge_index.get(pairs_key, {})
            affected_set: set = set()
            for edge in effective_modified_set:
                affected_set.update(edge_index.get(edge, []))
            affected_indices = sorted(affected_set)

        with timed("delta_bc", timing):
            delta_bc = None
            if self._edge_bc_cache and effective_modified_set:
                new_bc, self._bc_sample_nodes = bpr.compute_betweenness(
                    self.graph, self._bc_sample_nodes, label="delta-BC"
                )
                delta_bc = {
                    (u, v): new_bc.get((u, v), 0.0) - self._edge_bc_cache.get((u, v), 0.0)
                    for (u, v) in set(new_bc) | set(self._edge_bc_cache)
                }
                bpr.write_bc_duration(self.graph, new_bc)

        with timed("route_calculation", timing):
            new_routes_by_index = {}
            if affected_indices:
                new_routes = await self.calculate_routes(
                    [pairs[i] for i in affected_indices], "duration_bc"
                )
                for i, idx in enumerate(affected_indices):
                    if i < len(new_routes):
                        new_routes_by_index[idx] = new_routes[i]

        return new_routes_by_index, delta_bc, affected_indices

    async def recalculate_with_modifications(
        self,
        pairs: Optional[List[NodePair]] = None,
        edge_modifications: List[EdgeModification] = None,
        weight: str = "travel_time",
        use_congestion: bool = False,
        congestion_iterations: int = 1,
        resample_destinations: bool = False,
    ) -> RecalculateResponse:
        """Recalculate routes after applying edge modifications (remove or change speed).

        Selects one of two strategies:
        - default: targeted BC reroute — only affected pairs, BC-derived weights
        - use_congestion=True: volume model — all pairs iteratively, Wardrop equilibrium

        Edge modifications are applied in-place and rolled back in the finally block.
        """
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        t_total_start = time.perf_counter()
        timing: dict = {}

        pairs = pairs or self.default_pairs
        if pairs is None:
            raise RuntimeError("No pairs available")
        edge_modifications = edge_modifications or []
        pairs_key = tuple((p.origin, p.destination) for p in pairs)

        with timed("cache_lookup", timing):
            if self.pairs_cache != pairs_key or pairs_key not in self.route_cache:
                original_routes = await self.calculate_routes(pairs, weight)
                self.pairs_cache = pairs_key
                self.route_cache[pairs_key] = original_routes
                self._route_edge_index[pairs_key] = routing_engine.build_route_edge_index(original_routes)
            else:
                original_routes = self.route_cache[pairs_key]

        with timed("apply_modifications", timing):
            applied, effective_modified_set, removed_edges, modified_edges = (
                apply_edge_modifications(
                    self.graph, self._edge_metrics_cache, self._edge_co2_cache,
                    edge_modifications
                )
            )

        resampled_pairs = None
        try:
            if resample_destinations and self.od_nodes is not None and self.sampling_config is not None:
                with timed("od_resampling", timing):
                    from app.services.sampling.igraph_utils import networkx_to_igraph_with_indices
                    from app.services.routing_engine import copy_weight_to_igraph
                    from app.services.sampling.od_sampler import resample_od_destinations
                    ig_mod, idx_maps_mod = networkx_to_igraph_with_indices(self.graph)
                    copy_weight_to_igraph(self.graph, ig_mod, idx_maps_mod, "travel_time")
                    resampled_pairs = resample_od_destinations(
                        pairs, self.od_nodes, ig_mod, idx_maps_mod, self.sampling_config
                    )

                with timed("route_calculation", timing):
                    all_new_routes = await self.calculate_routes(resampled_pairs, weight)
                new_routes_by_index = {i: r for i, r in enumerate(all_new_routes)}
                delta_bc = None
                affected_indices = list(range(len(all_new_routes)))
            elif use_congestion:
                new_routes_by_index, delta_bc, affected_indices = (
                    await self._strategy_volume_model(
                        pairs, congestion_iterations, effective_modified_set, timing
                    )
                )
            else:
                new_routes_by_index, delta_bc, affected_indices = (
                    await self._strategy_targeted_bc(
                        pairs, pairs_key, effective_modified_set, timing
                    )
                )
        finally:
            restore_edge_modifications(
                self.graph, self._edge_metrics_cache, self._edge_co2_cache,
                removed_edges, modified_edges
            )
            for u, v, k, data in self.graph.edges(keys=True, data=True):
                data.pop("duration_bc", None)

        with timed("impact_stats", timing):
            if resampled_pairs is not None:
                # Elastic demand: per-route comparison is meaningless (destinations changed).
                # Compare aggregate totals: sum of all new trips vs sum of all original trips.
                orig_time_s = sum(r.travel_time or 0 for r in original_routes)
                new_time_s = sum(r.travel_time or 0 for r in new_routes_by_index.values())
                orig_dist_m = sum(r.distance or 0 for r in original_routes)
                new_dist_m = sum(r.distance or 0 for r in new_routes_by_index.values())
                orig_co2_g = sum(r.co2_emissions or 0 for r in original_routes)
                new_co2_g = sum(r.co2_emissions or 0 for r in new_routes_by_index.values())
                failed = sum(1 for r in new_routes_by_index.values() if not r.path)
                impact_stats = ImpactStatistics(
                    total_routes=len(original_routes),
                    affected_routes=0,
                    failed_routes=failed,
                    total_distance_increase_km=(new_dist_m - orig_dist_m) / 1000,
                    total_time_increase_minutes=(new_time_s - orig_time_s) / 60,
                    total_co2_increase_grams=new_co2_g - orig_co2_g,
                )
            else:
                impact_stats, _ = compute_impact_statistics(
                    original_routes, new_routes_by_index, affected_indices, applied,
                    compute_comparisons=False,
                )

        with timed("edge_usage", timing):
            edge_index = self._route_edge_index.get(pairs_key, {})
            original_counts = {edge: len(indices) for edge, indices in edge_index.items()}

            if len(new_routes_by_index) >= len(original_routes) * 0.9:
                complete_counts = count_edge_usage(list(new_routes_by_index.values()))
            else:
                complete_counts = dict(original_counts)
                for idx, new_route in new_routes_by_index.items():
                    old_route = original_routes[idx]
                    for j in range(len(old_route.path) - 1):
                        edge = (old_route.path[j], old_route.path[j + 1])
                        if edge in complete_counts:
                            complete_counts[edge] -= 1
                            if complete_counts[edge] == 0:
                                del complete_counts[edge]
                    for j in range(len(new_route.path) - 1):
                        edge = (new_route.path[j], new_route.path[j + 1])
                        complete_counts[edge] = complete_counts.get(edge, 0) + 1

            original_usage = build_edge_usage_stats(
                self._edge_co2_cache, original_counts, len(original_routes),
                edge_bc_cache=self._edge_bc_cache or None,
            )
            new_usage = build_edge_usage_stats(
                self._edge_co2_cache, complete_counts, len(original_routes),
                original_counts, edge_bc_cache=self._edge_bc_cache or None,
                delta_bc=delta_bc,
            )

        timing["total"] = (time.perf_counter() - t_total_start) * 1000

        ts = TimingStats(
            cache_lookup_ms=round(timing.get("cache_lookup", 0), 1),
            graph_copy_ms=0.0,
            apply_modifications_ms=round(timing.get("apply_modifications", 0), 1),
            od_resampling_ms=(
                round(timing["od_resampling"], 1) if "od_resampling" in timing else None
            ),
            affected_routes_ms=(
                round(timing["affected_routes"], 1) if "affected_routes" in timing else None
            ),
            route_calculation_ms=round(timing.get("route_calculation", 0), 1),
            impact_stats_ms=round(timing.get("impact_stats", 0), 1),
            edge_usage_stats_ms=round(timing.get("edge_usage", 0), 1),
            total_ms=round(timing["total"], 1),
        )
        logger.info(
            "[TIMING] recalculate | "
            f"cache={ts.cache_lookup_ms}ms | "
            f"apply_mods={ts.apply_modifications_ms}ms | "
            + (f"od_resample={ts.od_resampling_ms}ms | " if ts.od_resampling_ms else "")
            + (f"affected_routes={ts.affected_routes_ms}ms | " if ts.affected_routes_ms else "")
            + (f"delta_bc={timing.get('delta_bc', 0):.1f}ms | " if timing.get("delta_bc") else "")
            + f"route_calc={ts.route_calculation_ms}ms | "
            f"impact_stats={ts.impact_stats_ms}ms | "
            f"edge_usage={ts.edge_usage_stats_ms}ms | "
            f"TOTAL={ts.total_ms}ms"
        )

        return RecalculateResponse(
            applied_modifications=applied,
            original_edge_usage=original_usage,
            new_edge_usage=new_usage,
            impact_statistics=impact_stats,
            timing=ts,
        )

    # ── Graph Data & Utilities ────────────────────────────────────────────────

    def get_graph_info(self) -> dict:
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        return {
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
            "sample_nodes": list(self.graph.nodes())[:20],
        }

    def get_edge_geometries(self, limit: Optional[int] = None) -> List[dict]:
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        return get_edge_geometries(self.graph, limit)

    def get_graph_data(self):
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        return get_graph_data(self.graph)

    def clear_route_cache(self):
        self.route_cache.clear()
        self.pairs_cache = None
