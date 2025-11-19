#!/usr/bin/env python3
"""
Generate PMTiles from GraphML file for traffic analysis visualization.

This script converts a GraphML road network file to PMTiles format for efficient
web visualization. The PMTiles format allows for fast, viewport-based loading
of large road networks.

Usage:
    python generate_graph_tiles.py <input_graphml> <output_pmtiles>

Example:
    python generate_graph_tiles.py data/graph/lausanne_drive.graphml data/graph/lausanne_drive.pmtiles
"""

import osmnx as ox
import geopandas as gpd
from shapely.geometry import LineString
import subprocess
import sys
from pathlib import Path
import tempfile


def graphml_to_geojson(graphml_path: str, geojson_path: str) -> None:
    """
    Convert GraphML to GeoJSON.
    
    Args:
        graphml_path: Path to input GraphML file
        geojson_path: Path to output GeoJSON file
    """
    print(f"Loading graph from {graphml_path}...")
    graph = ox.load_graphml(graphml_path)
    
    # Ensure graph has speed and travel time attributes
    if not any("speed_kph" in d for _, _, d in graph.edges(data=True)):
        print("Adding edge speeds...")
        graph = ox.routing.add_edge_speeds(graph)
    if not any("travel_time" in d for _, _, d in graph.edges(data=True)):
        print("Adding travel times...")
        graph = ox.routing.add_edge_travel_times(graph)
    
    print(f"Processing {len(graph.edges)} edges...")
    
    # Convert edges to GeoDataFrame
    edges_data = []
    for u, v, d in graph.edges(data=True):
        # Build geometry
        if "geometry" in d:
            geom = d["geometry"]
        else:
            # Create line from node coordinates
            u_coords = (graph.nodes[u]["x"], graph.nodes[u]["y"])
            v_coords = (graph.nodes[v]["x"], graph.nodes[v]["y"])
            geom = LineString([u_coords, v_coords])
        
        # Get metadata
        name_raw = d.get("name")
        if isinstance(name_raw, list):
            name = name_raw[0] if name_raw else "Unknown"
        elif name_raw:
            name = str(name_raw)
        else:
            name = "Unknown"
        
        highway_raw = d.get("highway", "Unknown")
        highway = highway_raw[0] if isinstance(highway_raw, list) else highway_raw
        
        edges_data.append({
            "geometry": geom,
            "u": int(u),
            "v": int(v),
            "name": name,
            "highway": highway,
            "speed_kph": float(d.get("speed_kph", 0)),
            "length": float(d.get("length", 0)),
            "travel_time": float(d.get("travel_time", 0)),
        })
    
    # Create GeoDataFrame
    print("Creating GeoDataFrame...")
    gdf = gpd.GeoDataFrame(edges_data, crs="EPSG:4326")
    
    # Save as GeoJSON
    print(f"Writing GeoJSON to {geojson_path}...")
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"✓ GeoJSON created: {geojson_path}")


def geojson_to_pmtiles(geojson_path: str, pmtiles_path: str) -> None:
    """
    Convert GeoJSON to PMTiles using tippecanoe.
    
    Args:
        geojson_path: Path to input GeoJSON file
        pmtiles_path: Path to output PMTiles file
    """
    print(f"Converting to PMTiles using tippecanoe...")
    
    try:
        result = subprocess.run(
            [
                "tippecanoe",
                "-o", pmtiles_path,
                "-Z", "6",           # min zoom
                "-z", "20",          # max zoom
                "-l", "graph_edges", # layer name
                "-r1",               # simplification rate
                "--drop-densest-as-needed",
                "--extend-zooms-if-still-dropping",
                "--force",
                geojson_path
            ],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✓ PMTiles created: {pmtiles_path}")
        print(f"  Tippecanoe output: {result.stderr}")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error running tippecanoe: {e}")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("✗ Error: tippecanoe not found. Please install it:")
        print("  macOS:  brew install tippecanoe")
        print("  Linux:  See https://github.com/felt/tippecanoe#installation")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_graph_tiles.py <input_graphml> [output_pmtiles]")
        print("\nExample:")
        print("  python generate_graph_tiles.py data/graph/lausanne_drive.graphml")
        sys.exit(1)
    
    graphml_path = sys.argv[1]
    
    # Determine output path
    if len(sys.argv) >= 3:
        pmtiles_path = sys.argv[2]
    else:
        # Default: replace .graphml with .pmtiles
        pmtiles_path = str(Path(graphml_path).with_suffix(".pmtiles"))
    
    # Create temporary GeoJSON file
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
        geojson_path = tmp.name
    
    try:
        # Step 1: GraphML -> GeoJSON
        graphml_to_geojson(graphml_path, geojson_path)
        
        # Step 2: GeoJSON -> PMTiles
        geojson_to_pmtiles(geojson_path, pmtiles_path)
        
        print(f"\n✓ Success! PMTiles file created at: {pmtiles_path}")
        
        # Print file sizes
        graphml_size = Path(graphml_path).stat().st_size / (1024 * 1024)
        pmtiles_size = Path(pmtiles_path).stat().st_size / (1024 * 1024)
        print(f"  GraphML size:  {graphml_size:.2f} MB")
        print(f"  PMTiles size:  {pmtiles_size:.2f} MB")
        print(f"  Compression:   {(1 - pmtiles_size/graphml_size) * 100:.1f}% reduction")
        
    finally:
        # Clean up temporary GeoJSON
        Path(geojson_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
