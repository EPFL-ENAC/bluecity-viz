"""Graph service for route calculations."""

import osmnx as ox
import networkx as nx
import random
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
)


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

    async def calculate_routes(
        self, pairs: List[NodePair], weight: str = "travel_time"
    ) -> List[Route]:
        """Calculate shortest paths for given node pairs."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        routes = []
        for pair in pairs:
            try:
                path = ox.routing.shortest_path(
                    self.graph, pair.origin, pair.destination, weight=weight
                )

                if path is None:
                    continue

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
                print(
                    f"Failed to calculate route {pair.origin} -> {pair.destination}: {e}"
                )
                continue

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

        # Calculate original routes
        original_routes = await self.calculate_routes(pairs, weight)

        # Create modified graph
        G_modified = self.graph.copy()
        removed = []

        for edge in edges_to_remove:
            if G_modified.has_edge(edge.u, edge.v):
                G_modified.remove_edge(edge.u, edge.v)
                removed.append(edge)

        # Temporarily swap graphs
        original_graph = self.graph
        self.graph = G_modified

        # Calculate new routes
        new_routes = await self.calculate_routes(pairs, weight)

        # Restore original graph
        self.graph = original_graph

        # Build comparisons
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

        return RecalculateResponse(comparisons=comparisons, removed_edges=removed)

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
        self, count: int = 5, seed: Optional[int] = None
    ) -> List[NodePair]:
        """Generate random origin-destination node pairs."""
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if seed is not None:
            random.seed(seed)

        nodes = list(self.graph.nodes())
        pairs = []

        for _ in range(count):
            origin, destination = random.sample(nodes, 2)
            pairs.append(NodePair(origin=origin, destination=destination))

        return pairs
