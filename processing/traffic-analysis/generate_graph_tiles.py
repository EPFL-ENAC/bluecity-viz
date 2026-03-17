#!/usr/bin/env python3
"""
Generate GeoJSON and/or PMTiles from a GraphML road network file.

Converts an OSMnx GraphML file into formats used by the frontend and backend:
  - GeoJSON  → backend/data/lausanne.geojson  (edge geometry for the API)
  - PMTiles  → frontend/public/geodata/lausanne_drive.pmtiles  (vector tiles)

Usage:
    # GraphML → PMTiles only (intermediate GeoJSON is temporary)
    uv run python generate_graph_tiles.py <input.graphml> [output.pmtiles]

    # GraphML → GeoJSON only
    uv run python generate_graph_tiles.py <input.graphml> --geojson <output.geojson>

    # GraphML → both GeoJSON and PMTiles
    uv run python generate_graph_tiles.py <input.graphml> [output.pmtiles] \\
        --geojson <output.geojson>

Examples:
    uv run python generate_graph_tiles.py data/graph/lausanne_drive.graphml
    uv run python generate_graph_tiles.py data/graph/lausanne_drive.graphml \\
        --geojson data/graph/lausanne_drive.geojson
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import LineString


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
            "bus_route_count": int(d.get("bus_route_count", 0) or 0),
            "bus_route_refs": str(d.get("bus_route_refs", "") or ""),
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
        subprocess.run(
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
                geojson_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ PMTiles created: {pmtiles_path}")

    except subprocess.CalledProcessError as e:
        print(f"✗ tippecanoe failed (exit {e.returncode})")
        if e.stderr:
            print(e.stderr.rstrip())
        sys.exit(1)
    except FileNotFoundError:
        print("✗ tippecanoe not found. Install it first:")
        print("  macOS:  brew install tippecanoe")
        print("  Linux:  https://github.com/felt/tippecanoe#installation")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a GraphML road network to GeoJSON and/or PMTiles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input_graphml", help="Path to the input GraphML file")
    parser.add_argument(
        "output_pmtiles",
        nargs="?",
        help="Path for the output PMTiles file (default: same name as input with .pmtiles)",
    )
    parser.add_argument(
        "--geojson",
        metavar="PATH",
        help="Also persist the intermediate GeoJSON to this path",
    )
    args = parser.parse_args()

    graphml_path = args.input_graphml
    want_tiles = args.output_pmtiles is not None
    want_geojson = args.geojson is not None

    # If neither flag is given, default to tiles (backward-compatible).
    if not want_tiles and not want_geojson:
        want_tiles = True

    pmtiles_path = args.output_pmtiles or str(Path(graphml_path).with_suffix(".pmtiles"))

    # Use a persistent GeoJSON path when requested; otherwise a temp file.
    if want_geojson:
        geojson_path = args.geojson
        use_temp = False
    else:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
        geojson_path = tmp_file.name
        tmp_file.close()
        use_temp = True

    try:
        # Step 1: GraphML → GeoJSON
        graphml_to_geojson(graphml_path, geojson_path)

        # Step 2: GeoJSON → PMTiles (skipped when only GeoJSON was requested)
        if want_tiles:
            geojson_to_pmtiles(geojson_path, pmtiles_path)

        # Summary
        graphml_size = Path(graphml_path).stat().st_size / (1024 * 1024)
        print(f"\n  GraphML : {graphml_size:.1f} MB")
        if want_geojson:
            geojson_size = Path(geojson_path).stat().st_size / (1024 * 1024)
            print(f"  GeoJSON : {geojson_size:.1f} MB  →  {geojson_path}")
        if want_tiles:
            pmtiles_size = Path(pmtiles_path).stat().st_size / (1024 * 1024)
            print(
                f"  PMTiles : {pmtiles_size:.1f} MB"
                f"  ({(1 - pmtiles_size / graphml_size) * 100:.0f}% smaller than GraphML)"
            )

    finally:
        if use_temp:
            Path(geojson_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
