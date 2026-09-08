#!/usr/bin/env python3
"""Build the Swiss road network and write it as a graph store.

The scenario workbench used to run on Lausanne only. It now runs on any circle
the user draws in Switzerland, so the backend needs the whole country. A
country graph is about a million edges: too big to hold as a routing graph, so
it is written as two parquet files cut in grid cells, and the backend reads
only the cells under the circle. See backend/app/services/graph_store.py.

    make pbf-download          # once, ~700 MB from Geofabrik
    make dem                   # once, the elevation raster
    make swiss-store           # this script, about an hour and 16 GB of RAM

Steps:

  1. osmium keeps the ways a car can drive on, the same set osmnx's "drive"
     filter keeps, and writes them as OSM XML.
  2. osmnx builds the graph from that XML and simplifies it.
  3. speeds, travel times and street counts are added, the same way the
     Lausanne pipeline does it.
  4. node elevations come from the DEM raster, when there is one.
  5. the store is written straight from the graph, no GraphML in between: the
     XML for a country is already several GB and one big file is enough.

Use --bbox to try the whole thing on a small region first, it takes minutes
instead of an hour.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx
import osmnx as ox

# The store writer lives with its reader, in the backend, so the two cannot
# drift apart on the schema.
BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.graph_store import Grid, write_store  # noqa: E402

sys.path.insert(0, str(BACKEND / "scripts"))
from graphml_to_store import arrays_from_graph  # noqa: E402

# What a car can drive on. This is osmnx's "drive" filter written the other way
# round: it excludes types with a regex, osmium can only keep a list, so the
# list has to be spelled out. service roads are excluded, like osmnx does.
DRIVE_HIGHWAYS = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "road",
    "busway",
]


def run(command: list) -> None:
    print("  $", " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        raise SystemExit(f"{tool} not found. See the Makefile help for how to install it.")


def extract_drive_xml(pbf: Path, work: Path, bbox=None) -> Path:
    """PBF of the country -> OSM XML of the drivable ways only."""
    need("osmium")
    work.mkdir(parents=True, exist_ok=True)
    source = pbf

    if bbox:
        clipped = work / "clipped.osm.pbf"
        run(["osmium", "extract", "-b", ",".join(str(v) for v in bbox), source, "-o", clipped,
             "--overwrite"])
        source = clipped

    filtered = work / "drive.osm.pbf"
    run([
        "osmium",
        "tags-filter",
        source,
        f"w/highway={','.join(DRIVE_HIGHWAYS)}",
        "-o",
        filtered,
        "--overwrite",
    ])

    xml = work / "drive.osm"
    run(["osmium", "cat", filtered, "-o", xml, "--overwrite"])
    print(f"  XML: {xml.stat().st_size / 1e9:.1f} GB")
    return xml


def build_graph(xml: Path) -> nx.MultiDiGraph:
    """The simplified drive graph, with the attributes the backend reads."""
    print("Building the graph (this is the long step) ...")
    graph = ox.graph_from_xml(xml, bidirectional=False, simplify=True, retain_all=False)
    print(f"  {len(graph.nodes):,} nodes, {len(graph.edges):,} edges")

    print("Adding speeds and travel times ...")
    graph = ox.routing.add_edge_speeds(graph)
    graph = ox.routing.add_edge_travel_times(graph)

    # street_count is what the OD sampler uses to tell a junction from a bend,
    # so it must be right after the simplification.
    print("Counting streets per node ...")
    counts = ox.stats.count_streets_per_node(graph)
    nx.set_node_attributes(graph, values=counts, name="street_count")
    return graph


def add_elevation(graph: nx.MultiDiGraph, dem: str, dem_crs: str) -> nx.MultiDiGraph:
    """Node elevations from DEM rasters. No raster means flat ground.

    The rasters are in the Swiss projection, so the graph is projected to it,
    read, and the values copied back onto the WGS84 graph. Same dance as
    lausanne_network.py.
    """
    rasters = []
    if dem:
        path = Path(dem)
        rasters = sorted(str(f) for f in path.glob("*.tif")) if path.is_dir() else [str(path)]
        rasters = [f for f in rasters if Path(f).exists()]

    if not rasters:
        print("No elevation raster, elevations stay at 0 (CO2 ignores the slope).")
        for _node, data in graph.nodes(data=True):
            data["elevation"] = 0.0
        return graph

    print(f"Reading elevations from {len(rasters)} raster(s) ...")
    projected = ox.projection.project_graph(graph, to_crs=dem_crs)
    projected = ox.elevation.add_node_elevations_raster(projected, rasters, cpus=1)
    for node_id, data in projected.nodes(data=True):
        value = data.get("elevation")
        graph.nodes[node_id]["elevation"] = 0.0 if value is None or value != value else float(value)

    missing = sum(1 for _n, d in graph.nodes(data=True) if d["elevation"] == 0.0)
    print(f"  {len(graph.nodes) - missing:,} nodes got an elevation")
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", required=True, help="Switzerland OSM PBF from Geofabrik")
    parser.add_argument("--store", required=True, help="output store directory")
    parser.add_argument(
        "--dem", default=None, help="elevation raster, a GeoTIFF or a directory of them"
    )
    parser.add_argument("--dem-crs", default="EPSG:2056", help="CRS of the rasters")
    parser.add_argument("--work", default=".data/swiss", help="scratch directory")
    parser.add_argument(
        "--bbox",
        default=None,
        help="minlon,minlat,maxlon,maxlat, to try the pipeline on a small region",
    )
    parser.add_argument(
        "--graphml", default=None, help="also write the graph as GraphML (big, optional)"
    )
    args = parser.parse_args()

    started = time.perf_counter()
    bbox = [float(v) for v in args.bbox.split(",")] if args.bbox else None

    xml = extract_drive_xml(Path(args.pbf), Path(args.work), bbox)
    graph = build_graph(xml)
    graph = add_elevation(graph, args.dem, args.dem_crs)

    if args.graphml:
        print(f"Writing {args.graphml} ...")
        ox.save_graphml(graph, args.graphml)

    print(f"Writing the store to {args.store} ...")
    nodes, edges, geometry = arrays_from_graph(graph)
    index = write_store(args.store, nodes, edges, grid=Grid(), geometry=geometry)

    size = sum(f.stat().st_size for f in Path(args.store).iterdir())
    print(
        f"✓ {index['totals']['nodes']:,} nodes and {index['totals']['edges']:,} edges "
        f"in {len(index['cells'])} cells, {size / 1e6:.0f} MB, "
        f"in {(time.perf_counter() - started) / 60:.1f} min"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
