"""Graph service orchestrator for route calculations."""

import logging
import os
import random
import time
from pathlib import Path
from typing import List, Optional

import osmnx as ox
from app.models.route import (
    EdgeModification,
    GraphData,
    GraphEdge,
    NodePair,
    PathGeometry,
    RecalculateResponse,
    Route,
)
from app.services.co2_calculator import CO2Calculator
from app.services.graph_helpers import (
    build_edge_usage_stats,
    build_path_geometry,
    calculate_route_metrics,
    count_edge_usage,
)
from app.services.impact_calculator import compute_impact_statistics, find_affected_routes

logging.basicConfig(level=logging.INFO)
ox_logger = logging.getLogger("osmnx")
ox_logger.setLevel(logging.INFO)


class GraphService:
    """Service for managing graph and calculating routes."""

    def __init__(self, graph_path: Optional[str] = None):
        self.graph = None
        self.graph_path = graph_path
        self.route_cache = {}
        self.pairs_cache = None
        self.default_pairs = None
        self.default_routes = None

        if graph_path:
            self.load_graph(graph_path)

    def load_graph(self, graph_path: str):
        """Load graph from file and ensure required attributes."""
        path = Path(graph_path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_path}")

        self.graph = ox.load_graphml(graph_path)
        total = len(self.graph.edges)

        # Add speeds/travel times if mostly missing
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

        print(f"Loaded graph: {len(self.graph.nodes)} nodes, {total} edges")

    async def initialize_default_routes(
        self, count: int = 500, radius_km: float = 2.0, seed: int = 42
    ):
        """Generate default OD pairs and pre-calculate routes."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        self.default_pairs = self.generate_random_pairs(count=count, seed=seed, radius_km=radius_km)
        self.default_routes = await self.calculate_routes(self.default_pairs, weight="travel_time")

        pairs_key = tuple((p.origin, p.destination) for p in self.default_pairs)
        self.pairs_cache = pairs_key
        self.route_cache[pairs_key] = self.default_routes
        print(f"[STARTUP] Pre-calculated {len(self.default_routes)} routes")

    def get_graph_info(self) -> dict:
        """Get basic graph information."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")
        return {
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
            "sample_nodes": list(self.graph.nodes())[:20],
        }

    def get_edge_geometries(self, limit: Optional[int] = None) -> List[dict]:
        """Get edge geometries for visualization."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        edges = []
        for i, (u, v, data) in enumerate(self.graph.edges(data=True)):
            if limit and i >= limit:
                break

            coords = (
                [[lon, lat] for lon, lat in data["geometry"].coords]
                if "geometry" in data
                else [
                    [self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]],
                    [self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]],
                ]
            )

            name_raw = data.get("name")
            name = (
                (name_raw[0] if name_raw else None)
                if isinstance(name_raw, list)
                else (str(name_raw) if name_raw else None)
            )

            highway_raw = data.get("highway", "Unknown")
            highway = highway_raw[0] if isinstance(highway_raw, list) else highway_raw

            edges.append(
                {
                    "u": int(u),
                    "v": int(v),
                    "coordinates": coords,
                    "travel_time": data.get("travel_time"),
                    "length": data.get("length"),
                    "name": name,
                    "highway": highway,
                }
            )

        return edges

    async def calculate_routes(
        self, pairs: List[NodePair], weight: str = "travel_time", use_parallel: bool = None
    ) -> List[Route]:
        """Calculate shortest paths for given node pairs."""
        if not self.graph or not pairs:
            return []

        use_parallel = use_parallel if use_parallel is not None else len(pairs) > 100
        origins = [p.origin for p in pairs]
        destinations = [p.destination for p in pairs]

        if use_parallel:
            cpus = min(4, os.cpu_count() or 1)
            try:
                paths = ox.routing.shortest_path(
                    self.graph, origins, destinations, weight=weight, cpus=cpus
                )
            except Exception:
                use_parallel = False

        if not use_parallel:
            paths = []
            for p in pairs:
                try:
                    paths.append(
                        ox.routing.shortest_path(self.graph, p.origin, p.destination, weight=weight)
                    )
                except Exception:
                    paths.append(None)

        routes = []
        for pair, path in zip(pairs, paths):
            if path is None:
                continue
            metrics = calculate_route_metrics(self.graph, path)
            routes.append(
                Route(
                    origin=pair.origin,
                    destination=pair.destination,
                    path=path,
                    travel_time=metrics["travel_time"],
                    distance=metrics["distance"],
                    elevation_gain=metrics["elevation_gain"],
                    co2_emissions=CO2Calculator.calculate_route_co2(metrics["edges_data"]),
                )
            )

        return routes

    async def recalculate_with_modifications(
        self,
        pairs: Optional[List[NodePair]] = None,
        edge_modifications: List[EdgeModification] = None,
        weight: str = "travel_time",
    ) -> RecalculateResponse:
        """Recalculate routes after applying edge modifications (remove or change speed)."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        pairs = pairs or self.default_pairs
        if pairs is None:
            raise RuntimeError("No pairs available")
        edge_modifications = edge_modifications or []

        pairs_key = tuple((p.origin, p.destination) for p in pairs)

        # Get or calculate original routes
        if self.pairs_cache != pairs_key or pairs_key not in self.route_cache:
            original_routes = await self.calculate_routes(pairs, weight)
            self.pairs_cache = pairs_key
            self.route_cache[pairs_key] = original_routes
        else:
            original_routes = self.route_cache[pairs_key]

        modified_set = {(m.u, m.v) for m in edge_modifications}
        affected_indices = find_affected_routes(original_routes, modified_set)

        # Create modified graph and apply modifications
        G_mod = self.graph.copy()
        applied = []
        for mod in edge_modifications:
            if not G_mod.has_edge(mod.u, mod.v):
                continue
            applied.append(mod)
            if mod.action == "remove":
                G_mod.remove_edge(mod.u, mod.v)
            elif mod.action == "modify" and mod.speed_kph is not None:
                # Update speed and recalculate travel_time
                edge_data = G_mod.get_edge_data(mod.u, mod.v)
                if isinstance(edge_data, dict) and 0 in edge_data:
                    edge_data = edge_data[0]
                length = edge_data.get("length", 0)
                edge_data["speed_kph"] = mod.speed_kph
                edge_data["travel_time"] = (
                    (length / 1000) / (mod.speed_kph / 3600) if mod.speed_kph > 0 else 0
                )

        # Recalculate affected routes
        new_routes_by_index = {}
        if affected_indices:
            orig_graph = self.graph
            self.graph = G_mod
            new_routes = await self.calculate_routes([pairs[i] for i in affected_indices], weight)
            self.graph = orig_graph

            for i, idx in enumerate(affected_indices):
                if i < len(new_routes):
                    new_routes_by_index[idx] = new_routes[i]

        # Compute impact stats
        impact_stats, _ = compute_impact_statistics(
            original_routes, new_routes_by_index, affected_indices, applied
        )

        # Build complete routes list
        complete_routes = list(original_routes)
        for idx, route in new_routes_by_index.items():
            complete_routes[idx] = route

        # Edge usage stats
        original_counts = count_edge_usage(original_routes)
        original_usage = build_edge_usage_stats(self.graph, original_routes, len(pairs))
        new_usage = build_edge_usage_stats(self.graph, complete_routes, len(pairs), original_counts)

        return RecalculateResponse(
            applied_modifications=applied,
            original_edge_usage=original_usage,
            new_edge_usage=new_usage,
            impact_statistics=impact_stats,
            routes=complete_routes,
        )

    def get_graph_data(self) -> GraphData:
        """Get complete graph data for visualization."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        edges = []
        for u, v, d in self.graph.edges(data=True):
            coords = (
                [[lon, lat] for lon, lat in d["geometry"].coords]
                if "geometry" in d
                else [
                    [self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]],
                    [self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]],
                ]
            )

            name_raw = d.get("name")
            name = (
                " - ".join(str(n) for n in name_raw if n)
                if isinstance(name_raw, list)
                else (str(name_raw) if name_raw else None)
            )

            highway_raw = d.get("highway", "Unknown")
            edges.append(
                GraphEdge(
                    u=u,
                    v=v,
                    geometry=PathGeometry(coordinates=coords),
                    name=name,
                    highway=highway_raw[0] if isinstance(highway_raw, list) else highway_raw,
                    speed_kph=d.get("speed_kph"),
                    length=d.get("length"),
                    travel_time=d.get("travel_time"),
                )
            )

        return GraphData(
            edges=edges, node_count=len(self.graph.nodes), edge_count=len(self.graph.edges)
        )

    def clear_route_cache(self):
        """Clear the cached routes."""
        self.route_cache.clear()
        self.pairs_cache = None

    def generate_random_pairs(
        self, count: int = 100, seed: Optional[int] = None, radius_km: float = 2.0
    ) -> List[NodePair]:
        """Generate random OD pairs within radius from Lausanne center."""
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
