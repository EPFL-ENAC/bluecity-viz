#!/usr/bin/env python3
"""Check a graph store against the Lausanne GraphML.

The country store comes from a different pipeline than data/lausanne.graphml:
osmium picks the ways by their highway tag, osmnx picks them with its own
"drive" filter. This cuts the same circle out of both and compares them.

    uv run python scripts/lausanne_parity.py data/swiss_graph
    uv run python scripts/lausanne_parity.py data/swiss_graph --lon 6.633 --lat 46.52 -r 2500

Two things can make the two disagree, and they need different answers:

  * a wrong filter, which shows up as road types the store should not hold at
    all (service, footway, track, path). That is a bug in build_swiss_graph.py
    and this script fails on it whatever the counts say.
  * OSM drift, because the GraphML was built from an older snapshot of the map.
    That shows up as the same road types on both sides, on nodes the other side
    has never heard of. A few percent is normal and this script says so.

So the strict check is on the road types and on the total road length, not on
the raw edge count.
"""

import argparse
import collections
import sys
from pathlib import Path

import numpy as np
import osmnx as ox
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.area_builder import AreaSpec, select  # noqa: E402
from app.services.graph_store import GraphStore, distance_m  # noqa: E402

# Middle of Lausanne, a circle the tool would really be used on.
DEFAULT_LON, DEFAULT_LAT, DEFAULT_RADIUS = 6.633, 46.52, 2500.0

# What a car drives on. Anything else in the store means the osmium filter in
# build_swiss_graph.py let something through.
DRIVE_HIGHWAYS = {
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
}


def tag(value) -> str:
    """One highway value, whatever shape osmnx gave it."""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value)


def from_graphml(path: str, lon: float, lat: float, radius_m: float) -> tuple:
    """The same circle cut out of the GraphML: nodes, edges and total length."""
    graph = ox.load_graphml(path)
    xs = np.array([float(d["x"]) for _n, d in graph.nodes(data=True)])
    ys = np.array([float(d["y"]) for _n, d in graph.nodes(data=True)])
    ids = np.array(list(graph.nodes()), dtype=np.int64)

    all_nodes = set(int(n) for n in ids)
    keep = set(int(n) for n in ids[distance_m(xs, ys, lon, lat) <= radius_m])

    # Two views on purpose. The dict collapses parallel edges, which is what a
    # (u, v) comparison needs. The length has to add them all up, or it is not
    # the same quantity as the store's column.
    edges = {}
    total_m = 0.0
    for u, v, data in graph.edges(data=True):
        if u in keep and v in keep:
            edges[(int(u), int(v))] = data
            total_m += float(data.get("length") or 0)
    return all_nodes, keep, edges, total_m


def highway_of_store(store_dir: str) -> dict:
    """(u, v) -> highway, read straight from the parquet."""
    table = pq.read_table(Path(store_dir) / "edges.parquet", columns=["u", "v", "highway"])
    return dict(
        zip(
            zip(table["u"].to_pylist(), table["v"].to_pylist()),
            table["highway"].to_pylist(),
        )
    )


def line(label: str, store_value, graphml_value, unit: str = "") -> float:
    """One comparison line. Returns the relative difference."""
    if graphml_value:
        diff = (store_value - graphml_value) / graphml_value
    else:
        diff = 0.0 if not store_value else 1.0
    left = f"{store_value:,.0f}{unit}"
    right = f"{graphml_value:,.0f}{unit}"
    print(f"  {label:18} store {left:>12}   graphml {right:>12}   {diff * 100:+.1f}%")
    return diff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", help="the graph store directory")
    parser.add_argument("--graphml", default="data/lausanne.graphml")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("-r", "--radius", type=float, default=DEFAULT_RADIUS)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.15,
        help="allowed difference on the total road length (default 15%%)",
    )
    args = parser.parse_args()

    if not Path(args.graphml).exists():
        raise SystemExit(f"{args.graphml} not found")

    store = GraphStore.open(args.store)
    spec = AreaSpec.from_circle(args.lon, args.lat, args.radius)
    selection = select(store, spec)
    store_edges = set(zip(selection.edges["u"].tolist(), selection.edges["v"].tolist()))
    store_highway = highway_of_store(args.store)

    all_graphml_nodes, graphml_nodes, graphml_edges, graphml_m = from_graphml(
        args.graphml, args.lon, args.lat, args.radius
    )

    print(f"Circle {args.radius / 1000:.1f} km around {args.lat}, {args.lon}")
    line("nodes", len(selection.node_id), len(graphml_nodes))
    line("edges", len(store_edges), len(graphml_edges))

    # Both sides count every parallel edge, so the two numbers mean the same.
    store_km = float(selection.edges["length"].sum()) / 1000
    length_diff = line("road length", store_km, graphml_m / 1000, " km")

    # The strict check: nothing a car cannot drive on.
    strays = collections.Counter(
        highway
        for edge in store_edges
        if (highway := store_highway.get(edge, "")) not in DRIVE_HIGHWAYS
    )
    print()
    if strays:
        print("  FAIL road types the store should not hold:")
        for highway, count in strays.most_common(10):
            print(f"    {highway or '(empty)':20} {count:,}")
    else:
        print("  OK   every street in the store is a road type a car drives on")

    # Tell drift apart from a filter problem.
    only_store = store_edges - set(graphml_edges)
    only_graphml = set(graphml_edges) - store_edges
    drift = sum(
        1 for u, v in only_store if u not in all_graphml_nodes or v not in all_graphml_nodes
    )
    print(
        f"  {len(only_store):,} streets only in the store, "
        f"{len(only_graphml):,} only in the GraphML"
    )
    if only_store:
        share = drift / len(only_store)
        print(
            f"  {drift:,} of them ({share * 100:.0f}%) touch a node the GraphML never had, "
            "so they are map edits since it was built, not a filter difference"
        )
    print(
        "  store-only types:  ",
        collections.Counter(store_highway.get(e, "?") for e in only_store).most_common(6),
    )
    print(
        "  graphml-only types:",
        collections.Counter(tag(graphml_edges[e].get("highway")) for e in only_graphml).most_common(
            6
        ),
    )

    ok = not strays and abs(length_diff) <= args.tolerance
    print()
    if ok:
        print("✓ the two extractions agree")
    elif strays:
        print("✗ the osmium filter in build_swiss_graph.py lets the wrong ways through")
    else:
        print(
            f"✗ the road length differs by {length_diff * 100:+.1f}%, more than "
            f"{args.tolerance * 100:.0f}%. Too much for map edits alone, check the filter."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
