#!/usr/bin/env python3
"""Build the Swiss road network and write it as a graph store.

The scenario workbench used to run on Lausanne only. It now runs on any circle
the user draws in Switzerland, so the backend needs the whole country. A
country graph is about a million edges: too big to hold as a routing graph, so
it is written as two parquet files cut in grid cells, and the backend reads
only the cells under the circle. See backend/app/services/graph_store.py.

    make pbf-download          # once, ~520 MB from Geofabrik
    make swiss-all             # elevation, then this script, then the tiles

Why it builds in tiles
----------------------

osmnx cannot hold the country at once. Feeding it the national XML takes more
than 20 GB and the kernel kills it. So the country is cut in tiles and each one
is built on its own, then the pieces are put together.

Each tile is built on a rectangle a bit larger than the piece it keeps. The
margin matters: osmnx merges chains of degree-2 nodes into one edge, and a
chain cut at a boundary would give a street that stops in the middle of
nowhere. With a margin the chain is whole inside the build rectangle.

A node belongs to exactly one core rectangle (the test is half open), and an
edge belongs to the core of its start node, so no piece is written twice and
none is lost.

Steps:

  1. osmium keeps the ways a car can drive on, the same set osmnx's "drive"
     filter keeps, once for the whole country.
  2. per tile: osmium cuts the rectangle, osmnx builds and simplifies it,
     speeds, travel times and street counts are added, node elevations are
     read from the DEM, and the arrays of the core are kept.
  3. the pieces are stacked and the store is written once.

Each tile is cached in the work directory, so a run that dies picks up where
it stopped instead of starting over.

Use --bbox to try the whole thing on a small region first, it takes minutes
instead of an hour.
"""

import argparse
import gc
import shutil
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
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

# The country, with a little air around it.
SWITZERLAND = (5.85, 45.75, 10.65, 47.95)

# 4 by 3 tiles is about 1.2° by 0.7° each, which osmnx builds in a few GB.
DEFAULT_TILES = "4x3"
# About 6 km at this latitude. Longer than any chain of degree-2 nodes.
DEFAULT_MARGIN_DEG = 0.08

# Switzerland goes from 193 m (Lake Maggiore) to 4634 m (Dufourspitze). Outside
# that it is the raster's nodata sentinel, which is 3.4e38 on swissALTIRegio.
MIN_ELEVATION_M, MAX_ELEVATION_M = -100.0, 5000.0


def run(command: list, quiet: bool = False) -> None:
    if not quiet:
        print("  $", " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        raise SystemExit(f"{tool} not found. See the Makefile help for how to install it.")


def filter_drive_ways(pbf: Path, work: Path) -> Path:
    """The country PBF, cut down to the ways a car can drive on."""
    need("osmium")
    work.mkdir(parents=True, exist_ok=True)
    filtered = work / "drive.osm.pbf"
    if filtered.exists():
        print(f"Reusing {filtered} ({filtered.stat().st_size / 1e6:.0f} MB)")
        return filtered

    run(
        [
            "osmium",
            "tags-filter",
            pbf,
            f"w/highway={','.join(DRIVE_HIGHWAYS)}",
            "-o",
            filtered,
            "--overwrite",
        ]
    )
    print(f"  drivable ways: {filtered.stat().st_size / 1e6:.0f} MB")
    return filtered


def tile_boxes(bbox, cols: int, rows: int, margin: float) -> list:
    """(core, build) rectangles. The cores tile the box exactly."""
    minlon, minlat, maxlon, maxlat = bbox
    width = (maxlon - minlon) / cols
    height = (maxlat - minlat) / rows
    boxes = []
    for row in range(rows):
        for col in range(cols):
            core = (
                minlon + col * width,
                minlat + row * height,
                minlon + (col + 1) * width,
                minlat + (row + 1) * height,
            )
            build = (
                max(minlon - margin, core[0] - margin),
                max(minlat - margin, core[1] - margin),
                min(maxlon + margin, core[2] + margin),
                min(maxlat + margin, core[3] + margin),
            )
            boxes.append((core, build))
    return boxes


def tile_graph(drive_pbf: Path, work: Path, build_box) -> nx.MultiDiGraph:
    """Build one tile. None when the rectangle holds no road at all."""
    xml = work / "tile.osm"
    clipped = work / "tile.osm.pbf"
    run(
        [
            "osmium",
            "extract",
            "-b",
            ",".join(f"{v:.4f}" for v in build_box),
            drive_pbf,
            "-o",
            clipped,
            "--overwrite",
        ],
        quiet=True,
    )
    run(["osmium", "cat", clipped, "-o", xml, "--overwrite"], quiet=True)

    try:
        # retain_all: a tile is a window on the country, so a road that leaves
        # it looks disconnected here and must not be dropped. The area builder
        # takes the main component per area anyway.
        graph = ox.graph_from_xml(xml, bidirectional=False, simplify=True, retain_all=True)
    except Exception as error:
        print(f"    nothing to build here ({error})")
        return None
    finally:
        xml.unlink(missing_ok=True)
        clipped.unlink(missing_ok=True)

    if len(graph.nodes) == 0:
        return None

    graph = ox.routing.add_edge_speeds(graph)
    graph = ox.routing.add_edge_travel_times(graph)
    counts = ox.stats.count_streets_per_node(graph)
    nx.set_node_attributes(graph, values=counts, name="street_count")
    return graph


def clean_elevation(value) -> float:
    """A real height, or 0 when the raster had nothing there."""
    if value is None:
        return 0.0
    value = float(value)
    if value != value or not (MIN_ELEVATION_M <= value <= MAX_ELEVATION_M):
        return 0.0
    return value


def rasters_in(dem: str) -> list:
    if not dem:
        return []
    path = Path(dem)
    found = sorted(str(f) for f in path.glob("*.tif")) if path.is_dir() else [str(path)]
    return [f for f in found if Path(f).exists()]


def add_elevation(graph: nx.MultiDiGraph, rasters: list, dem_crs: str) -> nx.MultiDiGraph:
    """Node elevations from DEM rasters. No raster means flat ground.

    The rasters are in the Swiss projection, so the graph is projected to it,
    read, and the values copied back onto the WGS84 graph. Same dance as
    lausanne_network.py.
    """
    if not rasters:
        for _node, data in graph.nodes(data=True):
            data["elevation"] = 0.0
        return graph

    projected = ox.projection.project_graph(graph, to_crs=dem_crs)
    # One file goes in as a path. Handing osmnx a list of one makes it build a
    # VRT, and rio-vrt cannot merge a single raster (min() on one bound).
    source = rasters[0] if len(rasters) == 1 else rasters
    projected = ox.elevation.add_node_elevations_raster(projected, source, cpus=1)
    for node_id, data in projected.nodes(data=True):
        graph.nodes[node_id]["elevation"] = clean_elevation(data.get("elevation"))
    del projected
    return graph


def core_arrays(graph: nx.MultiDiGraph, core) -> tuple:
    """The part of a tile it keeps: nodes inside the core, edges starting there.

    The core test is half open, so two neighbouring tiles never claim the same
    node and no node falls between them.
    """
    nodes, edges, geometry = arrays_from_graph(graph)
    minlon, minlat, maxlon, maxlat = core

    x, y = nodes["x"], nodes["y"]
    inside = (x >= minlon) & (x < maxlon) & (y >= minlat) & (y < maxlat)
    kept_ids = set(int(n) for n in nodes["node_id"][inside])

    nodes = {name: values[inside] for name, values in nodes.items()}

    starts_here = np.fromiter(
        (int(u) in kept_ids for u in edges["u"]), dtype=bool, count=len(edges["u"])
    )
    picked = np.flatnonzero(starts_here)
    edges = {
        name: (
            values[starts_here] if isinstance(values, np.ndarray) else [values[i] for i in picked]
        )
        for name, values in edges.items()
    }
    geometry = [geometry[i] for i in picked]
    return nodes, edges, geometry


def save_tile(path: Path, nodes: dict, edges: dict, geometry: list) -> None:
    """Cache one tile, so a run that dies does not start over."""
    flat = np.concatenate([g.reshape(-1) for g in geometry]) if geometry else np.zeros(0, "f4")
    offsets = np.zeros(len(geometry) + 1, dtype=np.int64)
    for i, g in enumerate(geometry):
        offsets[i + 1] = offsets[i] + g.size
    payload = {f"node_{k}": v for k, v in nodes.items()}
    payload.update(
        {
            f"edge_{k}": (v if isinstance(v, np.ndarray) else np.array(v, dtype=object))
            for k, v in edges.items()
        }
    )
    payload["geom_flat"] = flat.astype(np.float32)
    payload["geom_offsets"] = offsets
    np.savez_compressed(path, **payload)


def load_tile(path: Path) -> tuple:
    data = np.load(path, allow_pickle=True)
    nodes = {k[5:]: data[k] for k in data.files if k.startswith("node_")}
    edges = {k[5:]: data[k] for k in data.files if k.startswith("edge_")}
    flat, offsets = data["geom_flat"], data["geom_offsets"]
    geometry = [flat[offsets[i] : offsets[i + 1]].reshape(-1, 2) for i in range(len(offsets) - 1)]
    return nodes, edges, geometry


def stack(pieces: list) -> tuple:
    """Put the tiles together, and drop edges whose far end we never saw."""
    nodes = {name: np.concatenate([p[0][name] for p in pieces]) for name in pieces[0][0]}
    edges = {}
    for name in pieces[0][1]:
        values = [p[1][name] for p in pieces]
        if isinstance(values[0], np.ndarray) and values[0].dtype != object:
            edges[name] = np.concatenate(values)
        else:
            edges[name] = [item for part in values for item in part]
    geometry = [g for p in pieces for g in p[2]]

    known = set(int(n) for n in nodes["node_id"])
    keep = np.fromiter(
        (int(u) in known and int(v) in known for u, v in zip(edges["u"], edges["v"])),
        dtype=bool,
        count=len(edges["u"]),
    )
    dropped = int((~keep).sum())
    if dropped:
        # A street leaving the built box: its far end is outside the country,
        # or in a tile that had nothing.
        print(f"  dropped {dropped:,} streets that leave the built area")
        picked = np.flatnonzero(keep)
        edges = {
            name: (
                values[keep]
                if isinstance(values, np.ndarray) and values.dtype != object
                else [values[i] for i in picked]
            )
            for name, values in edges.items()
        }
        geometry = [geometry[i] for i in picked]
    return nodes, edges, geometry


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
        "--tiles",
        default=DEFAULT_TILES,
        help=f"how many tiles, COLSxROWS (default {DEFAULT_TILES}). More tiles, less memory.",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=DEFAULT_MARGIN_DEG,
        help="degrees built around each tile so simplification is not cut",
    )
    parser.add_argument(
        "--fresh", action="store_true", help="ignore the cached tiles and build them again"
    )
    args = parser.parse_args()

    started = time.perf_counter()
    bbox = tuple(float(v) for v in args.bbox.split(",")) if args.bbox else SWITZERLAND
    cols, rows = (int(v) for v in args.tiles.lower().split("x"))

    work = Path(args.work)
    cache = work / "tiles"
    cache.mkdir(parents=True, exist_ok=True)
    if args.fresh:
        for old in cache.glob("*.npz"):
            old.unlink()

    drive_pbf = filter_drive_ways(Path(args.pbf), work)
    rasters = rasters_in(args.dem)
    print(f"{len(rasters)} elevation raster(s)" if rasters else "No elevation raster, flat ground")

    boxes = tile_boxes(bbox, cols, rows, args.margin)
    print(f"{len(boxes)} tiles over {bbox}")

    pieces = []
    for i, (core, build) in enumerate(boxes, start=1):
        cached = cache / f"tile_{i:03d}.npz"
        if cached.exists():
            nodes, edges, geometry = load_tile(cached)
            print(
                f"[{i}/{len(boxes)}] cached: {len(nodes['node_id']):,} nodes, "
                f"{len(edges['u']):,} streets"
            )
            pieces.append((nodes, edges, geometry))
            continue

        tile_started = time.perf_counter()
        print(f"[{i}/{len(boxes)}] building {tuple(round(v, 2) for v in core)} ...")
        graph = tile_graph(drive_pbf, work, build)
        if graph is None:
            save_tile(cached, *core_arrays(nx.MultiDiGraph(), core))
            continue

        graph = add_elevation(graph, rasters, args.dem_crs)
        nodes, edges, geometry = core_arrays(graph, core)
        del graph
        gc.collect()

        save_tile(cached, nodes, edges, geometry)
        pieces.append((nodes, edges, geometry))
        print(
            f"    {len(nodes['node_id']):,} nodes, {len(edges['u']):,} streets, "
            f"{time.perf_counter() - tile_started:.0f} s"
        )

    pieces = [p for p in pieces if len(p[0]["node_id"])]
    if not pieces:
        raise SystemExit("no road found anywhere, check the box and the PBF")

    print("Putting the tiles together ...")
    nodes, edges, geometry = stack(pieces)
    del pieces
    gc.collect()

    print(f"Writing the store to {args.store} ...")
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
