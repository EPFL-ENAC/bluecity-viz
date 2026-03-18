"""CVRP service for waste collection route optimization."""

import asyncio
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import geopandas as gpd
import igraph as ig
import networkx as nx
import osmnx as ox
import pandas as pd
import pyvrp
import pyvrp.stop
from shapely import wkt
from shapely.geometry import Point, Polygon

from app.models.cvrp import CVRPEdgeLoad, CVRPRequest, CVRPRouteSegment, CVRPSolveResponse
from app.services.graph_helpers import apply_edge_modifications

if TYPE_CHECKING:
    from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

# Lausanne bounding polygon
LAUSANNE_HULL_WKT = (
    "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
    "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
    "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
    "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
    "6.7016307 46.4999401, 6.6973149 46.4991489))"
)

# Depot location (city centre)
DEPOT_LON = 6.597982
DEPOT_LAT = 46.527867


# ---------------------------------------------------------------------------
# Graph utilities (extracted from notebook)
# ---------------------------------------------------------------------------


def _networkx_to_igraph_with_indices(
    g: nx.MultiDiGraph,
) -> Tuple[ig.Graph, Dict[str, dict]]:
    """Convert networkx graph to igraph with bidirectional index mappings."""
    e = ox.graph_to_gdfs(g, nodes=False, edges=True)
    nx.set_edge_attributes(g, {idx: idx for idx in e.index}, name="nx_edge_id")
    h = ig.Graph.from_networkx(g)

    idx_maps = {
        "node_nx_to_ig": {a: b for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "node_ig_to_nx": {b: a for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "edge_nx_to_ig": {a: b for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
        "edge_ig_to_nx": {b: a for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
    }

    return h, idx_maps


# ---------------------------------------------------------------------------
# Data preparation (extracted from notebook)
# ---------------------------------------------------------------------------


def _process_centroids(
    graph: nx.MultiDiGraph,
    idx_maps: dict,
    centroid_csv: str,
    waste_per_centroid: int = 10,
    max_centroids: Optional[int] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Process waste centroids and map to nearest graph nodes.

    Args:
        graph: NetworkX MultiDiGraph
        idx_maps: Index mappings from _networkx_to_igraph_with_indices
        centroid_csv: Path to centroid CSV file
        waste_per_centroid: Waste per centroid in kg
        max_centroids: If set, subsample to at most this many rows before snapping
        seed: Random seed for subsampling

    Returns:
        DataFrame with columns: node, centroid_waste, x, y, node_ig
    """
    df = pd.read_csv(centroid_csv)

    gdf = gpd.GeoDataFrame(
        df,
        geometry=df.apply(
            lambda row: Point(row["centroid_lon"], row["centroid_lat"]), axis=1
        ),
    )
    hull: Polygon = wkt.loads(LAUSANNE_HULL_WKT)
    filtered_gdf = gdf[gdf["geometry"].apply(lambda geom: geom.within(hull))].copy()

    # Subsample before snapping (snapping is expensive for large datasets)
    if max_centroids is not None and len(filtered_gdf) > max_centroids:
        filtered_gdf = filtered_gdf.sample(n=max_centroids, random_state=seed)

    filtered_gdf["node"] = ox.distance.nearest_nodes(
        graph,
        filtered_gdf["centroid_lon"],
        filtered_gdf["centroid_lat"],
    )
    filtered_gdf["centroid_waste"] = waste_per_centroid

    node_df = filtered_gdf.groupby("node")["centroid_waste"].sum().reset_index()
    node_df["x"] = node_df["node"].map(lambda n: graph.nodes[n]["x"])
    node_df["y"] = node_df["node"].map(lambda n: graph.nodes[n]["y"])
    node_df["node_ig"] = node_df["node"].map(lambda n: idx_maps["node_nx_to_ig"][n])

    return node_df


def _add_depot(
    node_df: pd.DataFrame,
    graph: nx.MultiDiGraph,
    idx_maps: dict,
    center_lon: float = DEPOT_LON,
    center_lat: float = DEPOT_LAT,
) -> Tuple[pd.DataFrame, int]:
    """Add depot location to node DataFrame."""
    depot_node_nx = ox.distance.nearest_nodes(graph, center_lon, center_lat)
    depot_node_ig = idx_maps["node_nx_to_ig"][depot_node_nx]

    node_df = node_df.copy()
    node_df["isdepot"] = False

    if depot_node_nx in node_df["node"].values:
        node_df.loc[node_df["node"] == depot_node_nx, "centroid_waste"] = 0
        node_df.loc[node_df["node"] == depot_node_nx, "isdepot"] = True
    else:
        depot_df = pd.DataFrame(
            {
                "node": [depot_node_nx],
                "node_ig": [depot_node_ig],
                "centroid_waste": [0],
                "x": [graph.nodes()[depot_node_nx]["x"]],
                "y": [graph.nodes()[depot_node_nx]["y"]],
                "isdepot": [True],
            }
        )
        node_df = pd.concat([depot_df, node_df], ignore_index=True)

    return node_df, depot_node_ig


# ---------------------------------------------------------------------------
# CVRP model creation & solving (extracted from notebook)
# ---------------------------------------------------------------------------


def _create_distance_matrix(
    g_ig: ig.Graph,
    node_df: pd.DataFrame,
) -> Tuple[List, List]:
    """Create origin-destination distance matrix."""
    unique_ig_nodes = list(set(node_df["node_ig"].tolist()))
    od_distance = g_ig.distances(unique_ig_nodes, unique_ig_nodes, weights="length")

    inaccessible_indices = [
        i for i, dist in enumerate(od_distance[0]) if dist == float("inf")
    ]

    return od_distance, inaccessible_indices


def _create_cvrp_model(
    node_df: pd.DataFrame,
    inaccessible_indices: List,
    od_distance: List,
    n_vehicles: int = 15,
    vehicle_capacity: int = 5000,
) -> pyvrp.Model:
    """Create PyVRP model."""
    m = pyvrp.Model()

    depot = m.add_depot(
        x=node_df.loc[node_df["isdepot"], "x"].values[0],
        y=node_df.loc[node_df["isdepot"], "y"].values[0],
    )

    regular = m.add_profile(name="regular")
    m.add_vehicle_type(
        n_vehicles,
        capacity=vehicle_capacity,
        reload_depots=[depot],
        max_reloads=10,
        profile=regular,
    )

    for _, row in node_df.iterrows():
        if not row["isdepot"]:
            required = row["node_ig"] not in inaccessible_indices
            m.add_client(
                x=row["x"],
                y=row["y"],
                delivery=int(row["centroid_waste"]),
                required=required,
            )

    for frm_idx, frm in enumerate(m.locations):
        for to_idx, to in enumerate(m.locations):
            duration = od_distance[frm_idx][to_idx]
            if duration == float("inf"):
                duration = 999999
            m.add_edge(frm, to, distance=duration)

    return m


def _solve_cvrp(
    model: pyvrp.Model,
    max_runtime: int = 5,
    no_improvement_iterations: int = 100,
    seed: int = 42,
) -> pyvrp.Result:
    """Solve CVRP model."""
    stop_criteria = pyvrp.stop.MultipleCriteria(
        [
            pyvrp.stop.MaxRuntime(max_runtime),
            pyvrp.stop.NoImprovement(no_improvement_iterations),
        ]
    )
    return model.solve(stop=stop_criteria, seed=seed)


# ---------------------------------------------------------------------------
# Route processing & analysis (extracted from notebook)
# ---------------------------------------------------------------------------


def _extract_routes_with_depots(solution: pyvrp.Solution) -> List[Dict]:
    """Extract routes from solution with explicit depot visits."""
    routes = solution.routes()
    result = []

    for route_id, route in enumerate(routes):
        trips_data = []
        total_distance = 0
        total_delivery = 0

        for trip_id, trip in enumerate(route.trips()):
            sequence = [trip.start_depot()] + list(trip.visits()) + [trip.end_depot()]
            trip_distance = trip.distance()
            trip_delivery = trip.delivery()[0]

            total_distance += trip_distance
            total_delivery += trip_delivery

            trips_data.append(
                {
                    "trip_id": trip_id,
                    "sequence": sequence,
                    "distance": trip_distance,
                    "delivery": trip_delivery,
                    "start_depot": trip.start_depot(),
                    "end_depot": trip.end_depot(),
                    "is_reload": trip_id > 0,
                }
            )

        result.append(
            {
                "route_id": route_id,
                "vehicle_id": route_id,
                "total_distance": total_distance,
                "total_delivery": total_delivery,
                "n_trips": len(trips_data),
                "trips": trips_data,
            }
        )

    return result


def _calculate_load_progression(routes: List[Dict], node_df: pd.DataFrame) -> List[Dict]:
    """Calculate cumulative load after pickup at each client location."""
    demands = {0: 0}
    client_idx = 1
    for _, row in node_df.iterrows():
        if not row.get("isdepot", False):
            demands[client_idx] = row["centroid_waste"]
            client_idx += 1

    result = []
    for route in routes:
        for trip in route["trips"]:
            sequence = trip["sequence"]
            progression = []
            cumulative_load = 0

            for loc_idx in sequence:
                if loc_idx == 0 and len(progression) > 0:
                    cumulative_load = 0
                elif loc_idx != 0:
                    cumulative_load += demands.get(loc_idx, 0)
                progression.append(
                    {"location_idx": loc_idx, "cumulative_load": cumulative_load}
                )

            result.append(
                {
                    "route_id": route["route_id"],
                    "trip_id": trip["trip_id"],
                    "progression": progression,
                }
            )

    return result


def _route_on_graph(
    routes: List[Dict],
    g_ig: ig.Graph,
    node_df: pd.DataFrame,
    idx_maps: Dict,
) -> Dict:
    """Route each trip segment on the actual street network."""
    loc_to_ig = [node_df.loc[node_df["isdepot"], "node_ig"].values[0]]
    for _, row in node_df.iterrows():
        if not row.get("isdepot", False):
            loc_to_ig.append(row["node_ig"])

    ig_to_nx = idx_maps["node_ig_to_nx"]
    graph_paths = []
    total_segments = 0
    successful = 0
    failed = 0
    failed_segments = []

    for route in routes:
        route_id = route["route_id"]
        for trip in route["trips"]:
            trip_id = trip["trip_id"]
            sequence = trip["sequence"]

            for segment_id in range(len(sequence) - 1):
                from_loc = sequence[segment_id]
                to_loc = sequence[segment_id + 1]
                total_segments += 1

                try:
                    from_ig = loc_to_ig[from_loc]
                    to_ig = loc_to_ig[to_loc]

                    path_ig = g_ig.get_shortest_paths(
                        from_ig, to=to_ig, weights="length", output="vpath"
                    )[0]

                    if len(path_ig) == 0:
                        logger.warning(
                            "Route %d, Trip %d, Segment %d: no path from %d to %d",
                            route_id,
                            trip_id,
                            segment_id,
                            from_loc,
                            to_loc,
                        )
                        failed += 1
                        failed_segments.append((route_id, trip_id, from_loc, to_loc))
                        graph_paths.append(
                            {
                                "route_id": route_id,
                                "trip_id": trip_id,
                                "segment_id": segment_id,
                                "from_loc": from_loc,
                                "to_loc": to_loc,
                                "path_ig": [],
                                "path_nx": [],
                                "path_length": None,
                                "success": False,
                            }
                        )
                    else:
                        path_nx = [ig_to_nx[n] for n in path_ig]
                        path_length = g_ig.distances(
                            [from_ig], [to_ig], weights="length"
                        )[0][0]
                        successful += 1
                        graph_paths.append(
                            {
                                "route_id": route_id,
                                "trip_id": trip_id,
                                "segment_id": segment_id,
                                "from_loc": from_loc,
                                "to_loc": to_loc,
                                "path_ig": path_ig,
                                "path_nx": path_nx,
                                "path_length": path_length,
                                "success": True,
                            }
                        )
                except Exception as exc:
                    logger.error(
                        "Route %d, Trip %d, Segment %d: error routing %d->%d: %s",
                        route_id,
                        trip_id,
                        segment_id,
                        from_loc,
                        to_loc,
                        exc,
                    )
                    failed += 1
                    failed_segments.append((route_id, trip_id, from_loc, to_loc))
                    graph_paths.append(
                        {
                            "route_id": route_id,
                            "trip_id": trip_id,
                            "segment_id": segment_id,
                            "from_loc": from_loc,
                            "to_loc": to_loc,
                            "path_ig": [],
                            "path_nx": [],
                            "path_length": None,
                            "success": False,
                        }
                    )

    return {
        "routes": routes,
        "graph_paths": graph_paths,
        "routing_stats": {
            "total_segments": total_segments,
            "successful": successful,
            "failed": failed,
            "failed_segments": failed_segments,
        },
    }


def _calculate_edge_loads(
    routing_result: Dict,
    load_progression: List[Dict],
    graph: nx.MultiDiGraph,
    unit: str = "kg",
) -> Dict:
    """Calculate total load passing through each edge."""
    edge_loads: dict = defaultdict(float)

    segment_loads = {}
    for lp in load_progression:
        route_id = lp["route_id"]
        trip_id = lp["trip_id"]
        for i in range(len(lp["progression"]) - 1):
            load = lp["progression"][i]["cumulative_load"]
            segment_loads[(route_id, trip_id, i)] = load

    for gp in routing_result["graph_paths"]:
        if not gp["success"]:
            continue

        route_id = gp["route_id"]
        trip_id = gp["trip_id"]
        segment_id = gp["segment_id"]
        path_nx = gp["path_nx"]
        load = segment_loads.get((route_id, trip_id, segment_id), 0)

        for i in range(len(path_nx) - 1):
            u = path_nx[i]
            v = path_nx[i + 1]

            if graph.has_edge(u, v):
                edge_data = graph.get_edge_data(u, v)
                if len(edge_data) == 1:
                    key = list(edge_data.keys())[0]
                else:
                    key = min(
                        edge_data.keys(),
                        key=lambda k: edge_data[k].get("length", float("inf")),
                    )
                if unit == "kg":
                    edge_loads[(u, v, key)] += load
                elif unit == "kg_m":
                    length = edge_data[key].get("length", 0)
                    edge_loads[(u, v, key)] += load * length
            elif graph.has_edge(v, u):
                edge_data = graph.get_edge_data(v, u)
                if len(edge_data) == 1:
                    key = list(edge_data.keys())[0]
                else:
                    key = min(
                        edge_data.keys(),
                        key=lambda k: edge_data[k].get("length", float("inf")),
                    )
                if unit == "kg":
                    edge_loads[(v, u, key)] += load
                elif unit == "kg_m":
                    length = edge_data[key].get("length", 0)
                    edge_loads[(v, u, key)] += load * length

    max_load = max(edge_loads.values(), default=0)
    return {
        "edge_loads": dict(edge_loads),
        "max_load": max_load,
        "unit": unit,
        "n_edges_used": len(edge_loads),
    }


# ---------------------------------------------------------------------------
# CVRPService class
# ---------------------------------------------------------------------------


class CVRPService:
    """Orchestrates CVRP solving for waste collection routing."""

    # Maps waste_type -> raw centroid CSV path (set at initialize time)
    _csv_paths: Dict[str, str]
    # Maps waste_type -> pre-snapped node_df (client nodes only, no depot)
    _node_dfs: Dict[str, pd.DataFrame]
    _graph_service: Optional["GraphService"]

    WASTE_TYPES = ("DI", "DV", "PC", "VE")

    def __init__(self) -> None:
        self._csv_paths = {}
        self._node_dfs = {}
        self._graph_service = None

    def set_graph_service(self, graph_service: "GraphService") -> None:
        self._graph_service = graph_service

    def initialize(self, centroids_dir: str) -> None:
        """Load and snap centroids for all waste types found in centroids_dir."""
        if self._graph_service is None or self._graph_service.graph is None:
            logger.warning("CVRPService.initialize() called before graph was loaded — skipping")
            return

        graph = self._graph_service.graph
        centroids_path = Path(centroids_dir)

        if not centroids_path.exists():
            logger.warning("Centroids directory not found: %s", centroids_dir)
            return

        # Build igraph + index maps (used for snapping)
        _, idx_maps = _networkx_to_igraph_with_indices(graph)

        loaded = 0
        for waste_type in self.WASTE_TYPES:
            csv_file = centroids_path / f"{waste_type}_final_clustered_centroids.csv"
            if not csv_file.exists():
                logger.warning("Centroid CSV not found: %s", csv_file)
                continue

            try:
                logger.info("Snapping centroids for waste type %s …", waste_type)
                # Snap all centroids; waste_per_centroid=1 so centroid_waste = count per node
                node_df = _process_centroids(
                    graph,
                    idx_maps,
                    str(csv_file),
                    waste_per_centroid=1,
                    max_centroids=None,
                )
                self._csv_paths[waste_type] = str(csv_file)
                self._node_dfs[waste_type] = node_df
                loaded += 1
                logger.info(
                    "Loaded %d client nodes for waste type %s", len(node_df), waste_type
                )
            except Exception as exc:
                logger.error("Failed to load centroids for %s: %s", waste_type, exc)

        logger.info("CVRPService initialized with %d waste types", loaded)

    def is_ready(self, waste_type: str) -> bool:
        return waste_type in self._node_dfs

    def get_centroids_geojson(self, waste_type: str) -> dict:
        """Return pre-snapped centroids as GeoJSON FeatureCollection."""
        if waste_type not in self._node_dfs:
            return {"type": "FeatureCollection", "features": []}

        node_df = self._node_dfs[waste_type]
        features = []
        for _, row in node_df.iterrows():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["x"], row["y"]]},
                    "properties": {
                        "node": int(row["node"]),
                        "centroid_waste": float(row["centroid_waste"]),
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    async def solve(self, request: CVRPRequest) -> CVRPSolveResponse:
        """Solve CVRP for waste collection.

        Applies edge modifications to a copy of the graph, then runs the full
        CVRP pipeline (distance matrix, model, solve, routing) in a thread pool.
        """
        if self._graph_service is None or self._graph_service.graph is None:
            raise RuntimeError("Graph not loaded")

        waste_type = request.waste_type
        if waste_type not in self._node_dfs:
            raise ValueError(
                f"Waste type '{waste_type}' not available. "
                f"Available: {list(self._node_dfs.keys())}"
            )

        t_start = time.perf_counter()

        # Copy graph and apply edge modifications (pass empty caches — we discard the copy)
        graph_copy = self._graph_service.graph.copy()
        if request.edge_modifications:
            apply_edge_modifications(graph_copy, {}, {}, request.edge_modifications)

        # Use all pre-snapped centroids (base centroid_waste is count of centroids per node)
        node_df = self._node_dfs[waste_type].copy()
        node_df["centroid_waste"] = (
            node_df["centroid_waste"] * request.waste_per_centroid
        ).astype(int)
        # Ensure minimum of 1
        node_df.loc[node_df["centroid_waste"] < 1, "centroid_waste"] = 1

        centroids_used = len(node_df)

        # Run heavy computation in thread pool
        result = await asyncio.to_thread(
            self._solve_sync,
            graph_copy,
            node_df,
            request,
        )

        t_elapsed_ms = (time.perf_counter() - t_start) * 1000
        result["solve_time_ms"] = t_elapsed_ms
        result["centroids_used"] = centroids_used

        return CVRPSolveResponse(**result)

    def _solve_sync(
        self,
        graph: nx.MultiDiGraph,
        node_df: pd.DataFrame,
        request: CVRPRequest,
    ) -> dict:
        """Synchronous CVRP solve pipeline (runs in thread pool)."""
        # Build igraph from (possibly modified) graph
        g_ig, idx_maps = _networkx_to_igraph_with_indices(graph)

        # Re-snap client nodes to the (possibly modified) graph
        # We can reuse existing node mappings since we only change edge weights/removal
        # but nodes remain the same — just update node_ig from the new idx_maps
        node_df = node_df.copy()
        node_df["node_ig"] = node_df["node"].map(
            lambda n: idx_maps["node_nx_to_ig"].get(n, -1)
        )
        # Remove nodes that couldn't be mapped (shouldn't happen, but be safe)
        node_df = node_df[node_df["node_ig"] >= 0].copy()

        # Add depot
        node_df, _depot_ig = _add_depot(node_df, graph, idx_maps)

        # Create distance matrix
        od_distance, inaccessible_indices = _create_distance_matrix(g_ig, node_df)

        # Create and solve CVRP model
        model = _create_cvrp_model(
            node_df,
            inaccessible_indices,
            od_distance,
            n_vehicles=request.n_vehicles,
            vehicle_capacity=request.vehicle_capacity,
        )
        pyvrp_result = _solve_cvrp(model, max_runtime=request.max_runtime)
        solution = pyvrp_result.best

        n_routes = solution.num_routes()
        n_missing = solution.num_missing_clients()
        total_dist = float(solution.distance())

        # Extract routes
        routes = _extract_routes_with_depots(solution)
        load_progression = _calculate_load_progression(routes, node_df)
        routing_result = _route_on_graph(routes, g_ig, node_df, idx_maps)
        edge_loads_result = _calculate_edge_loads(
            routing_result, load_progression, graph, unit=request.load_unit
        )

        # Build route_segments for API response
        route_segments = self._build_route_segments(
            routing_result, load_progression, graph
        )

        # Build edge_loads list for API response
        edge_loads = [
            CVRPEdgeLoad(u=int(u), v=int(v), load=float(load))
            for (u, v, _key), load in edge_loads_result["edge_loads"].items()
        ]

        return {
            "n_routes": n_routes,
            "n_missing_clients": n_missing,
            "total_distance_m": total_dist,
            "route_segments": route_segments,
            "edge_loads": edge_loads,
            "load_unit": request.load_unit,
            "solve_time_ms": 0.0,  # filled in by caller
            "centroids_used": 0,  # filled in by caller
        }

    @staticmethod
    def _get_edge_geometry_coords(
        graph: nx.MultiDiGraph, u: int, v: int
    ) -> list:
        """Return coordinate list for edge (u, v), using Shapely geometry if available."""
        edge_data = graph.get_edge_data(u, v)
        if edge_data is None:
            return [[graph.nodes[u]["x"], graph.nodes[u]["y"]],
                    [graph.nodes[v]["x"], graph.nodes[v]["y"]]]
        key = min(edge_data.keys())
        geom = edge_data[key].get("geometry")
        if geom is not None and hasattr(geom, "coords"):
            return [[lon, lat] for lon, lat in geom.coords]
        return [[graph.nodes[u]["x"], graph.nodes[u]["y"]],
                [graph.nodes[v]["x"], graph.nodes[v]["y"]]]

    @staticmethod
    def _build_route_segments(
        routing_result: dict,
        load_progression: List[Dict],
        graph: nx.MultiDiGraph,
    ) -> List[CVRPRouteSegment]:
        """Convert routing result into API-ready route segments."""
        # Build segment load lookup
        segment_loads: dict = {}
        for lp in load_progression:
            route_id = lp["route_id"]
            trip_id = lp["trip_id"]
            for i in range(len(lp["progression"]) - 1):
                load = lp["progression"][i]["cumulative_load"]
                segment_loads[(route_id, trip_id, i)] = load

        segments: List[CVRPRouteSegment] = []
        for gp in routing_result["graph_paths"]:
            if not gp["success"] or not gp["path_nx"]:
                continue

            path_nx = gp["path_nx"]
            # Chain edge geometries (Shapely LineString coords) instead of just node coords
            coords: list = []
            for i in range(len(path_nx) - 1):
                u, v = path_nx[i], path_nx[i + 1]
                edge_coords = CVRPService._get_edge_geometry_coords(graph, u, v)
                coords.extend(edge_coords if i == 0 else edge_coords[1:])

            load = segment_loads.get(
                (gp["route_id"], gp["trip_id"], gp["segment_id"]), 0.0
            )
            segments.append(
                CVRPRouteSegment(
                    route_id=gp["route_id"],
                    trip_id=gp["trip_id"],
                    path_coordinates=coords,
                    load_kg=float(load),
                )
            )

        return segments
