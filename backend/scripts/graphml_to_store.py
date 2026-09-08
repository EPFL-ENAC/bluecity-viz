#!/usr/bin/env python3
"""Turn an OSMnx GraphML file into a graph store the backend can serve areas from.

This is the last step of the offline pipeline: processing/traffic-analysis
builds the GraphML for a region (one city today, the whole country later) and
this writes the parquet files the backend reads cell by cell.

    uv run python scripts/graphml_to_store.py data/lausanne.graphml data/swiss_graph

The store is not committed. In production it is either baked into the image or
downloaded at startup.
"""

import argparse
import sys
import time
from pathlib import Path

import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.graph_store import Grid  # noqa: E402
from app.services.graph_store_writer import arrays_from_graph, write_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graphml", help="input GraphML file")
    parser.add_argument("output", help="output store directory")
    args = parser.parse_args()

    started = time.perf_counter()
    print(f"Loading {args.graphml} ...")
    graph = ox.load_graphml(args.graphml)
    if not any(d.get("speed_kph") for _, _, d in graph.edges(data=True)):
        graph = ox.routing.add_edge_speeds(graph)
    if not any(d.get("travel_time") for _, _, d in graph.edges(data=True)):
        graph = ox.routing.add_edge_travel_times(graph)

    nodes, edges, geometry = arrays_from_graph(graph)
    index = write_store(args.output, nodes, edges, grid=Grid(), geometry=geometry)

    total = sum(f.stat().st_size for f in Path(args.output).iterdir())
    print(
        f"Wrote {index['totals']['nodes']:,} nodes and {index['totals']['edges']:,} edges "
        f"in {len(index['cells'])} cells, {total / 1e6:.1f} MB, "
        f"in {time.perf_counter() - started:.1f} s"
    )
    print(f"Copy {args.output}/density.json to frontend/public/geodata/swiss_graph_density.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
