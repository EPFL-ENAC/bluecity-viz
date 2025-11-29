"""Graph service orchestrator for route calculations."""

import logging
import os
import random
import time
from pathlib import Path
from typing import List, Optional

import networkx as nx
import osmnx as ox
from app.models.route import (
    Edge,
    EdgeUsageStats,
    GraphData,
    GraphEdge,
    ImpactStatistics,
    NodePair,
    PathGeometry,
    RecalculateResponse,
    Route,
    RouteComparison,
)
from app.services.co2_calculator import CO2Calculator

# Enable osmnx logging to see what it's doing
logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger("osmnx")
ox_logger.setLevel(logging.INFO)


class GraphService:
    """Service for managing graph and calculating routes."""

    def __init__(self, graph_path: Optional[str] = None):
        """
        Initialize graph service.

        Args:
            graph_path: Path to saved graph file (graphml format)
        """
        self.graph = None
        self.graph_path = graph_path
        self.route_cache = {}  # Cache for original routes by pairs hash
        self.pairs_cache = None  # Cache the last node pairs for comparison
        self.default_pairs = None  # Default OD pairs generated on startup
        self.default_routes = None  # Pre-calculated routes for default pairs

        if graph_path:
            self.load_graph(graph_path)

    def load_graph(self, graph_path: str):
        """Load graph from file."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)

        # Ensure graph has speed and travel time attributes
        edges_with_speed = sum(
            1 for _, _, d in self.graph.edges(data=True) if d.get("speed_kph", 0) > 0
        )
        edges_with_time = sum(
            1 for _, _, d in self.graph.edges(data=True) if d.get("travel_time", 0) > 0
        )
        total_edges = len(self.graph.edges)

        # Add/recalculate speeds if missing or invalid
        if edges_with_speed < total_edges * 0.9:
            print(f"[WARNING] Graph doesn't have fully populated edge speeds")
            self.graph = ox.routing.add_edge_speeds(self.graph)

        # Add/recalculate travel times if missing or invalid
        if edges_with_time < total_edges * 0.9:
            print(f"[WARNING] Graph doesn't have fully populated edge travel times")
            self.graph = ox.routing.add_edge_travel_times(self.graph)

        print(f"Loaded graph: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")

    async def initialize_default_routes(
        self, count: int = 500, radius_km: float = 2.0, seed: int = 42
    ):
        """
        Generate default OD pairs and pre-calculate routes on startup.

        Args:
            count: Number of OD pairs to generate
            radius_km: Radius from city center to sample nodes
            seed: Random seed for reproducible pairs
        """
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        print(f"[STARTUP] Generating {count} default OD pairs...")
        self.default_pairs = self.generate_random_pairs(count=count, seed=seed, radius_km=radius_km)

        print(f"[STARTUP] Pre-calculating routes for {len(self.default_pairs)} pairs...")
        start_time = time.time()
        self.default_routes = await self.calculate_routes(
            pairs=self.default_pairs, weight="travel_time"
        )
        elapsed = time.time() - start_time

        # Cache these routes
        pairs_key = tuple((p.origin, p.destination) for p in self.default_pairs)
        self.pairs_cache = pairs_key
        self.route_cache[pairs_key] = self.default_routes

        print(f"[STARTUP] Pre-calculated {len(self.default_routes)} routes in {elapsed:.2f}s")
        print(f"[STARTUP] Default routes cached and ready")

    def get_edge_geometries(self, limit: Optional[int] = None) -> List[dict]:
        """
        Get edge geometries for visualization.

        Args:
            limit: Optional limit on number of edges to return

        Returns:
            List of edge dictionaries with u, v, coordinates, and properties
        """
        import time

        if not self.graph:
            raise RuntimeError("Graph not loaded")

        start_time = time.time()
        edges = []

        iteration_start = time.time()
        for i, (u, v, data) in enumerate(self.graph.edges(data=True)):
            if limit and i >= limit:
                break

            # Get edge geometry
            if "geometry" in data:
                coords = [[lon, lat] for lon, lat in data["geometry"].coords]
            else:
                # Fallback to straight line between nodes
                coords = [
                    [self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]],
                    [self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]],
                ]

            # Get edge name
            name_raw = data.get("name")
            if isinstance(name_raw, list):
                name = name_raw[0] if name_raw else None
            elif name_raw:
                name = str(name_raw)
            else:
                name = None

            # Get highway type
            highway_raw = data.get("highway", "Unknown")
            highway = highway_raw[0] if isinstance(highway_raw, list) else highway_raw

            edge_dict = {
                "u": int(u),
                "v": int(v),
                "coordinates": coords,
                "travel_time": data.get("travel_time"),
                "length": data.get("length"),
                "name": name,
                "highway": highway,
            }
            edges.append(edge_dict)

        iteration_time = time.time() - iteration_start
        total_time = time.time() - start_time

        print(f"[PERF] Graph iteration: {iteration_time:.3f}s")
        print(f"[PERF] Total get_edge_geometries: {total_time:.3f}s for {len(edges)} edges")

        return edges

    def get_graph_info(self) -> dict:
        """Get information about the loaded graph."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        # Get sample nodes (first 20 nodes)
        sample_nodes = list(self.graph.nodes())[:20]

        return {
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
            "sample_nodes": sample_nodes,
        }

    def _build_path_geometry(self, path: List[int]) -> PathGeometry:
        """Build geometry for a path using actual road geometries from graph edges."""
        if not self.graph:
            return PathGeometry(coordinates=[])

        coordinates = []
        edges_with_geometry = 0
        edges_without_geometry = 0

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = self.graph.get_edge_data(u, v)

            if edge_data and "geometry" in edge_data:
                # Extract coordinates from Shapely LineString geometry
                coords = list(edge_data["geometry"].coords)
                edges_with_geometry += 1

                # Add all points for first edge, skip first point for subsequent edges to avoid duplication
                if i == 0:
                    coordinates.extend([[lon, lat] for lon, lat in coords])
                else:
                    coordinates.extend([[lon, lat] for lon, lat in coords[1:]])
            else:
                # Fallback to straight line between nodes
                edges_without_geometry += 1
                if i == 0:
                    coordinates.append([self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]])
                coordinates.append([self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]])

        # Only log occasionally to avoid spam (e.g., first route)
        if len(coordinates) > 0 and edges_with_geometry + edges_without_geometry <= 10:
            print(
                f"[GEOM] Built path with {len(coordinates)} points from {edges_with_geometry} edges with geometry, {edges_without_geometry} without"
            )

        return PathGeometry(coordinates=coordinates)

    def _calculate_route_metrics(self, path: List[int], weight: str) -> dict:
        """Calculate travel time, distance, and elevation gain for a path by summing edge attributes."""
        if not self.graph or not path or len(path) < 2:
            return {"travel_time": None, "distance": None, "elevation_gain": None, "edges_data": []}

        travel_time = 0.0
        distance = 0.0
        elevation_gain = 0.0
        edges_data = []  # Store edge data for CO2 calculation

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]

            # For MultiGraph, get_edge_data returns dict of {edge_key: edge_data}
            # We need to access the first edge (key=0) or iterate through all parallel edges
            edge_data_dict = self.graph.get_edge_data(u, v)

            if edge_data_dict:
                # Get the first edge's data (key 0) or the data itself if not a MultiGraph
                if isinstance(edge_data_dict, dict) and 0 in edge_data_dict:
                    # MultiGraph: access first parallel edge
                    edge_data = edge_data_dict[0]
                else:
                    # Regular Graph: edge_data_dict is the data itself
                    edge_data = edge_data_dict

                edge_travel_time = edge_data.get("travel_time", 0)
                edge_length = edge_data.get("length", 0)
                travel_time += edge_travel_time
                distance += edge_length

                # Calculate elevation gain for this edge
                edge_elevation_gain = 0.0
                if "elevation" in self.graph.nodes[u] and "elevation" in self.graph.nodes[v]:
                    elev_diff = self.graph.nodes[v]["elevation"] - self.graph.nodes[u]["elevation"]
                    if elev_diff > 0:  # Only count uphill
                        elevation_gain += elev_diff
                        edge_elevation_gain = elev_diff

                # Calculate speed for this edge (km/h)
                speed_kph = None
                if edge_travel_time > 0 and edge_length > 0:
                    speed_kph = (edge_length / 1000.0) / (edge_travel_time / 3600.0)

                # Store edge data for CO2 calculation
                edges_data.append(
                    {
                        "travel_time": edge_travel_time,
                        "speed_kph": speed_kph,
                        "elevation_gain": edge_elevation_gain,
                    }
                )
            else:
                print(f"[WARNING] No edge data for {u}->{v} in path")

        # Return actual values, not None - we need the numbers for delta calculations
        return {
            "travel_time": travel_time,
            "distance": distance,
            "elevation_gain": elevation_gain if elevation_gain > 0 else None,
            "edges_data": edges_data,
        }

    def _calculate_edge_usage_stats(
        self, routes: List[Route], total_routes: int, original_stats: Optional[dict] = None
    ) -> List[EdgeUsageStats]:
        """Calculate edge usage statistics from routes."""
        edge_counts = {}

        # Count edge usage across all routes
        for route in routes:
            for i in range(len(route.path) - 1):
                u, v = route.path[i], route.path[i + 1]
                edge_key = (u, v)
                edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1

        # Build statistics with frequency
        stats = []
        for (u, v), count in edge_counts.items():
            frequency = count / total_routes if total_routes > 0 else 0

            # Calculate delta if original stats provided
            delta_count = None
            delta_frequency = None
            if original_stats and (u, v) in original_stats:
                orig_count = original_stats[(u, v)]["count"]
                orig_freq = original_stats[(u, v)]["frequency"]
                delta_count = count - orig_count
                delta_frequency = frequency - orig_freq
            elif original_stats:
                # Edge is new (not in original)
                delta_count = count
                delta_frequency = frequency

            # Calculate CO2 per use for this edge
            co2_per_use = None
            edge_data_dict = self.graph.get_edge_data(u, v)
            if edge_data_dict:
                if isinstance(edge_data_dict, dict) and 0 in edge_data_dict:
                    edge_data = edge_data_dict[0]
                else:
                    edge_data = edge_data_dict

                edge_travel_time = edge_data.get("travel_time", 0)
                edge_length = edge_data.get("length", 0)

                # Calculate speed
                speed_kph = None
                if edge_travel_time > 0 and edge_length > 0:
                    speed_kph = (edge_length / 1000.0) / (edge_travel_time / 3600.0)

                # Calculate elevation gain for this edge
                edge_elevation_gain = 0.0
                if u in self.graph.nodes and v in self.graph.nodes:
                    if "elevation" in self.graph.nodes[u] and "elevation" in self.graph.nodes[v]:
                        elev_diff = (
                            self.graph.nodes[v]["elevation"] - self.graph.nodes[u]["elevation"]
                        )
                        if elev_diff > 0:
                            edge_elevation_gain = elev_diff

                co2_per_use = CO2Calculator.calculate_edge_co2(
                    travel_time=edge_travel_time,
                    speed_kph=speed_kph,
                    elevation_gain=edge_elevation_gain,
                )

            stats.append(
                EdgeUsageStats(
                    u=u,
                    v=v,
                    count=count,
                    frequency=frequency,
                    delta_count=delta_count,
                    delta_frequency=delta_frequency,
                    co2_per_use=co2_per_use,
                )
            )

        # Sort by frequency descending
        stats.sort(key=lambda x: x.frequency, reverse=True)
        return stats

    async def calculate_routes(
        self, pairs: List[NodePair], weight: str = "travel_time", use_parallel: bool = None
    ) -> List[Route]:
        """Calculate shortest paths for given node pairs."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if not pairs:
            return []

        # Auto-determine parallelization based on number of routes
        if use_parallel is None:
            use_parallel = len(pairs) > 100

        # Check available CPU cores
        cpu_count = os.cpu_count()
        print(f"[PERF] Available CPU cores: {cpu_count}")

        start_time = time.time()
        print(
            f"[PERF] Starting route calculation for {len(pairs)} pairs (parallel={use_parallel}, auto={use_parallel is None})"
        )

        # Extract origins and destinations for batch processing
        origins = [pair.origin for pair in pairs]
        destinations = [pair.destination for pair in pairs]

        path_calc_start = time.time()

        if use_parallel:
            # Use multiprocessing for faster calculation
            # Optimal number of CPUs for this workload (too many causes overhead)
            cpus_to_use = min(4, cpu_count or 1)  # Cap at 4 cores for best performance
            print(
                f"[PERF] Calling ox.routing.shortest_path with cpus={cpus_to_use} (of {cpu_count} available)"
            )
            print(f"[PERF] Origins type: {type(origins)}, length: {len(origins)}")
            print(f"[PERF] Destinations type: {type(destinations)}, length: {len(destinations)}")

            try:
                paths = ox.routing.shortest_path(
                    self.graph, origins, destinations, weight=weight, cpus=cpus_to_use
                )
                path_calc_time = time.time() - path_calc_start
                print(
                    f"[PERF] Parallel shortest_path took {path_calc_time:.2f}s for {len(pairs)} pairs ({path_calc_time/len(pairs)*1000:.2f}ms per route)"
                )
                print(f"[PERF] Returned {len(paths) if paths else 0} paths")
            except Exception as e:
                print(f"Parallel shortest path failed: {e}, falling back to sequential")
                use_parallel = False

        if not use_parallel:
            # Sequential is often faster for graphs in memory without multiprocessing overhead
            paths = []
            for pair in pairs:
                try:
                    path = ox.routing.shortest_path(
                        self.graph, pair.origin, pair.destination, weight=weight
                    )
                    paths.append(path)
                except Exception as path_error:
                    print(
                        f"Failed to calculate route {pair.origin} -> {pair.destination}: {path_error}"
                    )
                    paths.append(None)
            path_calc_time = time.time() - path_calc_start
            print(
                f"[PERF] Sequential shortest_path took {path_calc_time:.2f}s for {len(pairs)} pairs ({path_calc_time/len(pairs)*1000:.1f}ms per route)"
            )

        # Build Route objects from paths
        build_start = time.time()
        routes = []
        for idx, (pair, path) in enumerate(zip(pairs, paths)):
            if path is None:
                continue

            try:
                metrics = self._calculate_route_metrics(path, weight)

                # Calculate CO2 emissions
                co2_emissions = CO2Calculator.calculate_route_co2(metrics["edges_data"])

                route = Route(
                    origin=pair.origin,
                    destination=pair.destination,
                    path=path,
                    travel_time=metrics["travel_time"],
                    distance=metrics["distance"],
                    elevation_gain=metrics["elevation_gain"],
                    co2_emissions=co2_emissions,
                )
                routes.append(route)
            except Exception as e:
                print(f"Failed to build route {pair.origin} -> {pair.destination}: {e}")
                continue

        build_time = time.time() - build_start
        total_time = time.time() - start_time
        print(f"[PERF] Building {len(routes)} Route objects took {build_time:.2f}s")
        print(f"[PERF] Total calculate_routes took {total_time:.2f}s")

        return routes

    async def recalculate_with_removed_edges(
        self,
        pairs: Optional[List[NodePair]] = None,
        edges_to_remove: List[Edge] = None,
        weight: str = "travel_time",
    ) -> RecalculateResponse:
        """Recalculate routes after removing specified edges."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        # Use default pairs if none provided
        if pairs is None:
            if self.default_pairs is None:
                raise RuntimeError(
                    "No default pairs available. Call initialize_default_routes first."
                )
            pairs = self.default_pairs

        if edges_to_remove is None:
            edges_to_remove = []

        total_start = time.time()
        print("[PERF] ===== Starting recalculate_with_removed_edges =====")
        print(f"[PERF] Pairs: {len(pairs)}, " f"Edges to remove: {len(edges_to_remove)}")

        # Generate cache key for current pairs
        pairs_key = tuple((p.origin, p.destination) for p in pairs)

        # Check if we need to recalculate original routes
        if self.pairs_cache != pairs_key or pairs_key not in self.route_cache:
            print("[PERF] Cache miss - calculating original routes")
            orig_start = time.time()
            original_routes = await self.calculate_routes(pairs, weight)
            orig_time = time.time() - orig_start
            print(f"[PERF] Original routes calculation took {orig_time:.2f}s")

            # Cache the results
            self.pairs_cache = pairs_key
            self.route_cache[pairs_key] = original_routes
        else:
            print("[PERF] Cache hit - using cached original routes")
            original_routes = self.route_cache[pairs_key]

        # Build set of removed edges for fast lookup
        removed_edges_set = {(edge.u, edge.v) for edge in edges_to_remove}

        # Find routes that have removed edges in their original path
        pairs_to_recalculate = []
        pairs_indices_to_recalculate = []

        for i, route in enumerate(original_routes):
            for j in range(len(route.path) - 1):
                edge = (route.path[j], route.path[j + 1])
                if edge in removed_edges_set:
                    pairs_to_recalculate.append(pairs[i])
                    pairs_indices_to_recalculate.append(i)
                    break

        print(f"[PERF] {len(pairs_to_recalculate)}/{len(pairs)} routes need recalculation")

        # Create modified graph
        copy_start = time.time()
        G_modified = self.graph.copy()
        copy_time = time.time() - copy_start
        print(f"[PERF] Graph copy took {copy_time:.2f}s")

        remove_start = time.time()
        removed = []
        for edge in edges_to_remove:
            if G_modified.has_edge(edge.u, edge.v):
                G_modified.remove_edge(edge.u, edge.v)
                removed.append(edge)
        remove_time = time.time() - remove_start
        print(f"[PERF] Removing {len(removed)} edges took {remove_time:.2f}s")

        # Recalculate only affected routes
        new_routes = []
        if pairs_to_recalculate:
            recalc_start = time.time()

            # Temporarily swap graphs
            original_graph = self.graph
            self.graph = G_modified

            # Calculate new routes for affected pairs only
            new_routes = await self.calculate_routes(pairs_to_recalculate, weight)

            # Restore original graph
            self.graph = original_graph

            recalc_time = time.time() - recalc_start
            print(
                f"[PERF] Recalculating {len(pairs_to_recalculate)} routes took {recalc_time:.2f}s"
            )

        # Calculate impact by comparing original vs new routes for affected pairs
        total_routes = len(pairs)
        affected_routes_count = 0  # Will count only routes with actual increases
        failed_routes_count = 0
        total_distance_increase = 0.0
        total_time_increase = 0.0
        total_co2_increase = 0.0
        max_distance_increase = 0.0
        max_time_increase = 0.0
        max_co2_increase = 0.0
        distance_percent_increases = []
        time_percent_increases = []
        co2_percent_increases = []

        comparisons = []

        # Create mapping of pair index to new route
        new_routes_by_index = {}
        new_route_idx = 0
        for orig_idx in pairs_indices_to_recalculate:
            if new_route_idx < len(new_routes):
                new_routes_by_index[orig_idx] = new_routes[new_route_idx]
                new_route_idx += 1

        # Build comparisons for affected routes
        for orig_idx in pairs_indices_to_recalculate:
            orig_route = original_routes[orig_idx]
            new_route = new_routes_by_index.get(orig_idx)

            if new_route is None:
                # Route not calculated (shouldn't happen but be safe)
                failed_routes_count += 1
                continue

            # Check if removed edge was on original path
            removed_on_path = None
            for edge in removed:
                for i in range(len(orig_route.path) - 1):
                    if orig_route.path[i] == edge.u and orig_route.path[i + 1] == edge.v:
                        removed_on_path = edge
                        break
                if removed_on_path:
                    break

            # Calculate deltas
            route_failed = False
            distance_delta = None
            distance_delta_percent = None
            time_delta = None
            time_delta_percent = None

            if new_route.path is None or len(new_route.path) == 0:
                # Route calculation failed
                route_failed = True
                failed_routes_count += 1
            else:
                # Only count as affected if new route is longer (or equal)
                is_actually_affected = False

                # Calculate distance delta
                if orig_route.distance is not None and new_route.distance is not None:
                    distance_delta = new_route.distance - orig_route.distance
                    if distance_delta >= 0:  # Only count increases or equal
                        is_actually_affected = True
                        total_distance_increase += distance_delta
                        max_distance_increase = max(max_distance_increase, distance_delta)
                        if orig_route.distance > 0:
                            distance_delta_percent = (distance_delta / orig_route.distance) * 100
                            distance_percent_increases.append(distance_delta_percent)

                # Calculate time delta
                if orig_route.travel_time is not None and new_route.travel_time is not None:
                    time_delta = new_route.travel_time - orig_route.travel_time
                    if time_delta >= 0:  # Only count increases or equal
                        is_actually_affected = True
                        total_time_increase += time_delta
                        max_time_increase = max(max_time_increase, time_delta)

                        if orig_route.travel_time > 0:
                            time_delta_percent = (time_delta / orig_route.travel_time) * 100
                            time_percent_increases.append(time_delta_percent)

                # Calculate CO2 delta
                if orig_route.co2_emissions is not None and new_route.co2_emissions is not None:
                    co2_delta = new_route.co2_emissions - orig_route.co2_emissions
                    if co2_delta >= 0:  # Only count increases or equal
                        total_co2_increase += co2_delta
                        max_co2_increase = max(max_co2_increase, co2_delta)

                        if orig_route.co2_emissions > 0:
                            co2_delta_percent = (co2_delta / orig_route.co2_emissions) * 100
                            co2_percent_increases.append(co2_delta_percent)

                if is_actually_affected:
                    affected_routes_count += 1

            comparison = RouteComparison(
                origin=orig_route.origin,
                destination=orig_route.destination,
                original_route=orig_route,
                new_route=new_route,
                removed_edge_on_path=removed_on_path,
                distance_delta=distance_delta,
                distance_delta_percent=distance_delta_percent,
                time_delta=time_delta,
                time_delta_percent=time_delta_percent,
                is_affected=True,
                route_failed=route_failed,
            )
            comparisons.append(comparison)

        # Calculate aggregate statistics
        avg_distance_increase_km = (
            (total_distance_increase / 1000.0 / affected_routes_count)
            if affected_routes_count > 0
            else 0.0
        )
        avg_time_increase_minutes = (
            (total_time_increase / 60.0 / affected_routes_count)
            if affected_routes_count > 0
            else 0.0
        )
        avg_co2_increase_grams = (
            (total_co2_increase / affected_routes_count) if affected_routes_count > 0 else 0.0
        )
        avg_distance_percent = (
            sum(distance_percent_increases) / len(distance_percent_increases)
            if distance_percent_increases
            else 0.0
        )
        avg_time_percent = (
            sum(time_percent_increases) / len(time_percent_increases)
            if time_percent_increases
            else 0.0
        )
        avg_co2_percent = (
            sum(co2_percent_increases) / len(co2_percent_increases)
            if co2_percent_increases
            else 0.0
        )

        impact_stats = ImpactStatistics(
            total_routes=total_routes,
            affected_routes=affected_routes_count,
            failed_routes=failed_routes_count,
            total_distance_increase_km=total_distance_increase / 1000.0,
            total_time_increase_minutes=total_time_increase / 60.0,
            avg_distance_increase_km=avg_distance_increase_km,
            avg_time_increase_minutes=avg_time_increase_minutes,
            max_distance_increase_km=max_distance_increase / 1000.0,
            max_time_increase_minutes=max_time_increase / 60.0,
            avg_distance_increase_percent=avg_distance_percent,
            avg_time_increase_percent=avg_time_percent,
            total_co2_increase_grams=total_co2_increase,
            avg_co2_increase_grams=avg_co2_increase_grams,
            max_co2_increase_grams=max_co2_increase,
            avg_co2_increase_percent=avg_co2_percent,
        )

        # Calculate edge usage statistics - need to create full new_routes list
        # Use original routes for unaffected, new routes for affected
        complete_new_routes = list(original_routes)
        for orig_idx, new_route in new_routes_by_index.items():
            complete_new_routes[orig_idx] = new_route

        stats_start = time.time()

        # Calculate original edge usage
        original_edge_usage = self._calculate_edge_usage_stats(original_routes, total_routes)

        # Build dict for delta calculation
        original_stats_dict = {
            (stat.u, stat.v): {"count": stat.count, "frequency": stat.frequency}
            for stat in original_edge_usage
        }

        # Calculate new edge usage with delta
        new_edge_usage = self._calculate_edge_usage_stats(
            complete_new_routes, total_routes, original_stats_dict
        )

        stats_time = time.time() - stats_start
        total_time = time.time() - total_start

        print(f"[PERF] Calculating edge usage stats took {stats_time:.2f}s")
        print(f"[PERF] Original: {len(original_edge_usage)} unique edges used")
        print(f"[PERF] New: {len(new_edge_usage)} unique edges used")
        print(f"[IMPACT] Affected routes: {affected_routes_count}/{total_routes}")
        print(f"[IMPACT] Failed routes: {failed_routes_count}")
        print(
            f"[IMPACT] Total distance increase: {total_distance_increase/1000.0:.2f} km (raw: {total_distance_increase:.2f}m)"
        )
        print(
            f"[IMPACT] Total time increase: {total_time_increase/60.0:.2f} minutes (raw: {total_time_increase:.2f}s)"
        )
        print(
            f"[IMPACT] Total CO2 increase: {total_co2_increase:.2f} grams ({total_co2_increase/1000.0:.3f} kg)"
        )
        print(f"[IMPACT] Max distance increase: {max_distance_increase/1000.0:.2f} km")
        print(f"[IMPACT] Max time increase: {max_time_increase/60.0:.2f} minutes")
        print(f"[IMPACT] Max CO2 increase: {max_co2_increase:.2f} grams")
        print(f"[IMPACT] Avg distance increase: {avg_distance_increase_km:.2f} km")
        print(f"[IMPACT] Avg time increase: {avg_time_increase_minutes:.2f} minutes")
        print(f"[IMPACT] Avg CO2 increase: {avg_co2_increase_grams:.2f} grams")
        print(f"[PERF] ===== Total recalculate took {total_time:.2f}s =====")

        # Return routes for visualization (use complete_new_routes which includes both original and recalculated)
        return RecalculateResponse(
            removed_edges=removed,
            original_edge_usage=original_edge_usage,
            new_edge_usage=new_edge_usage,
            impact_statistics=impact_stats,
            routes=complete_new_routes,  # Return all routes for trips visualization
        )

    def get_graph_data(self) -> GraphData:
        """Get complete graph data for visualization."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        edges = []
        for u, v, d in self.graph.edges(data=True):
            # Build geometry
            if "geometry" in d:
                coords = list(d["geometry"].coords)
                geometry = PathGeometry(coordinates=[[lon, lat] for lon, lat in coords])
            else:
                u_x, u_y = self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]
                v_x, v_y = self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]
                geometry = PathGeometry(coordinates=[[u_x, u_y], [v_x, v_y]])

            # Get metadata
            name_raw = d.get("name")
            if isinstance(name_raw, list):
                name = " - ".join(str(n) for n in name_raw if n)
            elif name_raw:
                name = str(name_raw)
            else:
                name = None

            highway_raw = d.get("highway", "Unknown")
            highway = highway_raw[0] if isinstance(highway_raw, list) else highway_raw

            edge = GraphEdge(
                u=u,
                v=v,
                geometry=geometry,
                name=name,
                highway=highway,
                speed_kph=d.get("speed_kph"),
                length=d.get("length"),
                travel_time=d.get("travel_time"),
            )
            edges.append(edge)

        return GraphData(
            edges=edges,
            node_count=len(self.graph.nodes),
            edge_count=len(self.graph.edges),
        )

    def clear_route_cache(self):
        """Clear the cached routes."""
        self.route_cache.clear()
        self.pairs_cache = None
        print("[CACHE] Route cache cleared")

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Generate random origin-destination node pairs within radius from center."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if seed is not None:
            random.seed(seed)

        # Lausanne city center coordinates (Place de la Riponne)
        center_lat, center_lon = 46.5225, 6.6328

        # Filter nodes within radius
        nodes_in_radius = []
        for node_id in self.graph.nodes():
            node = self.graph.nodes[node_id]
            node_lat, node_lon = node["y"], node["x"]

            # Calculate approximate distance in km using Haversine formula
            lat_diff = node_lat - center_lat
            lon_diff = node_lon - center_lon

            # Approximate distance (good enough for small areas)
            lat_km = lat_diff * 111.0  # 1 degree latitude ≈ 111 km
            lon_km = lon_diff * 111.0 * 0.7  # adjusted for Lausanne's latitude
            distance_km = (lat_km**2 + lon_km**2) ** 0.5

            if distance_km <= radius_km:
                nodes_in_radius.append(node_id)

        if len(nodes_in_radius) < 2:
            # Fallback to all nodes if radius too small
            nodes_in_radius = list(self.graph.nodes())

        # Generate pairs ensuring origin and destination are not too close
        min_distance_km = 0.3  # Minimum 300 meters between origin and destination
        pairs = []
        max_attempts = count * 10  # Prevent infinite loop
        attempts = 0

        while len(pairs) < count and attempts < max_attempts:
            attempts += 1
            origin, destination = random.sample(nodes_in_radius, 2)

            # Check distance between origin and destination
            orig_node = self.graph.nodes[origin]
            dest_node = self.graph.nodes[destination]

            lat_diff = orig_node["y"] - dest_node["y"]
            lon_diff = orig_node["x"] - dest_node["x"]
            lat_km = lat_diff * 111.0
            lon_km = lon_diff * 111.0 * 0.7
            distance_km = (lat_km**2 + lon_km**2) ** 0.5

            # Only add pair if nodes are far enough apart
            if distance_km >= min_distance_km:
                pairs.append(NodePair(origin=origin, destination=destination))

        if len(pairs) < count:
            print(
                f"Warning: Only generated {len(pairs)} pairs (requested {count}). Try increasing radius or decreasing min_distance."
            )

        return pairs
