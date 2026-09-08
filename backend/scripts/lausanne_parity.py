#!/usr/bin/env python3
"""Check a graph store against the Lausanne GraphML.

The country store comes from a different pipeline than data/lausanne.graphml:
osmium picks the ways instead of osmnx's filter, and the two can disagree. This
cuts a circle out of the store, builds the same circle from the GraphML, and
compares. If the numbers are close the extraction is right.

    uv run python scripts/lausanne_parity.py data/swiss_graph
    uv run python scripts/lausanne_parity.py data/swiss_graph --lon 6.633 --lat 46.52 -r 2500

It is a report, not a test: it prints the differences and exits 1 when they are
larger than the tolerance.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.area_builder import AreaSpec, select  # noqa: E402
from app.services.graph_store import GraphStore, distance_m  # noqa: E402

# Middle of Lausanne, a circle the tool would really be used on.
DEFAULT_LON, DEFAULT_LAT, DEFAULT_RADIUS = 6.633, 46.52, 2500.0


def from_graphml(path: str, lon: float, lat: float, radius_m: float) -> tuple:
    """The same circle cut out of the GraphML, node ids and edge pairs."""
    graph = ox.load_graphml(path)
    xs = np.array([float(d["x"]) for _n, d in graph.nodes(data=True)])
    ys = np.array([float(d["y"]) for _n, d in graph.nodes(data=True)])
    ids = np.array(list(graph.nodes()), dtype=np.int64)

    inside = ids[distance_m(xs, ys, lon, lat) <= radius_m]
    keep = set(int(n) for n in inside)
    edges = {(int(u), int(v)) for u, v in graph.edges() if u in keep and v in keep}
    return keep, edges


def report(name: str, store_value: int, graphml_value: int, tolerance: float) -> bool:
    """One line, and whether it is within tolerance."""
    if graphml_value == 0:
        ok = store_value == 0
        diff = 0.0
    else:
        diff = (store_value - graphml_value) / graphml_value
        ok = abs(diff) <= tolerance
    print(
        f"  {'OK ' if ok else 'BAD'} {name:16} store {store_value:7,}  "
        f"graphml {graphml_value:7,}  {diff * 100:+.1f}%"
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", help="the graph store directory")
    parser.add_argument("--graphml", default="data/lausanne.graphml")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("-r", "--radius", type=float, default=DEFAULT_RADIUS)
    parser.add_argument("--tolerance", type=float, default=0.05, help="allowed relative difference")
    args = parser.parse_args()

    if not Path(args.graphml).exists():
        raise SystemExit(f"{args.graphml} not found")

    store = GraphStore.open(args.store)
    spec = AreaSpec.from_circle(args.lon, args.lat, args.radius)
    selection = select(store, spec)
    store_nodes = set(int(n) for n in selection.node_id)
    store_edges = {(int(u), int(v)) for u, v in zip(selection.edges["u"], selection.edges["v"])}

    graphml_nodes, graphml_edges = from_graphml(args.graphml, args.lon, args.lat, args.radius)

    print(f"Circle {args.radius / 1000:.1f} km around {args.lat}, {args.lon}")
    ok = True
    ok &= report("nodes", len(store_nodes), len(graphml_nodes), args.tolerance)
    ok &= report("edges", len(store_edges), len(graphml_edges), args.tolerance)
    ok &= report(
        "shared edges", len(store_edges & graphml_edges), len(graphml_edges), args.tolerance
    )

    only_store = store_edges - graphml_edges
    only_graphml = graphml_edges - store_edges
    print(
        f"  {len(only_store):,} edges only in the store, {len(only_graphml):,} only in the GraphML"
    )

    lengths = selection.edges["length"]
    print(f"  total road length in the store: {lengths.sum() / 1000:,.0f} km")

    if not ok:
        print("\nThe two extractions disagree. Check the highway list in build_swiss_graph.py.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
