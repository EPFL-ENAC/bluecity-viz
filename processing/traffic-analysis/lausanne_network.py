# %% [markdown]
# # Lausanne Traffic Network Analysis
# 
# Download and analyze the road network of Lausanne for traffic simulation.

# %%
import osmnx as ox
import networkx as nx
from shapely import wkt
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import numpy as np

# %%
hull_polygon = 'POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, 6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, 6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, 6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, 6.7016307 46.4999401, 6.6973149 46.4991489))'
hull = wkt.loads(hull_polygon)
types = ['drive']

# %%
networks = {}
for net_type in types:
    graph_path = Path(f"data/graph/lausanne_{net_type}_enhanced.graphml")
    if graph_path.exists():
        print(f"Loading existing {net_type} network from {graph_path}")
        networks[net_type] = ox.load_graphml(graph_path)
    else:
        print(f"Downloading {net_type} network from OSM...")
        networks[net_type] = ox.graph_from_polygon(hull, network_type=net_type)

# Default to drive network for visualization
G = networks['drive']

# %%
# Visualize network
fig, ax = ox.plot_graph(G, figsize=(12, 12), node_size=0, edge_linewidth=0.5)

# %%
# Inspect graph properties
sample_edge = list(G.edges(data=True))[0]
print("Sample edge attributes:", sample_edge[2].keys())

# %%
# Compare network sizes
for name, graph in networks.items():
    length_km = sum(d['length'] for _, _, d in graph.edges(data=True)) / 1000
    print(f"{name:8} - Nodes: {len(graph.nodes):>5,} | Edges: {len(graph.edges):>6,} | Length: {length_km:>6.1f} km")

# %%
# Add edge speeds and travel times to networks
print("\nAdding edge speeds and travel times...")
for name, graph in networks.items():
    print(f"Processing {name} network...")
    
    # Add edge speeds (km/h)
    if not any("speed_kph" in d for _, _, d in graph.edges(data=True)):
        print(f"  Adding edge speeds to {name}...")
        graph = ox.routing.add_edge_speeds(graph)
    
    # Add travel times (seconds)
    if not any("travel_time" in d for _, _, d in graph.edges(data=True)):
        print(f"  Adding travel times to {name}...")
        graph = ox.routing.add_edge_travel_times(graph)
    
    networks[name] = graph

print("✓ Edge speeds and travel times added")

# %%
# Add elevation data to nodes using local raster data (Swiss ALTI3D)
# First, download the elevation data by running: python download_elevation_data.py
print("\nAdding elevation data to nodes using local raster files...")

import glob
import geopandas as gpd

elevation_dir = Path("data/elevation")
raster_files = sorted(glob.glob(str(elevation_dir / "*.tif")))

if raster_files:
    print(f"Found {len(raster_files)} elevation raster files")
    print(f"Note: Swiss rasters use MN95 (EPSG:2056), converting graph coordinates...")
    
    for name, graph in networks.items():
        print(f"Adding elevation data to {name} network ({len(graph.nodes)} nodes)...")
        try:
            # Convert graph to Swiss coordinate system MN95 (EPSG:2056 = CH1903+ / LV95)
            # Swiss ALTI3D rasters use the MN95 coordinate system
            graph_swiss = ox.project_graph(graph, to_crs="EPSG:2056")
            
            # Add elevation using the projected graph
            graph_swiss = ox.elevation.add_node_elevations_raster(
                graph_swiss,
                raster_files,
                cpus=None  # Use all available CPUs for parallel processing
            )
            
            # Copy elevation data back to original graph
            for node_id in graph.nodes():
                if node_id in graph_swiss.nodes and "elevation" in graph_swiss.nodes[node_id]:
                    graph.nodes[node_id]["elevation"] = graph_swiss.nodes[node_id]["elevation"]
            
            # Verify elevation data was added
            nodes_with_valid_elevation = sum(
                1 for _, d in graph.nodes(data=True) 
                if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
            )
            print(f"  ✓ Elevation data added: {nodes_with_valid_elevation}/{len(graph.nodes)} nodes have valid elevation")
            
            if nodes_with_valid_elevation > 0:
                # Show sample values
                sample_node = next(
                    n for n, d in graph.nodes(data=True) 
                    if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
                )
                sample_elev = graph.nodes[sample_node]["elevation"]
                print(f"  Sample: Node {sample_node} has elevation {sample_elev:.1f}m")
            
            networks[name] = graph
        except Exception as e:
            print(f"  ✗ Failed to add elevation data to {name}: {e}")
            import traceback
            traceback.print_exc()
else:
    print(f"⚠ No elevation raster files found in {elevation_dir}")
    print(f"  Run 'uv run python download_elevation_data.py' to download elevation data first")

# %%
# Add edge grades (rise over run) if elevation data is available
print("\nAdding edge grades...")
for name, graph in networks.items():
    # Check if nodes have elevation data
    nodes_with_elevation = [
        n for n, d in graph.nodes(data=True) 
        if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
    ]
    
    if nodes_with_elevation:
        print(f"Calculating grades for {name} network...")
        print(f"  Nodes with elevation data: {len(nodes_with_elevation)}/{len(graph.nodes)}")
        
        # Show sample elevation values
        sample_elevations = [
            graph.nodes[n]["elevation"] for n in list(nodes_with_elevation)[:5]
            if not pd.isna(graph.nodes[n]["elevation"])
        ]
        print(f"  Sample elevations: {sample_elevations}")
        
        try:
            graph = ox.elevation.add_edge_grades(graph, add_absolute=True)
            networks[name] = graph
            
            # Check if grades were added successfully
            edges_with_grade = [(u, v, d) for u, v, d in graph.edges(data=True) if "grade" in d and d["grade"] is not None]
            print(f"  ✓ Grades added to {len(edges_with_grade)}/{len(graph.edges)} edges")
            
            # Show sample grade values
            if edges_with_grade:
                sample_grades = [d["grade"] for u, v, d in edges_with_grade[:5]]
                print(f"  Sample grades: {sample_grades}")
        except Exception as e:
            print(f"  ✗ Failed to add grades to {name}: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"  ⚠ Skipping {name}: No elevation data available on nodes")

# %%
# Save networks to disk
for name, graph in networks.items():
    ox.save_graphml(graph, f"data/graph/lausanne_{name}_enhanced.graphml",gephi=True)
print("Saved:", ", ".join(f"lausanne_{name}_enhanced.graphml" for name in networks.keys()))

# %%
# Export networks for QGIS (GeoPackage format)
for name, graph in networks.items():
    nodes, edges = ox.graph_to_gdfs(graph)
    nodes.to_file(f"data/graph/lausanne_{name}_nodes.gpkg", layer="nodes", driver="GPKG")
    edges.to_file(f"data/graph/lausanne_{name}_edges.gpkg", layer="edges", driver="GPKG")
print("Exported GeoPackages for QGIS.")

# %%



