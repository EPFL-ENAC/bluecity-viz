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

import numpy as np
import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.graph_store import Grid, write_store  # noqa: E402
from app.services.osm_values import parse_lanes, parse_street_count  # noqa: E402


def first_value(value, default=""):
    """OSM tags come as a list when the way was merged."""
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value) if value is not None else default


def arrays_from_graph(graph):
    """Flatten a NetworkX graph into the columns the store holds."""
    node_ids = list(graph.nodes())
    node_data = [graph.nodes[n] for n in node_ids]
    nodes = {
        "node_id": np.asarray(node_ids, dtype=np.int64),
        "x": np.asarray([float(d["x"]) for d in node_data]),
        "y": np.asarray([float(d["y"]) for d in node_data]),
        "street_count": np.asarray(
            [parse_street_count(d.get("street_count")) for d in node_data], dtype=np.int16
        ),
        "elevation": np.asarray([float(d.get("elevation") or 0.0) for d in node_data]),
    }

    edge_list = list(graph.edges(keys=True, data=True))
    geometry = []
    elev_gain = []
    for u, v, _key, data in edge_list:
        if "geometry" in data:
            geometry.append(np.asarray(data["geometry"].coords, dtype=np.float32))
        else:
            geometry.append(
                np.asarray(
                    [
                        [graph.nodes[u]["x"], graph.nodes[u]["y"]],
                        [graph.nodes[v]["x"], graph.nodes[v]["y"]],
                    ],
                    dtype=np.float32,
                )
            )
        gain = data.get("elevation_gain")
        if gain is None:
            up, down = graph.nodes[u].get("elevation"), graph.nodes[v].get("elevation")
            gain = max(0.0, float(down) - float(up)) if up is not None and down is not None else 0.0
        elev_gain.append(float(gain))

    edges = {
        "u": np.asarray([u for u, _v, _k, _d in edge_list], dtype=np.int64),
        "v": np.asarray([v for _u, v, _k, _d in edge_list], dtype=np.int64),
        "key": np.asarray([k for _u, _v, k, _d in edge_list], dtype=np.int32),
        "length": np.asarray([float(d.get("length") or 0.0) for *_, d in edge_list]),
        "travel_time": np.asarray([float(d.get("travel_time") or 0.0) for *_, d in edge_list]),
        "speed_kph": np.asarray([float(d.get("speed_kph") or 0.0) for *_, d in edge_list]),
        "lanes": np.asarray(
            [parse_lanes(d.get("lanes", 2)) for *_, d in edge_list], dtype=np.int16
        ),
        "elev_gain": np.asarray(elev_gain),
        "highway": [first_value(d.get("highway"), "unknown") for *_, d in edge_list],
        "name": [first_value(d.get("name"), "") for *_, d in edge_list],
    }
    return nodes, edges, geometry


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
