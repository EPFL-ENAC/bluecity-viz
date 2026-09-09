"""Write a graph store: the parquet files the reader opens.

Only the build scripts call this. It lives beside the reader so the schema and
the grid are written and read from one place, but it is a separate module so a
request never imports the parquet writer.
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from app.services.graph_store import (
    DENSITY_FILE,
    EDGE_COLUMNS,
    EDGES_FILE,
    FORMAT_VERSION,
    INDEX_FILE,
    NODE_COLUMNS,
    NODES_FILE,
    Grid,
    _clip,
)
from app.services.osm_values import parse_lanes, parse_street_count

logger = logging.getLogger(__name__)


DENSITY_REFINE = 5

# How far a drawn street may move when the shape points it does not need are
# dropped. A road is stored with a point every few metres, twice what it takes
# to draw it. Douglas-Peucker at half a metre keeps two thirds of them and the
# file loses a third of its size. Nothing else changes: the two ends of an edge
# are its nodes and are never moved, and length, travel_time and every routing
# number are stored in their own columns.
SIMPLIFY_M = 0.5

# One degree of latitude in metres, near enough anywhere in Switzerland.
M_PER_DEG = 111_320.0

# The coordinates are the file, four fifths of it, and plain float32 hardly
# compresses at all. Byte stream split puts the bytes of the same weight
# together, which gives zstd something to work with: a third off, and the
# reader does not even know, parquet undoes the encoding on its own.
EDGE_PARQUET = {
    "compression": "zstd",
    "column_encoding": {"geom_xy.list.element": "BYTE_STREAM_SPLIT"},
    # everything else is a number, only these two repeat themselves
    "use_dictionary": ["highway", "name"],
}
NODE_PARQUET = {
    "compression": "zstd",
    "column_encoding": {name: "BYTE_STREAM_SPLIT" for name in ("x", "y", "elevation")},
    "use_dictionary": False,
}


def simplify_geometry(geometry: Sequence[np.ndarray], metres: float = SIMPLIFY_M) -> list:
    """The same lines with the points a road does not need dropped.

    One shapely call for the whole country: a loop over the edges took longer
    than everything else in the build.
    """
    pairs = [np.asarray(g, dtype=np.float64).reshape(-1, 2) for g in geometry]
    if not metres or not pairs:
        return [p.astype(np.float32).reshape(-1) for p in pairs]

    counts = np.fromiter((len(p) for p in pairs), dtype=np.int64, count=len(pairs))
    index = np.repeat(np.arange(len(pairs)), counts)
    lines = shapely.linestrings(np.concatenate(pairs), indices=index)
    # preserve_topology=False is Douglas-Peucker, which keeps both ends.
    simple = shapely.simplify(lines, metres / M_PER_DEG, preserve_topology=False)

    coords, back = shapely.get_coordinates(simple, return_index=True)
    kept = np.bincount(back, minlength=len(pairs))
    ends = np.zeros(len(pairs) + 1, dtype=np.int64)
    np.cumsum(kept, out=ends[1:])
    flat = coords.astype(np.float32).reshape(-1)
    return [flat[2 * ends[i] : 2 * ends[i + 1]] for i in range(len(pairs))]


def density_grid(grid: Grid, refine: int = DENSITY_REFINE) -> Grid:
    """The store grid, cut finer. Same origin, so the two line up."""
    return Grid(
        lon0=grid.lon0,
        lat0=grid.lat0,
        dlon=grid.dlon / refine,
        dlat=grid.dlat / refine,
        ncols=grid.ncols * refine,
        nrows=grid.nrows * refine,
    )


def _density(
    grid: Grid,
    coverage_bbox,
    x: np.ndarray,
    y: np.ndarray,
    street_count: np.ndarray,
    edge_x: np.ndarray,
    edge_y: np.ndarray,
    refine: int = DENSITY_REFINE,
) -> dict:
    """The small file the frontend sums under the circle.

    Counts are per fine cell: junctions (3 streets or more, the pool the OD
    sampler draws from) and streets, a street counted at its start node.
    """
    fine = density_grid(grid, refine)
    junction = np.asarray(street_count, dtype=np.int64) >= 3
    node_cells = fine.cell_of(x[junction], y[junction])
    edge_cells = fine.cell_of(edge_x, edge_y)

    nodes_sc3 = np.bincount(node_cells[node_cells >= 0], minlength=fine.n_cells)
    edges = np.bincount(edge_cells[edge_cells >= 0], minlength=fine.n_cells)
    return {
        "format_version": FORMAT_VERSION,
        "grid": asdict(fine),
        "coverage_bbox": coverage_bbox,
        "nodes_sc3": nodes_sc3.tolist(),
        "edges": edges.tolist(),
    }


# ── Reading ───────────────────────────────────────────────────────────────────


def write_store(
    directory,
    nodes: Dict[str, np.ndarray],
    edges: Dict[str, np.ndarray],
    grid: Grid = Grid(),
    geometry: Optional[Sequence[np.ndarray]] = None,
) -> dict:
    """Write a store, one row group per cell.

    `nodes` needs node_id, x, y, street_count, elevation; `edges` needs u, v,
    key and the per-edge attributes. Cells are derived here, so the caller
    never has to know the grid.

    `geometry` is one (n, 2) lon/lat array per edge. Missing means a straight
    line between the two nodes.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    node_id = np.asarray(nodes["node_id"], dtype=np.int64)
    x = np.asarray(nodes["x"], dtype=np.float64)
    y = np.asarray(nodes["y"], dtype=np.float64)
    # Cells are decided here, from the full precision coordinates, and the
    # cell column is the only truth afterwards. The stored coordinates are
    # float32, so recomputing the cell of a node sitting exactly on a boundary
    # can land next door.
    node_cell = grid.cell_of(x, y)

    # Node ids to positions with searchsorted, not with a dict: on the country
    # that dict was a million boxed ints.
    u = np.asarray(edges["u"], dtype=np.int64)
    v = np.asarray(edges["v"], dtype=np.int64)
    order = np.argsort(node_id)
    sorted_ids = node_id[order]
    u_pos = order[np.searchsorted(sorted_ids, u)]
    v_pos = order[np.searchsorted(sorted_ids, v)]
    edge_cell = node_cell[u_pos]

    if geometry is None:
        geometry = [
            np.array([[x[a], y[a]], [x[b], y[b]]], dtype=np.float32) for a, b in zip(u_pos, v_pos)
        ]

    node_order = np.argsort(node_cell, kind="stable")
    edge_order = np.argsort(edge_cell, kind="stable")

    # Convert each column once. Doing it inside the loop reread every row of
    # every column once per cell, and the country has thousands of cells.
    street_count = _clip(nodes["street_count"], np.int16)
    elevation = np.asarray(nodes["elevation"], dtype=np.float32)
    junction = np.asarray(nodes["street_count"], dtype=np.int64) >= 3
    x32 = x.astype(np.float32)
    y32 = y.astype(np.float32)
    edge_key = np.asarray(edges.get("key", np.zeros(len(u))), dtype=np.int32)
    length = np.asarray(edges["length"], dtype=np.float32)
    travel_time = np.asarray(edges["travel_time"], dtype=np.float32)
    speed_kph = np.asarray(edges["speed_kph"], dtype=np.float32)
    lanes = _clip(edges["lanes"], np.int16)
    elev_gain = np.asarray(edges["elev_gain"], dtype=np.float32)
    highway = edges.get("highway")
    name = edges.get("name")
    geom32 = simplify_geometry(geometry)

    index = {
        "format_version": FORMAT_VERSION,
        "grid": asdict(grid),
        "cells": {},
        "totals": {"nodes": int((node_cell >= 0).sum()), "edges": int(len(u))},
    }

    cells = sorted({int(c) for c in node_cell[node_cell >= 0]})
    # The two orders are sorted by cell, so each cell is one slice of them and
    # searchsorted gives every boundary at once.
    steps = cells + [cells[-1] + 1] if cells else []
    node_bounds = np.searchsorted(node_cell[node_order], steps)
    edge_bounds = np.searchsorted(edge_cell[edge_order], steps)
    node_writer = pq.ParquetWriter(directory / NODES_FILE, pa.schema(NODE_COLUMNS), **NODE_PARQUET)
    edge_writer = pq.ParquetWriter(directory / EDGES_FILE, pa.schema(EDGE_COLUMNS), **EDGE_PARQUET)
    node_rg = edge_rg = 0
    try:
        for i, cell in enumerate(cells):
            n_idx = node_order[node_bounds[i] : node_bounds[i + 1]]
            e_idx = edge_order[edge_bounds[i] : edge_bounds[i + 1]]

            node_writer.write_table(
                pa.table(
                    {
                        "cell": np.full(len(n_idx), cell, dtype=np.int32),
                        "node_id": node_id[n_idx],
                        "x": x32[n_idx],
                        "y": y32[n_idx],
                        "street_count": street_count[n_idx],
                        "elevation": elevation[n_idx],
                    },
                    schema=pa.schema(NODE_COLUMNS),
                )
            )
            entry = {
                "nodes_rg": node_rg,
                "n_nodes": int(len(n_idx)),
                "n_nodes_sc3": int(junction[n_idx].sum()),
                "n_edges": int(len(e_idx)),
                "edges_rg": None,
            }
            node_rg += 1

            if len(e_idx):
                edge_writer.write_table(
                    pa.table(
                        {
                            "cell": np.full(len(e_idx), cell, dtype=np.int32),
                            "u": u[e_idx],
                            "v": v[e_idx],
                            "key": edge_key[e_idx],
                            "length": length[e_idx],
                            "travel_time": travel_time[e_idx],
                            "speed_kph": speed_kph[e_idx],
                            "lanes": lanes[e_idx],
                            "elev_gain": elev_gain[e_idx],
                            "highway": [str(highway[j]) for j in e_idx]
                            if highway is not None
                            else [""] * len(e_idx),
                            "name": [str(name[j]) for j in e_idx]
                            if name is not None
                            else [""] * len(e_idx),
                            "geom_xy": [geom32[j] for j in e_idx],
                        },
                        schema=pa.schema(EDGE_COLUMNS),
                    )
                )
                entry["edges_rg"] = edge_rg
                edge_rg += 1

            index["cells"][str(cell)] = entry
    finally:
        node_writer.close()
        edge_writer.close()

    inside = node_cell >= 0
    index["coverage_bbox"] = [
        float(x[inside].min()),
        float(y[inside].min()),
        float(x[inside].max()),
        float(y[inside].max()),
    ]
    (directory / INDEX_FILE).write_text(json.dumps(index))
    (directory / DENSITY_FILE).write_text(
        json.dumps(
            _density(
                grid,
                index["coverage_bbox"],
                x,
                y,
                nodes["street_count"],
                x[u_pos],
                y[u_pos],
            )
        )
    )
    logger.info(
        "[STORE] wrote %d nodes, %d edges, %d cells to %s",
        len(node_id),
        len(u),
        len(cells),
        directory,
    )
    return index


# The density file has its own grid, finer than the store's. The store cells
# are 5 km because that is a good parquet row group, but the picker sums them
# under a 3 km circle and assumes each cell is evenly filled. A town is not
# evenly spread over 25 km2, so at 5 km the estimate came out 20 to 40 percent
# low and the picker said "too sparse" over a town the server accepts. Five
# times finer is about 1 km, which is small enough for the assumption to hold.


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
