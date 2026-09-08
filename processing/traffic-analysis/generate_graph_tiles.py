#!/usr/bin/env python3
"""
Generate GeoJSON and/or PMTiles from a road network.

Two inputs. A GraphML file, for one city, which is what the Lausanne pipeline
uses. Or a graph store (the parquet files the backend serves areas from),
which is how the country is done: a country GeoJSON would be tens of GB in one
object, so the store is streamed as one feature per line instead.

Converts into the formats used by the frontend and backend:
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

    # the whole country, from the store
    uv run python generate_graph_tiles.py --store ../../backend/data/swiss_graph \\
        ../../frontend/public/geodata/swiss_drive.pmtiles
"""

import argparse
import json
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
            "habitat_area_m2": float(d.get("habitat_area_m2", 0.0) or 0.0),
        })
    
    # Create GeoDataFrame
    print("Creating GeoDataFrame...")
    gdf = gpd.GeoDataFrame(edges_data, crs="EPSG:4326")
    
    # Save as GeoJSON
    print(f"Writing GeoJSON to {geojson_path}...")
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"✓ GeoJSON created: {geojson_path}")


def geojson_to_pmtiles(
    geojson_path: str,
    pmtiles_path: str,
    max_zoom: str = "20",
    line_delimited: bool = False,
    tmpdir: str = None,
) -> None:
    """
    Convert GeoJSON to PMTiles using tippecanoe.

    Args:
        geojson_path: Path to input GeoJSON file
        pmtiles_path: Path to output PMTiles file
        max_zoom: Highest zoom to cut. The country stops at 14, a whole city
            street network at that zoom is already precise enough and the file
            stays reasonable.
        line_delimited: The input is one feature per line (GeoJSONSeq), which
            lets tippecanoe read it in parallel (-P). That is what the country
            store produces.
        tmpdir: Where tippecanoe spools. Its pool for the country is tens of
            GB, and /tmp is often a small tmpfs, so this defaults to the
            directory the tiles are written to.
    """
    print("Converting to PMTiles using tippecanoe...")

    command = [
        "tippecanoe",
        "-o", pmtiles_path,
        "-Z", "6",           # min zoom
        "-z", max_zoom,      # max zoom
        "-l", "graph_edges", # layer name
        "-r1",               # simplification rate
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--force",
    ]
    if line_delimited:
        command.append("-P")

    spool = writable_dir(tmpdir, Path(pmtiles_path).resolve().parent)
    command += ["-t", spool]

    command.append(geojson_path)

    try:
        subprocess.run(
            command,
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


def writable_dir(*candidates) -> str:
    """The first directory we can really write in.

    The obvious place, next to the tiles, is often a symlink to shared data or
    a read-only mount, and /tmp is often a small tmpfs that a country fills. So
    try each in turn instead of assuming.
    """
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-probe"
            probe.write_text("x")
            probe.unlink()
            return str(path)
        except OSError:
            continue
    return tempfile.gettempdir()


def store_to_geojsonseq(store_dir: str, output_path: str) -> int:
    """Write one GeoJSON feature per line from a graph store.

    Row group by row group, so a country never sits in memory at once. The
    properties are the same as the GraphML path, so the frontend reads one
    shape whatever the source.
    """
    import numpy as np
    import pyarrow.parquet as pq

    edges_file = Path(store_dir) / "edges.parquet"
    if not edges_file.exists():
        print(f"✗ no store at {store_dir} (missing edges.parquet)")
        sys.exit(1)

    parquet = pq.ParquetFile(edges_file)
    written = 0
    print(f"Streaming {edges_file} to {output_path} ...")
    with open(output_path, "w", encoding="utf-8") as out:
        # Only the columns the tiles carry: the store also holds cell, key,
        # lanes and elev_gain, which are three quarters of the bytes read.
        wanted = ["u", "v", "name", "highway", "speed_kph", "length", "travel_time", "geom_xy"]
        for group in range(parquet.num_row_groups):
            table = parquet.read_row_group(group, columns=wanted)
            columns = table.to_pydict()
            for i in range(table.num_rows):
                flat = np.asarray(columns["geom_xy"][i], dtype=float)
                if flat.size < 4:
                    continue
                # About 10 cm, and it takes a third off the file tippecanoe reads.
                coords = np.round(flat.reshape(-1, 2), 6).tolist()
                out.write(
                    json.dumps(
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": coords},
                            "properties": {
                                "u": int(columns["u"][i]),
                                "v": int(columns["v"][i]),
                                "name": columns["name"][i] or "Unknown",
                                "highway": columns["highway"][i] or "Unknown",
                                "speed_kph": float(columns["speed_kph"][i]),
                                "length": float(columns["length"][i]),
                                "travel_time": float(columns["travel_time"][i]),
                            },
                        },
                        separators=(",", ":"),
                    )
                )
                out.write("\n")
                written += 1
            if group % 100 == 0:
                print(f"  {group + 1}/{parquet.num_row_groups} cells, {written:,} edges")

    print(f"✓ {written:,} edges written")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a GraphML road network to GeoJSON and/or PMTiles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_graphml",
        nargs="?",
        help="Path to the input GraphML file (leave out when using --store)",
    )
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
    parser.add_argument(
        "--store",
        metavar="DIR",
        help="Read a graph store instead of a GraphML file (the country)",
    )
    parser.add_argument(
        "--max-zoom",
        default=None,
        help="Highest zoom to cut (default 20 for a city, 14 for a store)",
    )
    parser.add_argument(
        "--tmpdir",
        default=None,
        help="Where tippecanoe spools (default: next to the output, not /tmp)",
    )
    args = parser.parse_args()

    if args.store:
        return main_store(args)

    if not args.input_graphml:
        parser.error("give a GraphML file, or --store DIR")

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
            geojson_to_pmtiles(geojson_path, pmtiles_path, max_zoom=args.max_zoom or "20")

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


def main_store(args) -> None:
    """The country: store -> line-delimited GeoJSON -> PMTiles."""
    # With --store there is no input file, so the one positional the user gives
    # is the output. argparse cannot know that, it filled input_graphml.
    pmtiles_path = (
        args.output_pmtiles
        or args.input_graphml
        or str(Path(args.store) / "graph.pmtiles")
    )

    # The store's own directory first: the pipeline just wrote there, so it is
    # writable, and it has room. A country as one feature per line is several
    # GB, more than a /tmp tmpfs usually holds, and the tiles often land in a
    # symlink to shared data we must not write into.
    spool = writable_dir(args.tmpdir, args.store, Path(pmtiles_path).resolve().parent)

    if args.geojson:
        seq_path = args.geojson
        use_temp = False
    else:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".geojsonseq", delete=False, dir=spool)
        seq_path = tmp_file.name
        tmp_file.close()
        use_temp = True

    try:
        store_to_geojsonseq(args.store, seq_path)
        geojson_to_pmtiles(
            seq_path,
            pmtiles_path,
            max_zoom=args.max_zoom or "14",
            line_delimited=True,
            tmpdir=spool,
        )
        size = Path(pmtiles_path).stat().st_size / (1024 * 1024)
        print(f"\n  PMTiles : {size:.1f} MB  →  {pmtiles_path}")
    finally:
        if use_temp:
            Path(seq_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
