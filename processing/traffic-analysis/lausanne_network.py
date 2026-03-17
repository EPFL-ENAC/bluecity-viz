#!/usr/bin/env python3
"""
Build the Lausanne road network graph for traffic analysis.

Downloads the OSM drive network for the Lausanne region, enriches it with
edge speeds, travel times, and optionally Swiss ALTI3D elevation data, then
saves the result as a GraphML file consumed by the backend and the tile
generation pipeline.

Usage:
    uv run python lausanne_network.py                   # full pipeline
    uv run python lausanne_network.py --no-elevation    # skip elevation step
    uv run python lausanne_network.py --output data/graph/lausanne_drive.graphml

Outputs:
    data/graph/lausanne_drive.graphml   – enriched road network (backend input)
    data/graph/lausanne_drive_nodes.gpkg
    data/graph/lausanne_drive_edges.gpkg  (QGIS-ready GeoPackages)
"""

import argparse
import glob
import traceback
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd
from shapely import wkt
from shapely.geometry import Polygon

from enrich_pt_bike import enrich_pt_bike

# ---------------------------------------------------------------------------
# Lausanne bounding polygon (WGS84 / EPSG:4326)
# ---------------------------------------------------------------------------

LAUSANNE_HULL_WKT = (
    "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
    "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
    "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
    "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
    "6.7016307 46.4999401, 6.6973149 46.4991489))"
)

DEFAULT_OUTPUT = Path("data/graph/lausanne_drive.graphml")
ELEVATION_DIR = Path("data/elevation")


# ---------------------------------------------------------------------------
# Step 1 — Load or download the OSM network
# ---------------------------------------------------------------------------

def load_or_download_network(output_path: Path) -> nx.MultiDiGraph:
    """
    Return the drive network for the Lausanne hull polygon.

    If *output_path* already exists on disk the graph is loaded from that
    file; otherwise it is downloaded from OpenStreetMap and the caller is
    responsible for saving it afterwards.

    Args:
        output_path: Path where the GraphML file lives (or will be saved).

    Returns:
        An OSMnx MultiDiGraph for the Lausanne drive network.
    """
    if output_path.exists():
        print(f"Loading existing network from {output_path} …")
        return ox.load_graphml(output_path)

    print("Downloading drive network from OpenStreetMap …")
    hull: Polygon = wkt.loads(LAUSANNE_HULL_WKT)  # type: ignore[assignment]
    graph = ox.graph_from_polygon(hull, network_type="drive")
    print(
        f"Downloaded: {len(graph.nodes):,} nodes, {len(graph.edges):,} edges, "
        f"{sum(d['length'] for _, _, d in graph.edges(data=True)) / 1000:.1f} km"
    )
    return graph


# ---------------------------------------------------------------------------
# Step 2 — Add edge speeds and travel times
# ---------------------------------------------------------------------------

def add_speeds_and_times(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Ensure every edge has *speed_kph* and *travel_time* attributes.

    OSMnx infers speed from the OSM ``maxspeed`` tag and road type when the
    tag is absent.  Travel time is derived from speed and edge length.

    Args:
        graph: Input graph (modified in-place and returned).

    Returns:
        The same graph with speed and travel-time attributes guaranteed.
    """
    edges = list(graph.edges(data=True))

    if not any("speed_kph" in d for _, _, d in edges):
        print("  Adding edge speeds …")
        graph = ox.routing.add_edge_speeds(graph)

    if not any("travel_time" in d for _, _, d in edges):
        print("  Adding travel times …")
        graph = ox.routing.add_edge_travel_times(graph)

    return graph


# ---------------------------------------------------------------------------
# Step 3 — Add node elevations from Swiss ALTI3D rasters (optional)
# ---------------------------------------------------------------------------

def add_elevation(
    graph: nx.MultiDiGraph,
    elevation_dir: Path = ELEVATION_DIR,
) -> nx.MultiDiGraph:
    """
    Enrich graph nodes with elevation data from local Swiss ALTI3D rasters.

    The rasters use the MN95 coordinate system (EPSG:2056), so the graph is
    projected before sampling and the results are copied back to the original
    WGS84 graph.

    Run ``make elevation`` (or ``uv run python download_elevation_data.py``)
    to download the raster tiles before calling this function.

    Args:
        graph:         Input graph in WGS84 (EPSG:4326).
        elevation_dir: Directory containing ``*.tif`` elevation rasters.

    Returns:
        The graph with ``elevation`` attributes added to nodes where data is
        available.  Returns the graph unchanged if no raster files are found.
    """
    raster_files = sorted(glob.glob(str(elevation_dir / "*.tif")))

    if not raster_files:
        print(
            f"  No elevation rasters found in {elevation_dir}.\n"
            "  Run 'make elevation' to download Swiss ALTI3D data first."
        )
        return graph

    print(f"  Found {len(raster_files)} raster file(s) — projecting to MN95 (EPSG:2056) …")

    try:
        # Swiss ALTI3D tiles use MN95; project the graph before sampling.
        graph_swiss = ox.project_graph(graph, to_crs="EPSG:2056")
        graph_swiss = ox.elevation.add_node_elevations_raster(
            graph_swiss,
            raster_files,
            cpus=None,  # use all available CPUs
        )

        # Copy elevations back to the original WGS84 graph.
        for node_id in graph.nodes():
            node_data = graph_swiss.nodes.get(node_id, {})
            if "elevation" in node_data:
                graph.nodes[node_id]["elevation"] = node_data["elevation"]

        valid = sum(
            1
            for _, d in graph.nodes(data=True)
            if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
        )
        print(f"  Elevation added: {valid:,}/{len(graph.nodes):,} nodes have valid data.")

        if valid > 0:
            sample = next(
                d["elevation"]
                for _, d in graph.nodes(data=True)
                if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
            )
            print(f"  Sample elevation: {sample:.1f} m")

    except Exception:
        print("  Failed to add elevation data:")
        traceback.print_exc()

    return graph


# ---------------------------------------------------------------------------
# Step 4 — Add edge grades (requires elevation)
# ---------------------------------------------------------------------------

def add_grades(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Add grade (rise / run) to each edge if elevation data is available.

    Args:
        graph: Graph with (ideally) node ``elevation`` attributes.

    Returns:
        Graph with ``grade`` and ``grade_abs`` attributes on edges that have
        elevation data on both endpoint nodes.  Returns the graph unchanged if
        no elevation data is present.
    """
    nodes_with_elevation = [
        n
        for n, d in graph.nodes(data=True)
        if "elevation" in d and d["elevation"] is not None and not pd.isna(d["elevation"])
    ]

    if not nodes_with_elevation:
        print("  No elevation data on nodes — skipping grade calculation.")
        return graph

    print(
        f"  Calculating grades "
        f"({len(nodes_with_elevation):,}/{len(graph.nodes):,} nodes have elevation) …"
    )

    try:
        graph = ox.elevation.add_edge_grades(graph, add_absolute=True)
        graded = sum(1 for _, _, d in graph.edges(data=True) if d.get("grade") is not None)
        print(f"  Grades added to {graded:,}/{len(graph.edges):,} edges.")
    except Exception:
        print("  Failed to add edge grades:")
        traceback.print_exc()

    return graph


# ---------------------------------------------------------------------------
# Step 5 — Persist outputs
# ---------------------------------------------------------------------------

def save_network(graph: nx.MultiDiGraph, output_path: Path) -> None:
    """
    Save the enriched graph as a GraphML file.

    The ``gephi=True`` flag adds extra attributes that make the file
    compatible with Gephi for visualisation.

    Args:
        graph:       Graph to save.
        output_path: Destination ``.graphml`` file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, str(output_path), gephi=True)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Saved: {output_path}  ({size_mb:.1f} MB)")


def export_geopackage(graph: nx.MultiDiGraph, output_dir: Path) -> None:
    """
    Export nodes and edges as GeoPackage files for use in QGIS.

    Args:
        graph:      Graph to export.
        output_dir: Directory where ``lausanne_drive_nodes.gpkg`` and
                    ``lausanne_drive_edges.gpkg`` will be written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes, edges = ox.graph_to_gdfs(graph)

    nodes_path = output_dir / "lausanne_drive_nodes.gpkg"
    edges_path = output_dir / "lausanne_drive_edges.gpkg"

    nodes.to_file(nodes_path, layer="nodes", driver="GPKG")
    edges.to_file(edges_path, layer="edges", driver="GPKG")
    print(f"  Exported nodes: {nodes_path}")
    print(f"  Exported edges: {edges_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Lausanne road network graph for traffic analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"GraphML output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--no-elevation",
        action="store_true",
        help="Skip Swiss ALTI3D elevation enrichment (useful for quick testing)",
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Skip public transport & bike infrastructure enrichment (faster rebuild)",
    )
    parser.add_argument(
        "--pbf",
        type=Path,
        default=None,
        help="Path to filtered Lausanne OSM PBF for transit enrichment (e.g. data/lausanne-filtered.osm.pbf). Falls back to Overpass API if not provided.",
    )
    parser.add_argument(
        "--transit-output",
        type=Path,
        default=None,
        help="Directory for transit GeoJSON output (transit_routes.geojson, transit_stops.geojson). E.g. ../../frontend/public/geodata",
    )
    parser.add_argument(
        "--no-gpkg",
        action="store_true",
        help="Skip GeoPackage export for QGIS",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("Lausanne Network Builder")
    print("=" * 60)

    n_steps = 5

    # 1. Load or download
    print(f"\n[1/{n_steps}] Network …")
    graph = load_or_download_network(args.output)

    # 2. Speeds & travel times
    print(f"\n[2/{n_steps}] Speeds & travel times …")
    graph = add_speeds_and_times(graph)

    # 3. Elevation (optional)
    if not args.no_elevation:
        print(f"\n[3/{n_steps}] Elevation …")
        graph = add_elevation(graph)
        graph = add_grades(graph)
    else:
        print(f"\n[3/{n_steps}] Elevation — skipped (--no-elevation)")

    # 4. Public transport & bike infrastructure enrichment (optional)
    if not args.no_enrichment:
        print(f"\n[4/{n_steps}] Public transport & bike infrastructure …")
        hull: Polygon = wkt.loads(LAUSANNE_HULL_WKT)  # type: ignore[assignment]
        graph = enrich_pt_bike(
            graph,
            hull,
            pbf_path=args.pbf,
            transit_geojson_dir=args.transit_output,
        )
    else:
        print(f"\n[4/{n_steps}] PT & bike enrichment — skipped (--no-enrichment)")

    # 5. Save
    print(f"\n[5/{n_steps}] Saving …")
    save_network(graph, args.output)

    if not args.no_gpkg:
        export_geopackage(graph, args.output.parent)

    print("\nDone.")
    print(f"  GraphML: {args.output}")
    print("  Next step: make tiles")


if __name__ == "__main__":
    main()
