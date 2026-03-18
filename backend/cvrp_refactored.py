# %% [markdown]
# # CVRP Solver - Refactored with Enhanced Features
#
# This notebook contains a well-structured implementation of the CVRP solver with:
# - Clean, reusable functions
# - Route extraction with depot movements
# - Load progression calculation
# - Graph-based route trajectory computation
# - Edge load aggregation for infrastructure analysis
#

import logging
import random
from collections import defaultdict
from typing import Dict, List, Tuple

import geopandas as gpd
import igraph as ig
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd

# %%
import pyvrp
import pyvrp.plotting
import pyvrp.stop
from shapely import wkt
from shapely.geometry import Point, Polygon

# %% [markdown]
# ## Section 1: Graph Utilities
#
# Functions for graph conversion and manipulation.
#


# %%
def networkx_to_igraph_with_indices(
    g: nx.MultiDiGraph,
) -> Tuple[ig.Graph, Dict[str, dict]]:
    """Convert networkx graph to igraph with bidirectional index mappings.

    Args:
        g: NetworkX MultiDiGraph

    Returns:
        Tuple of (igraph Graph, index mappings dict)
        Index mappings contain: node_nx_to_ig, node_ig_to_nx, edge_nx_to_ig, edge_ig_to_nx
    """
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


# %%
def nx_to_ig(graph: nx.MultiDiGraph) -> ig.Graph:
    """Simple NetworkX to igraph conversion.

    Args:
        graph: NetworkX MultiDiGraph

    Returns:
        igraph Graph
    """
    e = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    nx.set_edge_attributes(graph, {idx: idx for idx in e.index}, name="nx_edge_id")
    g_ig = ig.Graph.from_networkx(graph)
    return g_ig


# %%
def get_intersection_nodes(graph: nx.MultiDiGraph) -> Tuple[pd.DataFrame, List, Dict]:
    """Get nodes with street_count >= 3 (intersections).

    Args:
        graph: NetworkX MultiDiGraph

    Returns:
        Tuple of (nodes DataFrame, igraph node indices, index mappings)
    """
    h, idx_maps = networkx_to_igraph_with_indices(graph)
    nodes = ox.graph_to_gdfs(graph, nodes=True, edges=False)
    nodes = nodes.loc[(nodes["street_count"] >= 3)]
    nodes_ig = [idx_maps["node_nx_to_ig"][idx] for idx in nodes.index]

    return nodes, nodes_ig, idx_maps


# %% [markdown]
# ## Section 2: Data Preparation
#
# Functions for loading and preparing waste collection data.
#

# %%
# Constants
LAUSANNE_HULL_WKT = (
    "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
    "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
    "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
    "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
    "6.7016307 46.4999401, 6.6973149 46.4991489))"
)


# %%
def process_centroids(
    graph: nx.MultiDiGraph,
    idx_maps: dict,
    waste_per_centroid: int = 10,
    centroid_csv: str = "data/DI_final_clustered_centroids.csv",
) -> pd.DataFrame:
    """Process waste centroids and map to nearest graph nodes.

    Args:
        graph: NetworkX MultiDiGraph
        idx_maps: Index mapping dictionary from networkx_to_igraph_with_indices
        waste_per_centroid: Weight of waste per centroid in kg
        centroid_csv: Path to centroid CSV file

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
    filtered_gdf["node"] = ox.distance.nearest_nodes(
        graph, filtered_gdf["centroid_lon"], filtered_gdf["centroid_lat"]
    )
    filtered_gdf["centroid_waste"] = waste_per_centroid

    node_df = filtered_gdf.groupby("node")["centroid_waste"].sum().reset_index()

    # Add coordinates
    node_df["x"] = node_df["node"].map(lambda n: graph.nodes[n]["x"])
    node_df["y"] = node_df["node"].map(lambda n: graph.nodes[n]["y"])

    # Convert to igraph indices
    node_df["node_ig"] = node_df["node"].map(lambda n: idx_maps["node_nx_to_ig"][n])

    return node_df


# %%
def add_depot(
    node_df: pd.DataFrame,
    graph: nx.MultiDiGraph,
    idx_maps: dict,
    center_lon: float = 6.597982,
    center_lat: float = 46.527867,
) -> Tuple[pd.DataFrame, int]:
    """Add depot location to node DataFrame.

    Args:
        node_df: DataFrame with client nodes
        graph: NetworkX MultiDiGraph
        idx_maps: Index mapping dictionary
        center_lon: Longitude of depot
        center_lat: Latitude of depot

    Returns:
        Tuple of (updated DataFrame with depot, depot igraph node index)
    """
    depot_node_nx = ox.distance.nearest_nodes(graph, center_lon, center_lat)
    depot_node_ig = idx_maps["node_nx_to_ig"][depot_node_nx]

    node_df["isdepot"] = False

    # If depot node already exists in node_df, mark it
    if depot_node_nx in node_df["node"].values:
        node_df.loc[node_df["node"] == depot_node_nx, "centroid_waste"] = 0
        node_df.loc[node_df["node"] == depot_node_nx, "isdepot"] = True
    else:
        # Add new row for depot
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


# %% [markdown]
# ## Section 3: CVRP Model Creation & Solving
#
# Functions for creating and solving the CVRP problem.
#


# %%
def create_distance_matrix(g_ig: ig.Graph, node_df: pd.DataFrame) -> Tuple[List, List]:
    """Create origin-destination distance matrix.

    Args:
        g_ig: igraph Graph
        node_df: DataFrame with node_ig column

    Returns:
        Tuple of (distance matrix, list of inaccessible node indices)
    """
    unique_ig_nodes = list(set(node_df["node_ig"].tolist()))
    od_distance = g_ig.distances(unique_ig_nodes, unique_ig_nodes, weights="length")

    inaccessible_indices = [
        i for i, dist in enumerate(od_distance[0]) if dist == float("inf")
    ]

    return od_distance, inaccessible_indices


# %%
def create_cvrp_model(
    node_df: pd.DataFrame,
    inaccessible_indices: List,
    od_distance: List,
    n_vehicles: int = 15,
    vehicle_capacity: int = 5000,
) -> pyvrp.Model:
    """Create PyVRP model.

    Args:
        node_df: DataFrame with depot and client nodes
        inaccessible_indices: List of nodes unreachable from depot
        od_distance: Origin-destination distance matrix
        n_vehicles: Number of vehicles
        vehicle_capacity: Maximum capacity per vehicle in kg

    Returns:
        Configured PyVRP Model
    """
    m = pyvrp.Model()

    # Add depot
    depot = m.add_depot(
        x=node_df.loc[node_df["isdepot"], "x"].values[0],
        y=node_df.loc[node_df["isdepot"], "y"].values[0],
    )

    # Add vehicle type with reload capability
    regular = m.add_profile(name="regular")
    m.add_vehicle_type(
        n_vehicles,
        capacity=vehicle_capacity,
        reload_depots=[depot],
        max_reloads=10,
        profile=regular,
    )

    # Add clients
    for _, row in node_df.iterrows():
        if not row["isdepot"]:
            required = row["node_ig"] not in inaccessible_indices
            # if not required:
            # logging.info(
            #     f"Node {row['node']} (ig: {row['node_ig']}) is inaccessible, "
            #     f"adding as optional client"
            # )

            m.add_client(
                x=row["x"],
                y=row["y"],
                delivery=int(row["centroid_waste"]),
                required=required,
            )

    # Add edges
    for frm_idx, frm in enumerate(m.locations):
        for to_idx, to in enumerate(m.locations):
            duration = od_distance[frm_idx][to_idx]

            if duration == float("inf"):
                # logging.info(
                #     f"Edge {frm_idx} -> {to_idx} inaccessible, "
                #     f"setting large distance"
                # )
                duration = 999999

            m.add_edge(frm, to, distance=duration)

    return m


# %%
def solve_cvrp(
    model: pyvrp.Model,
    max_runtime: int = 5,
    no_improvement_iterations: int = 100,
    seed: int = 42,
) -> pyvrp.Result:
    """Solve CVRP model.

    Args:
        model: PyVRP Model to solve
        max_runtime: Maximum runtime in seconds
        no_improvement_iterations: Stop after N iterations with no improvement
        seed: Random seed for reproducibility

    Returns:
        PyVRP Result object
    """
    stop_criteria = pyvrp.stop.MultipleCriteria(
        [
            pyvrp.stop.MaxRuntime(max_runtime),
            pyvrp.stop.NoImprovement(no_improvement_iterations),
        ]
    )

    result = model.solve(stop=stop_criteria, seed=seed)
    return result


# %% [markdown]
# ## Section 4: Route Processing & Analysis (NEW FEATURES)
#
# Functions for extracting routes with depot movements, calculating load progression, routing on graph, and analyzing edge loads.
#


# %%
def extract_routes_with_depots(
    solution: pyvrp.Solution, depot_idx: int = 0
) -> List[Dict]:
    """Extract routes from solution with explicit depot visits.

    Adds depot location (0) at:
    - Start of each route
    - End of each route
    - Before/after reload trips

    Args:
        solution: PyVRP Solution object
        depot_idx: Index of depot in model (default 0)

    Returns:
        List of route dictionaries with structure:
        [
            {
                'route_id': 0,
                'vehicle_id': 0,
                'total_distance': 7523303,
                'total_delivery': 4850,
                'n_trips': 3,
                'trips': [
                    {
                        'trip_id': 0,
                        'sequence': [0, 25, 423, 2, ..., 0],
                        'distance': 1024585,
                        'delivery': 4710,
                        'start_depot': 0,
                        'end_depot': 0,
                        'is_reload': False
                    },
                    ...
                ]
            },
            ...
        ]
    """
    routes = solution.routes()
    result = []

    for route_id, route in enumerate(routes):
        trips_data = []
        total_distance = 0
        total_delivery = 0

        for trip_id, trip in enumerate(route.trips()):
            # Build sequence with depot at start and end
            sequence = [trip.start_depot()] + list(trip.visits()) + [trip.end_depot()]

            trip_distance = trip.distance()
            trip_delivery = trip.delivery()[0]  # First dimension is delivery

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
                    "is_reload": trip_id > 0,  # Trips after first are reloads
                }
            )

        result.append(
            {
                "route_id": route_id,
                "vehicle_id": route_id,  # Assuming 1-to-1 mapping
                "total_distance": total_distance,
                "total_delivery": total_delivery,
                "n_trips": len(trips_data),
                "trips": trips_data,
            }
        )

    return result


# %%
def calculate_load_progression(routes: List[Dict], node_df: pd.DataFrame) -> List[Dict]:
    """Calculate cumulative load after pickup at each client location.

    Args:
        routes: List of route dictionaries from extract_routes_with_depots()
        node_df: DataFrame with client demands (centroid_waste column)

    Returns:
        List of load progression dictionaries:
        [
            {
                'route_id': 0,
                'trip_id': 0,
                'progression': [
                    {'location_idx': 0, 'cumulative_load': 0},  # depot start
                    {'location_idx': 25, 'cumulative_load': 10},
                    {'location_idx': 423, 'cumulative_load': 20},
                    ...
                    {'location_idx': 0, 'cumulative_load': 0}  # depot end (after unload)
                ]
            },
            ...
        ]
    """
    # Create lookup for client demands by location index
    # Location 0 is depot, locations 1..N are clients in order they were added
    demands = {0: 0}  # Depot has no demand

    client_idx = 1
    for _, row in node_df.iterrows():
        if not row.get("isdepot", False):
            demands[client_idx] = row["centroid_waste"]
            client_idx += 1

    result = []

    for route in routes:
        route_id = route["route_id"]

        for trip in route["trips"]:
            trip_id = trip["trip_id"]
            sequence = trip["sequence"]

            progression = []
            cumulative_load = 0

            for loc_idx in sequence:
                # At depot end, unload everything
                if loc_idx == 0 and len(progression) > 0:
                    cumulative_load = 0
                # At clients, add pickup
                elif loc_idx != 0:
                    cumulative_load += demands.get(loc_idx, 0)

                progression.append(
                    {"location_idx": loc_idx, "cumulative_load": cumulative_load}
                )

            result.append(
                {"route_id": route_id, "trip_id": trip_id, "progression": progression}
            )

    return result


# %%
def route_on_graph(
    routes: List[Dict], g_ig: ig.Graph, node_df: pd.DataFrame, idx_maps: Dict
) -> Dict:
    """Route each trip segment on the actual street network.

    Args:
        routes: List of route dictionaries from extract_routes_with_depots()
        g_ig: igraph Graph
        node_df: DataFrame with node mappings
        idx_maps: Index mapping dictionary

    Returns:
        Dictionary with:
        {
            'routes': routes,  # Pass-through of input routes
            'graph_paths': [
                {
                    'route_id': 0,
                    'trip_id': 0,
                    'segment_id': 0,
                    'from_loc': 0,
                    'to_loc': 25,
                    'path_ig': [1234, 1235, ...],  # igraph node indices
                    'path_nx': [node1, node2, ...],  # NetworkX node IDs
                    'path_length': 1234.5,
                    'success': True
                },
                ...
            ],
            'routing_stats': {
                'total_segments': 1000,
                'successful': 993,
                'failed': 7,
                'failed_segments': [(route_id, trip_id, from_loc, to_loc), ...]
            }
        }
    """
    # Map VRP location indices to igraph node indices
    loc_to_ig = [node_df.loc[node_df["isdepot"], "node_ig"].values[0]]  # Depot at loc 0
    for _, row in node_df.iterrows():
        if not row.get("isdepot", False):
            loc_to_ig.append(row["node_ig"])

    # Map igraph indices back to NetworkX node IDs
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

                    # Get shortest path on graph
                    path_ig = g_ig.get_shortest_paths(
                        from_ig, to=to_ig, weights="length", output="vpath"
                    )[0]

                    if len(path_ig) == 0:
                        # Empty path = unreachable
                        logging.warning(
                            f"Route {route_id}, Trip {trip_id}, Segment {segment_id}: "
                            f"No path found from location {from_loc} to {to_loc}"
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
                        # Convert to NetworkX node IDs
                        path_nx = [ig_to_nx[n] for n in path_ig]

                        # Calculate path length
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

                except Exception as e:
                    logging.error(
                        f"Route {route_id}, Trip {trip_id}, Segment {segment_id}: "
                        f"Error routing from {from_loc} to {to_loc}: {e}"
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


# %%
def calculate_edge_loads(
    routing_result: Dict,
    load_progression: List[Dict],
    graph: nx.MultiDiGraph,
    unit: str = "kg",
) -> Dict:
    """Calculate total load passing through each edge.

    Args:
        routing_result: Output from route_on_graph()
        load_progression: Output from calculate_load_progression()
        graph: NetworkX MultiDiGraph
        unit: 'kg' for load sum, or 'kg_m' for load × distance

    Returns:
        Dictionary with:
        {
            'edge_loads': {
                (node1, node2, key): total_load,
                ...
            },
            'max_load': 5000,
            'max_load_edge': (node1, node2, 0),
            'unit': 'kg',
            'n_edges_used': 1234
        }
    """
    edge_loads = defaultdict(float)

    # Create lookup for load at each segment
    segment_loads = {}
    for lp in load_progression:
        route_id = lp["route_id"]
        trip_id = lp["trip_id"]

        for i in range(len(lp["progression"]) - 1):
            from_loc = lp["progression"][i]["location_idx"]
            to_loc = lp["progression"][i + 1]["location_idx"]
            # Load during this segment is the load AFTER picking up at from_loc
            load = lp["progression"][i]["cumulative_load"]

            segment_loads[(route_id, trip_id, i)] = load

    # Process each graph path
    for gp in routing_result["graph_paths"]:
        if not gp["success"]:
            continue

        route_id = gp["route_id"]
        trip_id = gp["trip_id"]
        segment_id = gp["segment_id"]
        path_nx = gp["path_nx"]

        # Get load for this segment
        load = segment_loads.get((route_id, trip_id, segment_id), 0)

        # Iterate through each edge in the path
        for i in range(len(path_nx) - 1):
            u = path_nx[i]
            v = path_nx[i + 1]

            # Find the edge (there may be multiple edges between u and v in a MultiDiGraph)
            if graph.has_edge(u, v):
                # Get all edge keys between u and v
                edge_data = graph.get_edge_data(u, v)

                # Use the shortest edge (by length) for routing
                if len(edge_data) == 1:
                    key = list(edge_data.keys())[0]
                else:
                    # Multiple edges exist, choose the shortest one
                    key = min(
                        edge_data.keys(),
                        key=lambda k: edge_data[k].get("length", float("inf")),
                    )

                if unit == "kg":
                    edge_loads[(u, v, key)] += load
                elif unit == "kg_m":
                    length = edge_data[key].get("length", 0)
                    edge_loads[(u, v, key)] += load * length
            else:
                # Edge might be in reverse direction (common in MultiDiGraphs)
                if graph.has_edge(v, u):
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

    # Find max load edge
    if edge_loads:
        max_load_edge = max(edge_loads.items(), key=lambda x: x[1])
        max_edge = max_load_edge[0]
        max_load = max_load_edge[1]
    else:
        max_edge = None
        max_load = 0

    return {
        "edge_loads": dict(edge_loads),
        "max_load": max_load,
        "max_load_edge": max_edge,
        "unit": unit,
        "n_edges_used": len(edge_loads),
    }


# %% [markdown]
# ## Section 5: Complete Workflow Demonstration
#
# Demonstration of the complete workflow from data loading to route analysis.
#

# %%
# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# %%
# Step 1: Load graph
print("Loading graph...")
graph = ox.load_graphml("data/lausanne.graphml")
print(f"Graph loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges")


# %%
# Step 2: Convert to igraph and get node mappings
print("\nConverting to igraph...")
g_ig = nx_to_ig(graph)
nodes, nodes_ig, idx_maps = get_intersection_nodes(graph)
print(f"igraph created: {g_ig.vcount()} vertices, {g_ig.ecount()} edges")
print(f"Intersection nodes: {len(nodes)}")


# %%
# Step 3: Process waste centroids
print("\nProcessing waste centroids...")
waste_per_centroid = 10
node_df = process_centroids(graph, idx_maps, waste_per_centroid)
print(f"Client nodes: {len(node_df)}")
print(f"Total waste: {node_df['centroid_waste'].sum()} kg")


# %%
# Step 4: Add depot
print("\nAdding depot...")
node_df, depot_osm_node_ig = add_depot(node_df, graph, idx_maps)
print(f"Depot igraph node: {depot_osm_node_ig}")
print(f"Total nodes (with depot): {len(node_df)}")


# %%
# Step 5: Create distance matrix
print("\nCreating distance matrix...")
od_distance, inaccessible_indices = create_distance_matrix(g_ig, node_df)
print(f"Distance matrix: {len(od_distance)}x{len(od_distance[0])}")
print(f"Inaccessible nodes: {len(inaccessible_indices)}")


# %%
len(od_distance)

# %%
# Step 6: Create CVRP model
print("\nCreating CVRP model...")
n_vehicles = 5
vehicle_capacity = 5000
m = create_cvrp_model(
    node_df,
    inaccessible_indices,
    od_distance,
    n_vehicles=n_vehicles,
    vehicle_capacity=vehicle_capacity,
)
print(f"Model created: {len(m.locations)} locations, {n_vehicles} vehicles")


# %%
# Step 7: Solve CVRP
print("\nSolving CVRP...")
res = solve_cvrp(m, max_runtime=5, no_improvement_iterations=100)
print(f"\nSolution found!")
# print(f"  Objective: {res.best.cost()}")
print(f"  Routes: {res.best.num_routes()}")
print(f"  Missing clients: {res.best.num_missing_clients()}")


# %%
# Visualize solution
fig, ax = plt.subplots(figsize=(12, 12))
pyvrp.plotting.plot_solution(res.best, m.data(), ax=ax, plot_clients=True)
plt.tight_layout()
plt.show()


# %% [markdown]
# ### NEW FEATURES DEMONSTRATION
#

# %%
# Step 8: Extract routes with depot movements
print("\n" + "=" * 60)
print("FEATURE 1: Extracting routes with depot movements")
print("=" * 60)
routes = extract_routes_with_depots(res.best)

print(f"\nExtracted {len(routes)} routes:")
for route in routes:
    print(f"\nRoute {route['route_id']}:")
    print(f"  Vehicle: {route['vehicle_id']}")
    print(f"  Total distance: {route['total_distance']}")
    print(f"  Total delivery: {route['total_delivery']} kg")
    print(f"  Number of trips: {route['n_trips']}")

    for trip in route["trips"]:
        print(f"    Trip {trip['trip_id']}:")
        print(f"      Sequence: {trip['sequence'][:5]}...{trip['sequence'][-3:]}")
        print(f"      Distance: {trip['distance']}")
        print(f"      Delivery: {trip['delivery']} kg")
        print(f"      Reload: {trip['is_reload']}")


# %%
# Step 9: Calculate load progression
print("\n" + "=" * 60)
print("FEATURE 2: Calculating load progression")
print("=" * 60)
load_progression = calculate_load_progression(routes, node_df)

print(f"\nLoad progression calculated for {len(load_progression)} trips")
print("\nExample - First trip of first route:")
first_trip_load = load_progression[0]
print(f"Route {first_trip_load['route_id']}, Trip {first_trip_load['trip_id']}")
print(f"\nFirst 10 locations:")
for item in first_trip_load["progression"][:10]:
    print(f"  Location {item['location_idx']:4d}: {item['cumulative_load']:5.0f} kg")


# %%
# Step 10: Route on graph
print("\n" + "=" * 60)
print("FEATURE 3: Routing on actual street network")
print("=" * 60)
routing_result = route_on_graph(routes, g_ig, node_df, idx_maps)

stats = routing_result["routing_stats"]
print(f"\nRouting statistics:")
print(f"  Total segments: {stats['total_segments']}")
print(f"  Successful: {stats['successful']}")
print(f"  Failed: {stats['failed']}")
print(f"  Success rate: {100*stats['successful']/stats['total_segments']:.1f}%")

if stats["failed"] > 0:
    print(f"\nFailed segments:")
    for route_id, trip_id, from_loc, to_loc in stats["failed_segments"][:5]:
        print(f"  Route {route_id}, Trip {trip_id}: {from_loc} -> {to_loc}")
    if len(stats["failed_segments"]) > 5:
        print(f"  ... and {len(stats['failed_segments']) - 5} more")


# %%
# Step 11: Calculate edge loads (in kg)
print("\n" + "=" * 60)
print("FEATURE 4a: Calculating edge loads (kg)")
print("=" * 60)
edge_loads_kg = calculate_edge_loads(routing_result, load_progression, graph, unit="kg")

print(f"\nEdge load statistics (kg):")
print(f"  Edges used: {edge_loads_kg['n_edges_used']}")
print(f"  Max load: {edge_loads_kg['max_load']:.0f} kg")
print(f"  Max load edge: {edge_loads_kg['max_load_edge']}")

# Show top 10 most loaded edges
sorted_edges = sorted(
    edge_loads_kg["edge_loads"].items(), key=lambda x: x[1], reverse=True
)
print(f"\nTop 10 most loaded edges:")
for i, (edge, load) in enumerate(sorted_edges[:10], 1):
    u, v, key = edge
    print(f"  {i}. Edge ({u}, {v}, {key}): {load:.0f} kg")


# %%
# Step 11b: Calculate edge loads (in kg·m)
print("\n" + "=" * 60)
print("FEATURE 4b: Calculating edge loads (kg·m)")
print("=" * 60)
edge_loads_kgm = calculate_edge_loads(
    routing_result, load_progression, graph, unit="kg_m"
)

print(f"\nEdge load statistics (kg·m):")
print(f"  Edges used: {edge_loads_kgm['n_edges_used']}")
print(f"  Max load×distance: {edge_loads_kgm['max_load']:.0f} kg·m")
print(f"  Max load edge: {edge_loads_kgm['max_load_edge']}")

# Show top 10 most loaded edges
sorted_edges = sorted(
    edge_loads_kgm["edge_loads"].items(), key=lambda x: x[1], reverse=True
)
print(f"\nTop 10 most loaded edges (by kg·m):")
for i, (edge, load) in enumerate(sorted_edges[:10], 1):
    u, v, key = edge
    print(f"  {i}. Edge ({u}, {v}, {key}): {load:.0f} kg·m")


# %% [markdown]
# ### Visualization of Routes on Graph
#

# %%
# Visualize routes on street network
# import matplotlib.cm as cm

# # Prepare paths for visualization
# all_paths_nx = []
# route_colors = []

# n_routes = len(routes)
# for gp in routing_result['graph_paths']:
#     if gp['success'] and len(gp['path_nx']) > 0:
#         route_id = gp['route_id']
#         color = cm.rainbow(route_id / max(n_routes, 1))

#         all_paths_nx.append(gp['path_nx'])
#         route_colors.append(color)

# print(f"Plotting {len(all_paths_nx)} route segments...")

# # Plot
# fig, ax = ox.plot_graph_routes(
#     graph,
#     all_paths_nx,
#     route_colors=route_colors,
#     route_linewidth=2,
#     node_size=0,
#     figsize=(16, 16)
# )
# plt.show()


# %% [markdown]
# ## Summary
#
# This refactored notebook provides:
#
# 1. **Well-structured functions** for CVRP solving workflow
# 2. **Route extraction with depot movements** - explicitly showing when vehicles return to depot
# 3. **Load progression calculation** - tracking cumulative load at each stop
# 4. **Graph-based routing** - routing on actual street network with failure handling
# 5. **Edge load aggregation** - identifying which streets carry the most waste
#
# All functions return Python dictionaries for easy serialization and integration with backend APIs.
#

# %% [markdown]
# ### Visualization of Edge Loads
#
# Color-coded visualization showing which streets carry the most waste load.
#

# %%
# Diagnostic: Check edge load data structure
print("Edge Load Data Diagnostics")
print("=" * 60)

# Sample some edges
sample_edges = list(edge_loads_kg["edge_loads"].items())[:5]
print(f"\nSample edge loads (kg):")
for edge, load in sample_edges:
    print(f"  {edge}: {load:.1f} kg")

# Check edge format in graph
sample_graph_edges = list(graph.edges(keys=True))[:5]
print(f"\nSample graph edges:")
for u, v, k in sample_graph_edges:
    print(f"  ({u}, {v}, {k})")

# Check for matches
matches = 0
for edge in list(edge_loads_kg["edge_loads"].keys())[:100]:
    if graph.has_edge(edge[0], edge[1], edge[2]):
        matches += 1

print(f"\nEdge matching test (first 100):")
print(f"  {matches}/100 edges found in graph")

if matches == 0:
    print("\n⚠️  WARNING: No edges matching! This explains the visualization issue.")
    print("   This happens when edge directions don't match.")
    print("   The calculate_edge_loads function may need adjustment.")


import matplotlib as mpl

# %%
# Visualize edge loads on the street network
import numpy as np

# Prepare edge colors and widths based on load
edge_colors = []
edge_widths = []

# Get all edges in the graph
all_edges = list(graph.edges(keys=True))

# Create a lookup for edge loads
edge_load_lookup = edge_loads_kg["edge_loads"]

print(f"Total edges in graph: {len(all_edges)}")
print(f"Edges with loads: {len(edge_load_lookup)}")

# Normalize loads for visualization
if edge_load_lookup:
    loads_with_values = [v for v in edge_load_lookup.values() if v > 0]

    if loads_with_values:
        max_load = max(loads_with_values)
        min_load = min(loads_with_values)

        print(f"Edge load range: {min_load:.0f} - {max_load:.0f} kg")

        for u, v, k in all_edges:
            # Try to find load for this edge
            load = edge_load_lookup.get((u, v, k), 0)

            if load > 0:
                # Normalize load to 0-1 range for color mapping
                norm_load = (
                    (load - min_load) / (max_load - min_load)
                    if max_load > min_load
                    else 0.5
                )

                # Use colormap: blue (low) -> yellow -> red (high)
                color = plt.cm.YlOrRd(norm_load)
                # return as hex color
                color = mpl.colors.rgb2hex(color)

                # Width proportional to load (1-5 range)
                width = 1 + 4 * norm_load
            else:
                # Unused edges in light gray
                color = "#e0e0e0"
                width = 0.3

            edge_colors.append(color)
            edge_widths.append(width)

        # Create figure
        fig, ax = plt.subplots(figsize=(16, 16))

        # Plot the graph
        ox.plot_graph(
            graph,
            ax=ax,
            node_size=0,
            edge_color=edge_colors,
            # edge_linewidth=edge_widths,
            show=False,
            close=False,
        )

        # Add colorbar
        sm = plt.cm.ScalarMappable(
            cmap=plt.cm.YlOrRd, norm=plt.Normalize(vmin=min_load, vmax=max_load)
        )
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
        cbar.set_label("Total Load (kg)", rotation=270, labelpad=20, fontsize=12)

        ax.set_title(
            f'Edge Load Distribution\n{edge_loads_kg["n_edges_used"]} edges used, '
            f"max load: {max_load:.0f} kg",
            fontsize=14,
            pad=20,
        )

        plt.tight_layout()
        plt.show()

        print(f"\nVisualization complete!")
        print(f"  Red edges = high load")
        print(f"  Yellow edges = medium load")
        print(f"  Blue edges = low load")
        print(f"  Gray edges = unused")
    else:
        print("No edges with positive loads found")
else:
    print("No edge loads to visualize")


# %%
edge_colors

# %%
fig, ax = plt.subplots(figsize=(16, 16))

ox.plot_graph(
    graph,
    ax=ax,
    node_size=0,
    edge_color=edge_colors,
    edge_linewidth=edge_widths,
    show=False,
    close=False,
)

# Add colorbar
# sm = plt.cm.ScalarMappable(
#     cmap=plt.cm.YlOrRd,
#     norm=plt.Normalize(vmin=min_load, vmax=max_load)
# )
# sm.set_array([])
# cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
# cbar.set_label('Total Load (kg)', rotation=270, labelpad=20, fontsize=12)

# ax.set_title(
#     f'Edge Load Distribution\n{edge_loads_kg["n_edges_used"]} edges used, '
#     f'max load: {max_load:.0f} kg',
#     fontsize=14,
#     pad=20
# )

plt.tight_layout()
plt.show()

print(f"\nVisualization complete!")
print(f"  Red edges = high load")
print(f"  Yellow edges = medium load")
print(f"  Blue edges = low load")
print(f"  Gray edges = unused")

# %%
# Also visualize load×distance (kg·m) for comparison
edge_colors_kgm = []
edge_widths_kgm = []

edge_load_lookup_kgm = edge_loads_kgm["edge_loads"]

if edge_load_lookup_kgm:
    loads_with_values_kgm = [v for v in edge_load_lookup_kgm.values() if v > 0]

    if loads_with_values_kgm:
        max_load_kgm = max(loads_with_values_kgm)
        min_load_kgm = min(loads_with_values_kgm)

        print(
            f"\nEdge load×distance range: {min_load_kgm:.0f} - {max_load_kgm:.0f} kg·m"
        )

        for u, v, k in all_edges:
            load = edge_load_lookup_kgm.get((u, v, k), 0)

            if load > 0:
                norm_load = (
                    (load - min_load_kgm) / (max_load_kgm - min_load_kgm)
                    if max_load_kgm > min_load_kgm
                    else 0.5
                )
                color = plt.cm.YlOrRd(norm_load)
                width = 1 + 4 * norm_load
            else:
                color = "#e0e0e0"
                width = 0.3

            edge_colors_kgm.append(color)
            edge_widths_kgm.append(width)

        fig, ax = plt.subplots(figsize=(16, 16))

        ox.plot_graph(
            graph,
            ax=ax,
            node_size=0,
            edge_color=edge_colors_kgm,
            edge_linewidth=edge_widths_kgm,
            show=False,
            close=False,
        )

        sm = plt.cm.ScalarMappable(
            cmap=plt.cm.YlOrRd, norm=plt.Normalize(vmin=min_load_kgm, vmax=max_load_kgm)
        )
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
        cbar.set_label(
            "Total Load × Distance (kg·m)", rotation=270, labelpad=20, fontsize=12
        )

        ax.set_title(
            f'Edge Load×Distance Distribution\n{edge_loads_kgm["n_edges_used"]} edges used, '
            f"max: {max_load_kgm:.0f} kg·m",
            fontsize=14,
            pad=20,
        )

        plt.tight_layout()
        plt.show()

        print(f"\nkg·m visualization accounts for both load and edge length")
        print(f"Useful for infrastructure wear analysis")
    else:
        print("No edges with positive kg·m loads found")


# %% [markdown]
# ### Interpretation of Edge Load Visualizations
#
# **First map (kg):** Shows total weight of waste passing through each edge
# - Best for: Identifying critical collection routes
# - Use case: Where should we focus maintenance?
#
# **Second map (kg·m):** Shows load weighted by distance
# - Best for: Infrastructure wear and environmental impact
# - Use case: Which roads experience most stress?
#
# **Colors:**
# - 🔴 Red: High load (critical infrastructure)
# - 🟡 Yellow: Medium load
# - 🔵 Blue: Low load
# - ⚪ Gray: Unused edges
#
