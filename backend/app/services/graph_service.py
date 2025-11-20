"""Graph service for route calculations."""

import osmnx as ox
import networkx as nx
import random
import time
import os
import logging
from typing import List, Optional, Tuple
from pathlib import Path
import random

from app.models.route import (
    NodePair,
    Edge,
    Route,
    PathGeometry,
    RouteComparison,
    RecalculateResponse,
    GraphEdge,
    GraphData,
    EdgeUsageStats,
)

# Enable osmnx logging to see what it's doing
logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger('osmnx')
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

        if graph_path:
            self.load_graph(graph_path)

    def load_graph(self, graph_path: str):
        """Load graph from file."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)

        # Ensure graph has speed and travel time
        if not any("speed_kph" in d for _, _, d in self.graph.edges(data=True)):
            self.graph = ox.routing.add_edge_speeds(self.graph)
        if not any("travel_time" in d for _, _, d in self.graph.edges(data=True)):
            self.graph = ox.routing.add_edge_travel_times(self.graph)

        print(
            f"Loaded graph: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges"
        )

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
                    [self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]]
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
                "highway": highway
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
        """Build geometry for a path."""
        if not self.graph:
            return PathGeometry(coordinates=[])

        coordinates = []
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = self.graph.get_edge_data(u, v)

            if edge_data and "geometry" in edge_data:
                coords = list(edge_data["geometry"].coords)
                if i == 0:
                    coordinates.extend([[lon, lat] for lon, lat in coords])
                else:
                    coordinates.extend([[lon, lat] for lon, lat in coords[1:]])
            else:
                if i == 0:
                    coordinates.append(
                        [self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]]
                    )
                coordinates.append([self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]])

        return PathGeometry(coordinates=coordinates)

    def _calculate_route_metrics(self, path: List[int], weight: str) -> dict:
        """Calculate travel time and distance for a path."""
        if not self.graph or not path:
            return {"travel_time": None, "distance": None}

        travel_time = 0
        distance = 0

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data = self.graph.get_edge_data(u, v)

            if edge_data:
                travel_time += edge_data.get("travel_time", 0)
                distance += edge_data.get("length", 0)

        return {"travel_time": travel_time, "distance": distance}

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
                orig_count = original_stats[(u, v)]['count']
                orig_freq = original_stats[(u, v)]['frequency']
                delta_count = count - orig_count
                delta_frequency = frequency - orig_freq
            elif original_stats:
                # Edge is new (not in original)
                delta_count = count
                delta_frequency = frequency
            
            stats.append(EdgeUsageStats(
                u=u,
                v=v,
                count=count,
                frequency=frequency,
                delta_count=delta_count,
                delta_frequency=delta_frequency
            ))
        
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
        print(f"[PERF] Starting route calculation for {len(pairs)} pairs (parallel={use_parallel}, auto={use_parallel is None})")

        # Extract origins and destinations for batch processing
        origins = [pair.origin for pair in pairs]
        destinations = [pair.destination for pair in pairs]

        path_calc_start = time.time()
        
        if use_parallel:
            # Use multiprocessing for faster calculation
            # Optimal number of CPUs for this workload (too many causes overhead)
            cpus_to_use = min(4, cpu_count or 1)  # Cap at 4 cores for best performance
            print(f"[PERF] Calling ox.routing.shortest_path with cpus={cpus_to_use} (of {cpu_count} available)")
            print(f"[PERF] Origins type: {type(origins)}, length: {len(origins)}")
            print(f"[PERF] Destinations type: {type(destinations)}, length: {len(destinations)}")
            
            try:
                paths = ox.routing.shortest_path(
                    self.graph, origins, destinations, weight=weight, cpus=cpus_to_use
                )
                path_calc_time = time.time() - path_calc_start
                print(f"[PERF] Parallel shortest_path took {path_calc_time:.2f}s for {len(pairs)} pairs ({path_calc_time/len(pairs)*1000:.2f}ms per route)")
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
                    print(f"Failed to calculate route {pair.origin} -> {pair.destination}: {path_error}")
                    paths.append(None)
            path_calc_time = time.time() - path_calc_start
            print(f"[PERF] Sequential shortest_path took {path_calc_time:.2f}s for {len(pairs)} pairs ({path_calc_time/len(pairs)*1000:.1f}ms per route)")

        # Build Route objects from paths
        build_start = time.time()
        routes = []
        for pair, path in zip(pairs, paths):
            if path is None:
                continue

            try:
                geometry = self._build_path_geometry(path)
                metrics = self._calculate_route_metrics(path, weight)

                route = Route(
                    origin=pair.origin,
                    destination=pair.destination,
                    path=path,
                    geometry=geometry,
                    travel_time=metrics["travel_time"],
                    distance=metrics["distance"],
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
        pairs: List[NodePair],
        edges_to_remove: List[Edge],
        weight: str = "travel_time",
    ) -> RecalculateResponse:
        """Recalculate routes after removing specified edges."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        total_start = time.time()
        print(f"[PERF] ===== Starting recalculate_with_removed_edges =====")
        print(f"[PERF] Pairs: {len(pairs)}, Edges to remove: {len(edges_to_remove)}")

        # Calculate original routes
        orig_start = time.time()
        original_routes = await self.calculate_routes(pairs, weight)
        orig_time = time.time() - orig_start
        print(f"[PERF] Original routes calculation took {orig_time:.2f}s")

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

        # Temporarily swap graphs
        original_graph = self.graph
        self.graph = G_modified

        # Calculate new routes
        new_start = time.time()
        new_routes = await self.calculate_routes(pairs, weight)
        new_time = time.time() - new_start
        print(f"[PERF] New routes calculation took {new_time:.2f}s")

        # Restore original graph
        self.graph = original_graph

        # Build comparisons
        comp_start = time.time()
        comparisons = []
        for orig, new in zip(original_routes, new_routes):
            # Check if removed edge was on original path
            removed_on_path = None
            for edge in removed:
                for i in range(len(orig.path) - 1):
                    if orig.path[i] == edge.u and orig.path[i + 1] == edge.v:
                        removed_on_path = edge
                        break
                if removed_on_path:
                    break

            comparison = RouteComparison(
                origin=orig.origin,
                destination=orig.destination,
                original_route=orig,
                new_route=new,
                removed_edge_on_path=removed_on_path,
            )
            comparisons.append(comparison)
        comp_time = time.time() - comp_start
        
        # Calculate edge usage statistics
        stats_start = time.time()
        total_routes = len(pairs)
        
        # Calculate original edge usage
        original_edge_usage = self._calculate_edge_usage_stats(original_routes, total_routes)
        
        # Build dict for delta calculation
        original_stats_dict = {
            (stat.u, stat.v): {'count': stat.count, 'frequency': stat.frequency}
            for stat in original_edge_usage
        }
        
        # Calculate new edge usage with delta
        new_edge_usage = self._calculate_edge_usage_stats(
            new_routes, total_routes, original_stats_dict
        )
        
        stats_time = time.time() - stats_start
        total_time = time.time() - total_start
        
        print(f"[PERF] Calculating edge usage stats took {stats_time:.2f}s")
        print(f"[PERF] Original: {len(original_edge_usage)} unique edges used")
        print(f"[PERF] New: {len(new_edge_usage)} unique edges used")
        print(f"[PERF] ===== Total recalculate took {total_time:.2f}s =====")

        return RecalculateResponse(
            removed_edges=removed,
            original_edge_usage=original_edge_usage,
            new_edge_usage=new_edge_usage
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
            node_lat, node_lon = node['y'], node['x']
            
            # Calculate approximate distance in km using Haversine formula
            lat_diff = node_lat - center_lat
            lon_diff = node_lon - center_lon
            
            # Approximate distance (good enough for small areas)
            lat_km = lat_diff * 111.0  # 1 degree latitude ≈ 111 km
            lon_km = lon_diff * 111.0 * 0.7  # adjusted for Lausanne's latitude
            distance_km = (lat_km**2 + lon_km**2)**0.5
            
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
            
            lat_diff = orig_node['y'] - dest_node['y']
            lon_diff = orig_node['x'] - dest_node['x']
            lat_km = lat_diff * 111.0
            lon_km = lon_diff * 111.0 * 0.7
            distance_km = (lat_km**2 + lon_km**2)**0.5
            
            # Only add pair if nodes are far enough apart
            if distance_km >= min_distance_km:
                pairs.append(NodePair(origin=origin, destination=destination))

        if len(pairs) < count:
            print(f"Warning: Only generated {len(pairs)} pairs (requested {count}). Try increasing radius or decreasing min_distance.")

        return pairs
