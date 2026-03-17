#!/usr/bin/env python3
"""
Enrich a Lausanne road network graph with public transport and bike infrastructure.

Bus / transit routes
--------------------
Preferred: reads a pre-filtered Lausanne OSM PBF via the ``extractosm`` package
(``extract_all_transit_routes`` + ``extract_all_transit_stops``).
Fallback:  single Overpass API request (used when no PBF is supplied).

In both cases the transit geometries are spatially joined to graph edges to set:
  bus_route_count  int  — distinct transit lines through the edge
  bus_route_refs   str  — comma-separated route refs, e.g. "2,4,M2"

Transit GeoJSON files for frontend display are optionally written to
``transit_geojson_dir``:
  transit_routes.geojson
  transit_stops.geojson

Output edge attributes
----------------------
  bus_route_count  int   Number of distinct transit lines using this edge
  bus_route_refs   str   Comma-separated route refs

Usage (standalone — requires data/lausanne-filtered.osm.pbf)
-------------------------------------------------------------
    uv run python enrich_pt_bike.py

Build the PBF first with:
    make pbf-download && make pbf-lausanne
"""

from __future__ import annotations

import json
import traceback
import urllib.parse
import urllib.request
from ast import literal_eval
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Polygon

if TYPE_CHECKING:
    import pandas as pd

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Route type → display colour (used when saving GeoJSON for frontend)
ROUTE_COLORS = {
    "subway":      "#ef4444",  # red    – M2
    "light_rail":  "#8b5cf6",  # purple – LEB
    "tram":        "#10b981",  # green
    "trolleybus":  "#f97316",  # orange
    "bus":         "#3b82f6",  # blue
}


# ---------------------------------------------------------------------------
# Internal helpers — transit GeoJSON output
# ---------------------------------------------------------------------------

def _save_transit_geojson(routes: gpd.GeoDataFrame, stops: gpd.GeoDataFrame, output_dir: Path) -> None:
    """Save transit routes and stops as GeoJSON for frontend display."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not routes.empty:
        r = routes.to_crs("EPSG:4326") if routes.crs and routes.crs.to_epsg() != 4326 else routes.copy()
        # Add a colour column for easy frontend styling
        if "colour" not in r.columns:
            route_col = _detect_col(r, ["route_type", "route", "type"])
            if route_col:
                r = r.copy()
                r["colour"] = r[route_col].map(ROUTE_COLORS).fillna(ROUTE_COLORS["bus"])
        out = output_dir / "transit_routes.geojson"
        r.to_file(str(out), driver="GeoJSON")
        print(f"  Transit routes → {out}  ({len(r)} features)")

    if not stops.empty:
        s = stops.to_crs("EPSG:4326") if stops.crs and stops.crs.to_epsg() != 4326 else stops.copy()
        out = output_dir / "transit_stops.geojson"
        s.to_file(str(out), driver="GeoJSON")
        print(f"  Transit stops  → {out}  ({len(s)} features)")


def _detect_col(gdf: gpd.GeoDataFrame, candidates: list[str]) -> str | None:
    """Return the first column name from candidates that exists in gdf."""
    for c in candidates:
        if c in gdf.columns:
            return c
    return None


# ---------------------------------------------------------------------------
# Filter to Mobilis network (Lausanne regional public transport)
# ---------------------------------------------------------------------------

def _filter_mobilis_routes(routes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only routes belonging to the Mobilis fare network."""
    if "network" not in routes.columns:
        print("  Warning: no 'network' column in routes — skipping Mobilis filter")
        return routes
    filtered = routes[routes["network"] == "Mobilis"]
    dropped = len(routes) - len(filtered)
    print(f"  Kept {len(filtered)} Mobilis routes (dropped {dropped} others)")
    return filtered


# ---------------------------------------------------------------------------
# Internal helpers — spatial join routes → graph edges
# ---------------------------------------------------------------------------

def _build_edge_gdf(graph: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    rows = []
    for u, v, data in graph.edges(data=True):
        geom = (
            data["geometry"]
            if "geometry" in data
            else LineString([
                (graph.nodes[u]["x"], graph.nodes[u]["y"]),
                (graph.nodes[v]["x"], graph.nodes[v]["y"]),
            ])
        )
        rows.append({"u": u, "v": v, "geometry": geom})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def _apply_routes_to_graph(graph: nx.MultiDiGraph, routes: gpd.GeoDataFrame) -> None:
    """Spatial join transit routes onto graph edges (buffer 8 m, UTM-32N)."""

    ref_col = _detect_col(routes, ["route_master_ref", "ref", "route_ref", "short_name", "network_ref", "name"])
    if ref_col is None:
        print("  Warning: no ref column found in routes GDF — using index as ref")
        routes = routes.copy()
        routes["_ref"] = routes.index.astype(str)
        ref_col = "_ref"

    routes_wgs = routes.to_crs("EPSG:4326") if routes.crs and routes.crs.to_epsg() != 4326 else routes

    # Buffer in UTM-32N (metric), then reproject back
    routes_proj = routes_wgs.to_crs("EPSG:32632")
    routes_buf = routes_proj.copy()
    routes_buf["geometry"] = routes_buf.geometry.buffer(8)
    routes_buf = routes_buf.to_crs("EPSG:4326")
    routes_buf["_ref"] = routes_buf[ref_col].fillna("").astype(str)

    # Exclude motorway/motorway_link — Mobilis buses never use them
    NO_BUS_HIGHWAY = {"motorway", "motorway_link"}
    motorway_edges = {
        (u, v)
        for u, v, data in graph.edges(data=True)
        if str(data.get("highway", "")).lower() in NO_BUS_HIGHWAY
    }
    edges_gdf = _build_edge_gdf(graph)
    joinable = edges_gdf[
        ~edges_gdf.apply(lambda row: (row.u, row.v) in motorway_edges, axis=1)
    ]

    joined = gpd.sjoin(
        joinable[["u", "v", "geometry"]],
        routes_buf[["geometry", "_ref"]],
        how="left",
        predicate="intersects",
    )
    # Left join produces NaN for unmatched edges; normalise to empty string
    joined["_ref"] = joined["_ref"].fillna("").astype(str)

    grouped = (
        joined.groupby(["u", "v"])["_ref"]
        .apply(lambda refs: sorted(set(r for r in refs if r)))
        .reset_index()
        .rename(columns={"_ref": "refs_list"})
    )
    grouped["bus_route_count"] = grouped["refs_list"].apply(len)
    grouped["bus_route_refs"]  = grouped["refs_list"].apply(",".join)

    bus_map: dict[tuple, tuple] = {
        (row.u, row.v): (int(row.bus_route_count), str(row.bus_route_refs))
        for row in grouped.itertuples(index=False)
    }

    bus_edge_count = 0
    for u, v, data in graph.edges(data=True):
        count, refs = bus_map.get((u, v), (0, ""))
        data["bus_route_count"] = count
        data["bus_route_refs"]  = refs
        if count > 0:
            bus_edge_count += 1

    total = graph.number_of_edges()
    print(f"  bus_route_count: {bus_edge_count:,}/{total:,} edges serve transit routes")


# ---------------------------------------------------------------------------
# PBF-based enrichment (primary path)
# ---------------------------------------------------------------------------

def _enrich_bus_from_pbf(
    graph: nx.MultiDiGraph,
    pbf_path: Path,
    transit_geojson_dir: Path | None = None,
) -> None:
    """Enrich bus routes from a local OSM PBF file via extractosm."""
    import tempfile

    try:
        from extractosm.transit import extract_all_transit_routes, extract_all_transit_stops
    except ImportError:
        print("  Warning: extractosm not installed — falling back to Overpass API")
        print("  Install with: uv add 'extractosm @ git+https://github.com/EPFL-ENAC/extractosm.git'")
        return None  # caller will fall back

    print(f"  PBF: {pbf_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        print("  Extracting transit routes (grouped by route_master) …")
        routes = extract_all_transit_routes(
            osm_pbf_path=str(pbf_path),
            output_path=str(tmp / "routes.geoparquet"),
            route_types=["bus", "tram", "subway", "trolleybus", "light_rail"],
            group_by="route_master",
        )

        print("  Extracting transit stops …")
        stops = extract_all_transit_stops(
            osm_pbf_path=str(pbf_path),
            output_path=str(tmp / "stops.geoparquet"),
        )

    routes = _filter_mobilis_routes(routes)

    route_type_col = _detect_col(routes, ["route_type", "route", "type"])
    if route_type_col:
        type_counts = routes[route_type_col].value_counts().to_dict()
        print(f"  Routes by type: {type_counts}")
    else:
        print(f"  Found {len(routes)} transit route groups, {len(stops)} stops")

    if transit_geojson_dir is not None:
        _save_transit_geojson(routes, stops, transit_geojson_dir)

    if routes.empty:
        print("  No routes found — setting bus_route_count=0 for all edges")
        for _u, _v, data in graph.edges(data=True):
            data.setdefault("bus_route_count", 0)
            data.setdefault("bus_route_refs", "")
        return

    _apply_routes_to_graph(graph, routes)
    return True  # success


# ---------------------------------------------------------------------------
# Overpass-based enrichment (fallback)
# ---------------------------------------------------------------------------

def _poly_str(polygon: Polygon) -> str:
    return " ".join(f"{lat} {lon}" for lon, lat in polygon.exterior.coords)


def _run_overpass(polygon: Polygon, timeout: int = 120) -> list[dict]:
    poly = _poly_str(polygon)
    query = (
        f"[out:json][timeout:{timeout}];\n"
        f"(\n"
        f'  relation["route"="bus"](poly:"{poly}");\n'
        f'  way["cycleway"](poly:"{poly}");\n'
        f'  way["cycleway:left"](poly:"{poly}");\n'
        f'  way["cycleway:right"](poly:"{poly}");\n'
        f'  way["cycleway:both"](poly:"{poly}");\n'
        f'  way["bicycle"="designated"](poly:"{poly}");\n'
        f");\n"
        f"out body;"
    )
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, method="POST")
    req.add_header("User-Agent", "bluecity-viz/1.0 (traffic analysis research tool)")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elements: list[dict] = payload.get("elements", [])
    print(f"  Overpass returned {len(elements)} elements")
    return elements


def _build_osmid_index(graph: nx.MultiDiGraph) -> dict[int, list[tuple[int, int]]]:
    index: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for u, v, data in graph.edges(data=True):
        raw = data.get("osmid")
        if raw is None:
            continue
        if isinstance(raw, (int, float)):
            ids = [int(raw)]
        elif isinstance(raw, list):
            ids = [int(x) for x in raw]
        else:
            s = str(raw).strip()
            try:
                ids = [int(x) for x in literal_eval(s)] if s.startswith("[") else [int(s)]
            except (ValueError, SyntaxError):
                ids = []
        for oid in ids:
            index[oid].append((u, v))
    return index


def _enrich_bus_overpass(graph: nx.MultiDiGraph, polygon: Polygon) -> None:
    """Single Overpass request for bus relations; match to graph edges by osmid."""
    print("  Querying Overpass API (bus routes, single request) …")
    try:
        elements = _run_overpass(polygon)
    except Exception:
        print("  Warning: Overpass query failed:")
        traceback.print_exc()
        print("  Setting bus_route_count=0 for all edges.")
        for _u, _v, data in graph.edges(data=True):
            data.setdefault("bus_route_count", 0)
            data.setdefault("bus_route_refs", "")
        return

    osmid_index = _build_osmid_index(graph)
    bus_ways: dict[int, set[str]] = defaultdict(set)

    for el in elements:
        if el.get("type") != "relation":
            continue
        tags = el.get("tags", {})
        if tags.get("route") != "bus":
            continue
        ref = str(tags.get("ref", "") or "").strip()
        for member in el.get("members", []):
            if member.get("type") == "way":
                bus_ways[int(member["ref"])].add(ref)

    edge_bus_refs: dict[tuple[int, int], set[str]] = defaultdict(set)
    for way_id, refs in bus_ways.items():
        for uv in osmid_index.get(way_id, []):
            edge_bus_refs[uv].update(refs)

    bus_edge_count = 0
    for u, v, data in graph.edges(data=True):
        refs = edge_bus_refs.get((u, v), set())
        data["bus_route_count"] = len(refs)
        data["bus_route_refs"]  = ",".join(sorted(refs))
        if refs:
            bus_edge_count += 1

    total = graph.number_of_edges()
    print(f"  bus_route_count: {bus_edge_count:,}/{total:,} edges serve bus routes")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_pt_bike(
    graph: nx.MultiDiGraph,
    polygon: Polygon,
    pbf_path: Path | None = None,
    transit_geojson_dir: Path | None = None,
) -> nx.MultiDiGraph:
    """
    Add bus_route_count and bus_route_refs to every graph edge.

    Args:
        graph:               OSMnx MultiDiGraph (modified in-place).
        polygon:             Shapely polygon matching the download area (lon/lat).
        pbf_path:            Path to a pre-filtered Lausanne OSM PBF file.
                             If None or missing, falls back to Overpass API.
        transit_geojson_dir: Directory where transit_routes.geojson and
                             transit_stops.geojson will be written (for frontend).

    Returns:
        The same graph with new edge attributes.
    """
    if pbf_path is not None and Path(pbf_path).exists():
        result = _enrich_bus_from_pbf(graph, Path(pbf_path), transit_geojson_dir)
        if result is None:
            # extractosm not installed — fall back
            _enrich_bus_overpass(graph, polygon)
    else:
        if pbf_path is not None:
            print(f"  PBF not found at {pbf_path} — falling back to Overpass API")
        _enrich_bus_overpass(graph, polygon)

    return graph


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    import osmnx as ox
    from shapely import wkt

    LAUSANNE_HULL_WKT = (
        "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
        "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
        "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
        "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
        "6.7016307 46.4999401, 6.6973149 46.4991489))"
    )

    graphml_path = Path("data/graph/lausanne_drive.graphml")
    pbf_path     = Path("data/lausanne-filtered.osm.pbf")
    geojson_dir  = Path("../../frontend/public/geodata")

    if not graphml_path.exists():
        print(f"GraphML not found at {graphml_path}. Run lausanne_network.py first.")
        sys.exit(1)
    if not pbf_path.exists():
        print(f"PBF not found at {pbf_path}. Run: make pbf-download && make pbf-lausanne")
        sys.exit(1)

    print("Loading graph …")
    G = ox.load_graphml(str(graphml_path))
    hull = wkt.loads(LAUSANNE_HULL_WKT)

    print("\nEnriching …")
    G = enrich_pt_bike(G, hull, pbf_path=pbf_path, transit_geojson_dir=geojson_dir)

    out_path = graphml_path.with_stem(graphml_path.stem + "_enriched")
    ox.save_graphml(G, str(out_path))
    print(f"\nSaved → {out_path}")
