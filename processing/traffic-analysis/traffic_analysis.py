# %% [markdown]
# # Traffic Analysis with Waste Collection Points
#
# Analyze Lausanne's traffic network and visualize waste collection centroids.

# %%
import osmnx as ox
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Interactive visualization with pydeck (with road network edges and descriptive labels)
import pydeck as pdk
import random
import itertools
from collections import defaultdict
import numpy as np
import geopandas as gpd

# %%
# Load pre-saved networks from disk
data_dir = Path("data/graph")
networks = {}
types = ["drive"]
# types= ['drive', 'walk', 'bike']

for net_type in types:
    graph_path = data_dir / f"lausanne_{net_type}.graphml"
    networks[net_type] = ox.load_graphml(graph_path)
    print(
        f"Loaded {net_type} network: {len(networks[net_type].nodes)} nodes, {len(networks[net_type].edges)} edges"
    )

# Default to drive network
G = networks["drive"]

# %%
# Load waste collection centroids
waste_dir = Path("data/waste")

waste_types = {
    "DV": {"name": "Organic waste", "color": "orange"},
    # 'DI': {'name': 'Household waste', 'color': 'green'},
    # 'PC': {'name': 'Paper & Cardboards', 'color': 'purple'},
    # 'VE': {'name': 'Glass', 'color': 'blue'}
}

waste_data = {}
for waste_code, info in waste_types.items():
    file_path = waste_dir / f"{waste_code}_final_clustered_centroids.csv"
    df = pd.read_csv(file_path)
    waste_data[waste_code] = df
    print(f"{waste_code} ({info['name']}): {len(df)} centroids")

# %%


lausanne_center = [6.6322734, 46.5196535]  # [lon, lat]

# Prepare edge data for pydeck (as lines) using full geometry
edge_data = []
for u, v, d in G.edges(data=True):
    if "geometry" in d:
        # Use the full LineString geometry if available
        coords = list(d["geometry"].coords)
        path = [[lon, lat] for lon, lat in coords]
    else:
        # Fallback to straight line between nodes
        u_x, u_y = G.nodes[u]["x"], G.nodes[u]["y"]
        v_x, v_y = G.nodes[v]["x"], G.nodes[v]["y"]
        path = [[u_x, u_y], [v_x, v_y]]

    edge_data.append({"path": path, "color": [180, 180, 180], "width": 2})

# Prepare centroid data for pydeck (as points)
scatter_data = []
for waste_code, info in waste_types.items():
    df = waste_data[waste_code]
    if "centroid_lat" in df.columns and "centroid_lon" in df.columns:
        lats = df["centroid_lat"]
        lons = df["centroid_lon"]
    elif "latitude" in df.columns and "longitude" in df.columns:
        lats = df["latitude"]
        lons = df["longitude"]
    elif "lat" in df.columns and "lon" in df.columns:
        lats = df["lat"]
        lons = df["lon"]
    else:
        continue
    for lat, lon in zip(lats, lons):
        scatter_data.append(
            {
                "lat": lat,
                "lon": lon,
                "waste_code": waste_code,
                "waste_label": info["name"],
                "color": info["color"],
            }
        )

color_map = {
    "orange": [255, 140, 0],
    "green": [0, 200, 0],
    "purple": [128, 0, 128],
    "blue": [0, 120, 255],
}

for d in scatter_data:
    d["color_rgb"] = color_map.get(waste_types[d["waste_code"]]["color"], [0, 0, 0])

# Road network as LineLayer
edge_layer = pdk.Layer(
    "PathLayer",
    edge_data,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=1,
    get_width="width",
    opacity=0.5,
    pickable=False,
)

# Waste centroids as ScatterplotLayer
centroid_layer = pdk.Layer(
    "ScatterplotLayer",
    scatter_data,
    get_position="[lon, lat]",
    get_color="color_rgb",
    get_label="waste_label",
    get_radius=5,
    pickable=True,
    auto_highlight=True,
    opacity=0.8,
    tooltip=True,
)

view_state = pdk.ViewState(
    longitude=lausanne_center[0],
    latitude=lausanne_center[1],
    zoom=12,
    min_zoom=10,
    max_zoom=18,
    pitch=0,
    bearing=0,
)


# %%
# Assign each centroid to its closest node in the graph using osmnx API (vectorized)
centroid_to_node = {}
for waste_code, info in waste_types.items():
    df = waste_data[waste_code]
    if "centroid_lat" in df.columns and "centroid_lon" in df.columns:
        lats = df["centroid_lat"].values
        lons = df["centroid_lon"].values
    elif "latitude" in df.columns and "longitude" in df.columns:
        lats = df["latitude"].values
        lons = df["longitude"].values
    elif "lat" in df.columns and "lon" in df.columns:
        lats = df["lat"].values
        lons = df["lon"].values
    else:
        continue
    # Use osmnx.nearest_nodes vectorized API
    node_ids = ox.nearest_nodes(G, lons, lats)
    df["nearest_node"] = node_ids
    centroid_to_node[waste_code] = node_ids
    waste_data[waste_code] = df
print("Assigned each centroid to its closest node in the graph (osmnx vectorized API).")

# %%
# Add a layer for the assigned nearest nodes (as blue markers)
assigned_node_data = []
for waste_code, info in waste_types.items():
    df = waste_data[waste_code]
    if "nearest_node" in df:
        for node_id in df["nearest_node"]:
            node = G.nodes[node_id]
            assigned_node_data.append(
                {"lat": node["y"], "lon": node["x"], "waste_label": info["name"]}
            )

assigned_node_layer = pdk.Layer(
    "ScatterplotLayer",
    assigned_node_data,
    get_position="[lon, lat]",
    get_color=[0, 0, 255],  # blue
    get_radius=10,
    pickable=False,
    opacity=0.7,
    radius_min_pixels=1,
    radius_max_pixels=10,
)


# %%

r = pdk.Deck(
    layers=[edge_layer, assigned_node_layer],
    initial_view_state=view_state,
    map_style=pdk.map_styles.LIGHT,
    tooltip={"text": "{waste_label}\nLat: {lat}\nLon: {lon}"},
)
r.show()

# %%
for u, v, d in G.edges(data=True):
    print(d)
    print(d["geometry"].coords)
    break

# %%
G = ox.routing.add_edge_speeds(G)


edge_data_speed = []
for u, v, d in G.edges(data=True):
    if "geometry" in d:
        coords = list(d["geometry"].coords)
        path = [[lon, lat] for lon, lat in coords]
    else:
        u_x, u_y = G.nodes[u]["x"], G.nodes[u]["y"]
        v_x, v_y = G.nodes[v]["x"], G.nodes[v]["y"]
        path = [[u_x, u_y], [v_x, v_y]]

    speed = d.get("speed_kph", "N/A")

    highway_raw = d.get("highway", "Unknown")
    highway = highway_raw[0] if isinstance(highway_raw, list) else highway_raw

    name_raw = d.get("name")
    if isinstance(name_raw, list):
        name = " - ".join(str(n) for n in name_raw if n)
    elif name_raw:
        name = str(name_raw)
    else:
        name = (
            f"{highway.replace('_', ' ').title()}"
            if isinstance(highway, str)
            else "Road"
        )

    edge_data_speed.append(
        {
            "path": path,
            "color": [180, 180, 180],
            "width": 2,
            "speed_kph": speed,
            "name": name,
            "highway": highway,
        }
    )

# %%

# Ensure travel time is computed on the graph (requires speed_kph and length)
G = ox.routing.add_edge_travel_times(G)

# Collect all assigned nodes (from all waste types)
assigned_nodes = []
for waste_code, info in waste_types.items():
    df = waste_data[waste_code]
    if "nearest_node" in df:
        assigned_nodes.extend(df["nearest_node"].tolist())

# Remove duplicates, just in case
assigned_nodes = list(set(assigned_nodes))

# If less than 2 nodes, skip
if len(assigned_nodes) < 2:
    print("Not enough assigned nodes to compute paths.")
    path_layer = None
else:
    pairs = set()
    while len(pairs) < 20:
        a, b = random.sample(assigned_nodes, 2)
        if a != b:
            pairs.add((a, b))
    pairs = list(pairs)

    # Compute shortest paths (using travel_time as weight)
    shortest_paths = []
    for orig, dest in pairs:
        try:
            path = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
            if path is not None:
                shortest_paths.append(
                    {"origin": orig, "destination": dest, "path": path}
                )
        except Exception as e:
            print(f"Failed to find path between {orig} and {dest}: {e}")

    print(
        f"Computed {len(shortest_paths)} shortest paths between 20 random pairs of assigned nodes."
    )


# %%
def generate_distinct_colors(n):
    colors = []
    for i in range(n):
        hue = (i * 360 / n) % 360
        import colorsys

        rgb = colorsys.hsv_to_rgb(hue / 360, 0.8, 0.9)
        colors.append([int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)])
    return colors


pair_colors = generate_distinct_colors(len(shortest_paths))

path_layer_data = []
origin_nodes_data = []
destination_nodes_data = []

for i, sp in enumerate(shortest_paths):
    # Build high-quality path using edge geometries
    path_coords = []
    for j in range(len(sp["path"]) - 1):
        u, v = sp["path"][j], sp["path"][j + 1]
        edge_data = G.get_edge_data(u, v)

        if edge_data and "geometry" in edge_data:
            coords = list(edge_data["geometry"].coords)
            if j == 0:
                path_coords.extend([[lon, lat] for lon, lat in coords])
            else:
                path_coords.extend([[lon, lat] for lon, lat in coords[1:]])
        else:
            if j == 0:
                path_coords.append([G.nodes[u]["x"], G.nodes[u]["y"]])
            path_coords.append([G.nodes[v]["x"], G.nodes[v]["y"]])

    color = pair_colors[i]

    path_layer_data.append(
        {"path": path_coords, "color": color, "width": 4, "pair_index": i}
    )

    origin_node = G.nodes[sp["origin"]]
    origin_nodes_data.append(
        {
            "lat": origin_node["y"],
            "lon": origin_node["x"],
            "pair_index": i,
            "color_rgb": color,
            "type": "Origin",
        }
    )

    dest_node = G.nodes[sp["destination"]]
    destination_nodes_data.append(
        {
            "lat": dest_node["y"],
            "lon": dest_node["x"],
            "pair_index": i,
            "color_rgb": color,
            "type": "Destination",
        }
    )


edge_layer_speed = pdk.Layer(
    "PathLayer",
    edge_data_speed,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=1,
    get_width="width",
    opacity=0.7,
    pickable=True,
)
path_layer = pdk.Layer(
    "PathLayer",
    path_layer_data,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=2,
    get_width="width",
    opacity=0.8,
    pickable=False,
)

origin_layer = pdk.Layer(
    "ScatterplotLayer",
    origin_nodes_data,
    get_position="[lon, lat]",
    get_color="color_rgb",
    get_radius=15,
    pickable=False,
    opacity=0.9,
    radius_min_pixels=5,
)

destination_layer = pdk.Layer(
    "ScatterplotLayer",
    destination_nodes_data,
    get_position="[lon, lat]",
    get_color="color_rgb",
    get_radius=12,
    pickable=False,
    opacity=0.9,
    radius_min_pixels=4,
    stroked=True,
    line_width_min_pixels=2,
    get_line_color=[255, 255, 255],
)

r = pdk.Deck(
    layers=[edge_layer_speed, path_layer, origin_layer, destination_layer],
    initial_view_state=view_state,
    map_style=pdk.map_styles.LIGHT,
    tooltip={
        "html": "<b>{name}</b><br/>Type: {highway}<br/>Speed: {speed_kph} km/h",
        "style": {"color": "white"},
    },
)
r.show()

# %% [markdown]
# ## Edge Removal Proof of Concept
# Remove edges from the graph and show how routes adapt

# %%
# Create a copy of the graph for modification
G_modified = G.copy()

# Select a few pairs to demonstrate edge removal (e.g., first 5 pairs)
demo_pairs_count = min(5, len(shortest_paths))
demo_pairs = shortest_paths[:demo_pairs_count]

# For each selected pair, remove one edge from the middle of its shortest path
removed_edges = []
for i, sp in enumerate(demo_pairs):
    path = sp["path"]
    if len(path) >= 3:
        # Remove an edge from the middle of the path
        mid_idx = len(path) // 2
        u, v = path[mid_idx], path[mid_idx + 1]

        # Check if edge exists before removing
        if G_modified.has_edge(u, v):
            G_modified.remove_edge(u, v)
            removed_edges.append((u, v))
            print(f"Removed edge ({u}, {v}) from pair {i}")

print(f"Removed {len(removed_edges)} edges from the modified graph")

# %%
# Recalculate shortest paths on the modified graph
recalculated_paths = []
for i, sp in enumerate(demo_pairs):
    orig, dest = sp["origin"], sp["destination"]
    try:
        new_path = ox.routing.shortest_path(
            G_modified, orig, dest, weight="travel_time"
        )
        if new_path is not None:
            recalculated_paths.append(
                {
                    "origin": orig,
                    "destination": dest,
                    "path": new_path,
                    "original_path": sp["path"],
                }
            )
            print(
                f"Recalculated path for pair {i}: {len(sp['path'])} -> {len(new_path)} nodes"
            )
    except Exception as e:
        print(f"Failed to recalculate path between {orig} and {dest}: {e}")

print(f"Successfully recalculated {len(recalculated_paths)} paths")

# %%
# Prepare visualization data for comparison
# Original paths in one color scheme, new paths in another

recalc_colors = generate_distinct_colors(len(recalculated_paths))

original_path_data = []
new_path_data = []
removed_edge_data = []

for i, rp in enumerate(recalculated_paths):
    color = recalc_colors[i]

    # Build original path geometry
    orig_coords = []
    for j in range(len(rp["original_path"]) - 1):
        u, v = rp["original_path"][j], rp["original_path"][j + 1]
        edge_data = G.get_edge_data(u, v)

        if edge_data and "geometry" in edge_data:
            coords = list(edge_data["geometry"].coords)
            if j == 0:
                orig_coords.extend([[lon, lat] for lon, lat in coords])
            else:
                orig_coords.extend([[lon, lat] for lon, lat in coords[1:]])
        else:
            if j == 0:
                orig_coords.append([G.nodes[u]["x"], G.nodes[u]["y"]])
            orig_coords.append([G.nodes[v]["x"], G.nodes[v]["y"]])

    original_path_data.append(
        {
            "path": orig_coords,
            "color": [*color, 100],  # Semi-transparent
            "width": 3,
            "pair_index": i,
            "type": "original",
        }
    )

    # Build new path geometry
    new_coords = []
    for j in range(len(rp["path"]) - 1):
        u, v = rp["path"][j], rp["path"][j + 1]
        edge_data = G_modified.get_edge_data(u, v)

        if edge_data and "geometry" in edge_data:
            coords = list(edge_data["geometry"].coords)
            if j == 0:
                new_coords.extend([[lon, lat] for lon, lat in coords])
            else:
                new_coords.extend([[lon, lat] for lon, lat in coords[1:]])
        else:
            if j == 0:
                new_coords.append([G.nodes[u]["x"], G.nodes[u]["y"]])
            new_coords.append([G.nodes[v]["x"], G.nodes[v]["y"]])

    new_path_data.append(
        {"path": new_coords, "color": color, "width": 5, "pair_index": i, "type": "new"}
    )

# Visualize removed edges
for u, v in removed_edges:
    edge_data = G.get_edge_data(u, v)
    if edge_data and "geometry" in edge_data:
        coords = list(edge_data["geometry"].coords)
        path = [[lon, lat] for lon, lat in coords]
    else:
        path = [[G.nodes[u]["x"], G.nodes[u]["y"]], [G.nodes[v]["x"], G.nodes[v]["y"]]]

    removed_edge_data.append({"path": path, "color": [0, 0, 0], "width": 6})  # Black

# %%
# Create layers for the comparison visualization
base_roads_layer = pdk.Layer(
    "PathLayer",
    edge_data_speed,
    get_path="path",
    get_color=[200, 200, 200],
    width_scale=10,
    width_min_pixels=1,
    get_width=1,
    opacity=0.3,
    pickable=False,
)

original_paths_layer = pdk.Layer(
    "PathLayer",
    original_path_data,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=2,
    get_width="width",
    opacity=0.4,
    pickable=True,
)

new_paths_layer = pdk.Layer(
    "PathLayer",
    new_path_data,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=3,
    get_width="width",
    opacity=0.9,
    pickable=True,
)

removed_edges_layer = pdk.Layer(
    "PathLayer",
    removed_edge_data,
    get_path="path",
    get_color="color",
    width_scale=10,
    width_min_pixels=4,
    get_width="width",
    opacity=0.8,
    pickable=True,
)

# Reuse origin and destination markers from earlier
comparison_origin_data = []
comparison_dest_data = []

for i, rp in enumerate(recalculated_paths):
    color = recalc_colors[i]

    origin_node = G.nodes[rp["origin"]]
    comparison_origin_data.append(
        {
            "lat": origin_node["y"],
            "lon": origin_node["x"],
            "color_rgb": color,
        }
    )

    dest_node = G.nodes[rp["destination"]]
    comparison_dest_data.append(
        {
            "lat": dest_node["y"],
            "lon": dest_node["x"],
            "color_rgb": color,
        }
    )

comparison_origin_layer = pdk.Layer(
    "ScatterplotLayer",
    comparison_origin_data,
    get_position="[lon, lat]",
    get_color="color_rgb",
    get_radius=15,
    pickable=False,
    opacity=0.9,
    radius_min_pixels=5,
)

comparison_dest_layer = pdk.Layer(
    "ScatterplotLayer",
    comparison_dest_data,
    get_position="[lon, lat]",
    get_color="color_rgb",
    get_radius=12,
    pickable=False,
    opacity=0.9,
    radius_min_pixels=4,
    stroked=True,
    line_width_min_pixels=2,
    get_line_color=[255, 255, 255],
)

# %%
# Create the comparison deck
r_comparison = pdk.Deck(
    layers=[
        base_roads_layer,
        original_paths_layer,
        new_paths_layer,
        comparison_origin_layer,
        comparison_dest_layer,
        removed_edges_layer,
    ],
    initial_view_state=view_state,
    map_style=pdk.map_styles.LIGHT,
    tooltip={
        "html": "<b>Path Type:</b> {type}<br/><b>Pair:</b> {pair_index}",
        "style": {"color": "white"},
    },
)
r_comparison.show()

# %%
