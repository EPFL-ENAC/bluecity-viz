"""Graph service orchestrator for route calculations."""

import logging
import random
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
  calculate_route_metrics,
  count_edge_usage,
)
from app.services.impact_calculator import (
  compute_impact_statistics,
  find_affected_routes,
)

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
        self,
        count: int = 500,
        radius_km: float = 2.0,
        seed: int = 42,
        sampling_method: str = "research",
        sampling_config=None,
    ):
        """Generate default OD pairs and pre-calculate routes.

        Args:
            count: Number of OD pairs to generate
            radius_km: Radius for simple sampling (ignored if method='research')
            seed: Random seed for reproducibility
            sampling_method: 'simple' or 'research' (default: 'research')
            sampling_config: SamplingConfig for research-based sampling (uses defaults if None)
        """
        if not self.graph:
            raise RuntimeError("Graph not loaded")

        if sampling_method == "research":
            from app.services.node_sampling_service import (
              SamplingConfig,
              generate_research_based_pairs,
            )

            config = sampling_config or SamplingConfig()
            print(f"[STARTUP] Using research-based sampling with {count} OD pairs")
            self.default_pairs = generate_research_based_pairs(
                self.graph, n_pairs=count, config=config, seed=seed
            )
        else:
            print(f"[STARTUP] Using simple random sampling with {count} OD pairs")
            self.default_pairs = self.generate_random_pairs(
                count=count, seed=seed, radius_km=radius_km
            )

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
                    "speed_kph": data.get("speed_kph"),
                    "name": name,
                    "highway": highway,
                }
            )

        return edges

    def _group_pairs_by_origin(self, pairs: List[NodePair]) -> dict:
        """Group OD pairs by origin for one-to-many routing.

        Args:
            pairs: List of origin-destination pairs

        Returns:
            Dict mapping origin → list of (destination, pair_object) tuples
        """
        from collections import defaultdict

        origin_groups = defaultdict(list)
        for pair in pairs:
            origin_groups[pair.origin].append((pair.destination, pair))

        return origin_groups

    async def _calculate_routes_igraph(
        self, origin_groups: dict, weight: str = "travel_time"
    ) -> List[Route]:
        """Calculate routes using igraph one-to-many shortest paths.

        Args:
            origin_groups: Dict mapping origin → [(destination, pair_object), ...]
            weight: Edge weight attribute

        Returns:
            List of Route objects (order not preserved)
        """
        import logging
        import time

        from app.services.node_sampling_service import (
          networkx_to_igraph_with_indices,
        )

        logger = logging.getLogger(__name__)

        # Convert NetworkX graph to igraph with index mappings
        t0 = time.time()
        h, idx_maps = networkx_to_igraph_with_indices(self.graph)
        t1 = time.time()
        logger.info(f"Graph conversion took {t1-t0:.2f}s")

        # Copy weight attribute from NetworkX to igraph
        if weight not in h.es.attributes():
            logger.info(f"Copying weight attribute '{weight}' to igraph...")
            edge_weights = []
            for edge_ig_idx in h.get_edgelist():
                edge_nx_idx = idx_maps["edge_ig_to_nx"][edge_ig_idx]
                edge_data = self.graph.edges[edge_nx_idx]
                edge_weights.append(edge_data.get(weight, edge_data.get("length", 1)))
            h.es[weight] = edge_weights

        all_routes = []
        failed_origins = 0

        t2 = time.time()
        logger.info(f"Calculating routes for {len(origin_groups)} origins...")
        t2_routing = 0

        for origin_nx, dest_pairs in origin_groups.items():
            # Convert origin from NetworkX ID to igraph index
            if origin_nx not in idx_maps["node_nx_to_ig"]:
                logger.warning(f"Origin {origin_nx} not found in igraph")
                failed_origins += 1
                continue

            origin_ig = idx_maps["node_nx_to_ig"][origin_nx]

            # Convert destinations from NetworkX IDs to igraph indices
            destinations_ig = []
            dest_pair_mapping = []  # Track which pair corresponds to which destination

            for dest_nx, pair_obj in dest_pairs:
                if dest_nx in idx_maps["node_nx_to_ig"]:
                    destinations_ig.append(idx_maps["node_nx_to_ig"][dest_nx])
                    dest_pair_mapping.append((dest_nx, pair_obj))

            if not destinations_ig:
                logger.warning(f"No valid destinations for origin {origin_nx}")
                failed_origins += 1
                continue

            try:
                # ONE DIJKSTRA CALL FOR ALL DESTINATIONS FROM THIS ORIGIN
                t2a = time.time()
                paths_ig = h.get_shortest_paths(
                    v=origin_ig, to=destinations_ig, weights=weight, output="vpath"
                )
                t2b = time.time()
                t2_routing += t2b - t2a

                # Process each path
                for path_ig, (dest_nx, pair_obj) in zip(paths_ig, dest_pair_mapping):
                    if not path_ig or len(path_ig) < 2:
                        # No path found (disconnected)
                        continue

                    # Convert path from igraph indices to NetworkX node IDs
                    path_nx = [idx_maps["node_ig_to_nx"][node_ig] for node_ig in path_ig]

                    # Calculate metrics using NetworkX graph (existing helper)
                    metrics = calculate_route_metrics(self.graph, path_nx)

                    # Build Route object
                    all_routes.append(
                        Route(
                            origin=pair_obj.origin,
                            destination=pair_obj.destination,
                            path=path_nx,
                            travel_time=metrics["travel_time"],
                            distance=metrics["distance"],
                            elevation_gain=metrics["elevation_gain"],
                            co2_emissions=CO2Calculator.calculate_route_co2(metrics["edges_data"]),
                        )
                    )

            except Exception as e:
                logger.warning(f"Failed to route from origin {origin_nx}: {e}")
                failed_origins += 1
                continue

        t3 = time.time()
        routing_time = t3 - t2
        logger.info(f"Total routing time: {routing_time:.2f}s")
        logger.info(f"Total routing time (igraph): {t2_routing:.2f}s")

        if failed_origins > 0:
            logger.warning(f"Failed to route from {failed_origins} origins")

        logger.info(
            f"Successfully calculated {len(all_routes)} routes in {routing_time:.2f}s "
            f"({len(all_routes)/routing_time:.0f} routes/sec)"
        )
        return all_routes

    async def calculate_routes(
        self, pairs: List[NodePair], weight: str = "travel_time", use_parallel: bool = None
    ) -> List[Route]:
        """Calculate shortest paths for given node pairs using igraph one-to-many routing.

        Args:
            pairs: List of origin-destination node pairs
            weight: Edge weight attribute to minimize
            use_parallel: Deprecated, kept for API compatibility (ignored)

        Returns:
            List of Route objects with paths and metrics

        Note:
            Uses igraph one-to-many shortest paths for efficiency.
            Result order may differ from input pair order.
        """
        if not self.graph or not pairs:
            return []

        import logging

        logger = logging.getLogger(__name__)

        # Group pairs by origin for one-to-many optimization
        origin_groups = self._group_pairs_by_origin(pairs)

        avg_dests_per_origin = len(pairs) / len(origin_groups)
        logger.info(
            f"[ROUTING] {len(pairs)} OD pairs grouped into {len(origin_groups)} origins "
            f"(avg {avg_dests_per_origin:.1f} destinations/origin)"
        )

        # Use igraph one-to-many routing
        routes = await self._calculate_routes_igraph(origin_groups, weight)

        logger.info(f"[ROUTING] Calculated {len(routes)} routes successfully")
        return routes

    async def recalculate_with_modifications(
        self,
        pairs: Optional[List[NodePair]] = None,
        edge_modifications: List[EdgeModification] = None,
        weight: str = "travel_time",
        resample_od_pairs: bool = False,
        sampling_config=None,
    ) -> RecalculateResponse:
        """Recalculate routes after applying edge modifications (remove or change speed).

        Args:
            pairs: OD pairs to use (uses default if None)
            edge_modifications: List of edge modifications
            weight: Edge weight attribute to use
            resample_od_pairs: If True, resample OD pairs after mods instead of rerouting
            sampling_config: SamplingConfig for OD resampling (uses defaults if None)
        """
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

        # Create modified graph and apply only effective modifications
        G_mod = self.graph.copy()
        applied = []
        effective_modified_set = set()  # Only edges that actually change

        for mod in edge_modifications:
            if not G_mod.has_edge(mod.u, mod.v):
                continue

            if mod.action == "remove":
                G_mod.remove_edge(mod.u, mod.v)
                applied.append(mod)
                effective_modified_set.add((mod.u, mod.v))

            elif mod.action == "modify" and mod.speed_kph is not None:
                # Check if speed actually changes before applying
                edge_data = G_mod.get_edge_data(mod.u, mod.v)
                if isinstance(edge_data, dict) and 0 in edge_data:
                    edge_data = edge_data[0]

                current_speed = edge_data.get("speed_kph", 0)
                # Skip if speed is already the same (within tolerance)
                if abs(current_speed - mod.speed_kph) < 0.1:
                    continue

                # Apply the modification
                length = edge_data.get("length", 0)
                edge_data["speed_kph"] = mod.speed_kph
                edge_data["travel_time"] = (
                    (length / 1000) / (mod.speed_kph / 3600) if mod.speed_kph > 0 else 0
                )
                applied.append(mod)
                effective_modified_set.add((mod.u, mod.v))

        # NEW: Resample OD pairs if requested
        if resample_od_pairs:
            from app.services.node_sampling_service import (
              SamplingConfig,
              generate_research_based_pairs,
            )

            config = sampling_config or SamplingConfig()

            print(f"[RESAMPLE] Generating new OD pairs using modified graph (n={len(pairs)})")
            # Generate new OD pairs using modified graph
            new_pairs = generate_research_based_pairs(
                G_mod, n_pairs=len(pairs), config=config, seed=42
            )

            # Recalculate ALL routes with new OD pairs
            orig_graph = self.graph
            self.graph = G_mod
            new_routes = await self.calculate_routes(new_pairs, weight)
            self.graph = orig_graph

            # All routes are "affected" since we resampled
            affected_indices = list(range(len(new_routes)))
            new_routes_by_index = {i: route for i, route in enumerate(new_routes)}

        else:
            # Existing logic: find affected routes and reroute
            affected_indices = find_affected_routes(original_routes, effective_modified_set)

            # Recalculate affected routes
            new_routes_by_index = {}
            if affected_indices:
                orig_graph = self.graph
                self.graph = G_mod
                new_routes = await self.calculate_routes(
                    [pairs[i] for i in affected_indices], weight
                )
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
