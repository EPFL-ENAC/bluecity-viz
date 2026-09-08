"""The Swiss road graph on disk, cut in cells.

The whole country is about a million edges. Holding it in memory as a routing
graph would cost more than the areas it serves, and nobody routes across the
country anyway: a user picks a circle a few kilometres wide. So the graph
lives in two parquet files, one row group per grid cell, and a request reads
only the cells its circle touches. That is a few milliseconds.

Layout of the store directory:

    nodes.parquet   cell, node_id, x, y, street_count, elevation
    edges.parquet   cell (of u), u, v, key, length, travel_time, speed_kph,
                    lanes, elev_gain, highway, name, geom_xy
    index.json      the grid, and per cell its row groups and its counts
    density.json    counts per cell for the frontend, so the picker can tell
                    "usable here" without asking the backend

An edge belongs to the cell of its start node. An area keeps the edges whose
two ends are both inside the shape, and those always start in a cell the
circle touches, so reading the touched cells is enough.

The writer lives here too, next to the reader, so the offline pipeline and
the tests cannot drift apart on the schema.
"""

import json
import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

# Bump when the columns change, so an old store is refused instead of read wrong.
FORMAT_VERSION = 1

NODES_FILE = "nodes.parquet"
EDGES_FILE = "edges.parquet"
INDEX_FILE = "index.json"
DENSITY_FILE = "density.json"

# Metres per degree, good enough at this scale: the cells are 5 km and the
# check they serve is "is this area dense enough", not a survey.
M_PER_DEG_LAT = 111_320.0


def m_per_deg_lon(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


@dataclass(frozen=True)
class Grid:
    """Plain lon/lat cells, about 4.9 by 5.0 km at the latitude of Bern.

    Degrees, not a projection: the backend and the frontend both have to map a
    circle to cells, and neither should carry projection code for it.
    """

    lon0: float = 5.90
    lat0: float = 45.80
    dlon: float = 0.064
    dlat: float = 0.045
    ncols: int = 72
    nrows: int = 47

    @property
    def n_cells(self) -> int:
        return self.ncols * self.nrows

    def col_of(self, lon):
        off = (np.asarray(lon, dtype=np.float64) - self.lon0) / self.dlon
        return np.floor(off).astype(np.int64)

    def row_of(self, lat):
        off = (np.asarray(lat, dtype=np.float64) - self.lat0) / self.dlat
        return np.floor(off).astype(np.int64)

    def cell_of(self, lon, lat) -> np.ndarray:
        """Cell id of each point. Points outside the grid get -1."""
        col, row = self.col_of(lon), self.row_of(lat)
        inside = (col >= 0) & (col < self.ncols) & (row >= 0) & (row < self.nrows)
        return np.where(inside, row * self.ncols + col, -1)

    def bounds_of(self, cell: int) -> tuple:
        """(minlon, minlat, maxlon, maxlat) of one cell."""
        row, col = divmod(int(cell), self.ncols)
        minlon = self.lon0 + col * self.dlon
        minlat = self.lat0 + row * self.dlat
        return (minlon, minlat, minlon + self.dlon, minlat + self.dlat)

    def cells_in_bbox(self, minlon, minlat, maxlon, maxlat) -> List[int]:
        c0 = max(0, int(self.col_of(minlon)))
        c1 = min(self.ncols - 1, int(self.col_of(maxlon)))
        r0 = max(0, int(self.row_of(minlat)))
        r1 = min(self.nrows - 1, int(self.row_of(maxlat)))
        if c1 < c0 or r1 < r0:
            return []
        return [r * self.ncols + c for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]

    def cells_in_circle(self, lon: float, lat: float, radius_m: float) -> List[int]:
        """Every cell the circle touches, corners rejected properly."""
        dlat_deg = radius_m / M_PER_DEG_LAT
        dlon_deg = radius_m / max(m_per_deg_lon(lat), 1.0)
        candidates = self.cells_in_bbox(
            lon - dlon_deg, lat - dlat_deg, lon + dlon_deg, lat + dlat_deg
        )
        kept = []
        for cell in candidates:
            minlon, minlat, maxlon, maxlat = self.bounds_of(cell)
            # distance from the centre to the cell rectangle, in metres
            dx = max(minlon - lon, 0.0, lon - maxlon) * m_per_deg_lon(lat)
            dy = max(minlat - lat, 0.0, lat - maxlat) * M_PER_DEG_LAT
            if dx * dx + dy * dy <= radius_m * radius_m:
                kept.append(cell)
        return kept


NODE_COLUMNS = {
    "cell": pa.int32(),
    "node_id": pa.int64(),
    "x": pa.float32(),
    "y": pa.float32(),
    "street_count": pa.int16(),
    "elevation": pa.float32(),
}

EDGE_COLUMNS = {
    "cell": pa.int32(),
    "u": pa.int64(),
    "v": pa.int64(),
    # osmnx writes a key per edge, not per parallel pair: it goes up to the
    # edge count, so int8 is far too narrow.
    "key": pa.int32(),
    "length": pa.float32(),
    "travel_time": pa.float32(),
    "speed_kph": pa.float32(),
    "lanes": pa.int16(),
    "elev_gain": pa.float32(),
    "highway": pa.string(),
    "name": pa.string(),
    # flat [lon0, lat0, lon1, lat1, ...]; float32 is about 1 cm here
    "geom_xy": pa.list_(pa.float32()),
}

# Columns an area needs to build its mirror. The geometry and the labels are
# read separately, only when the frontend asks for them.
HOT_EDGE_COLUMNS = [
    "u",
    "v",
    "key",
    "length",
    "travel_time",
    "speed_kph",
    "lanes",
    "elev_gain",
]


def _clip(values, dtype) -> np.ndarray:
    """Cast to a narrow integer type without overflowing on bad OSM data.

    A lane count of 300 is wrong anyway, and a hard crash while writing the
    country is worse than a clamped value.
    """
    info = np.iinfo(dtype)
    return np.clip(np.asarray(values, dtype=np.int64), info.min, info.max).astype(dtype)


def distance_m(lon, lat, lon0: float, lat0: float) -> np.ndarray:
    """Equirectangular distance in metres from (lon0, lat0)."""
    dx = (np.asarray(lon, dtype=np.float64) - lon0) * m_per_deg_lon(lat0)
    dy = (np.asarray(lat, dtype=np.float64) - lat0) * M_PER_DEG_LAT
    return np.sqrt(dx * dx + dy * dy)


# ── Writing ───────────────────────────────────────────────────────────────────


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

    pos = {int(n): i for i, n in enumerate(node_id)}
    u = np.asarray(edges["u"], dtype=np.int64)
    v = np.asarray(edges["v"], dtype=np.int64)
    u_pos = np.fromiter((pos[int(a)] for a in u), dtype=np.int64, count=len(u))
    v_pos = np.fromiter((pos[int(b)] for b in v), dtype=np.int64, count=len(v))
    edge_cell = node_cell[u_pos]

    if geometry is None:
        geometry = [
            np.array([[x[a], y[a]], [x[b], y[b]]], dtype=np.float32) for a, b in zip(u_pos, v_pos)
        ]

    node_order = np.argsort(node_cell, kind="stable")
    edge_order = np.argsort(edge_cell, kind="stable")

    index = {
        "format_version": FORMAT_VERSION,
        "grid": asdict(grid),
        "cells": {},
        "totals": {"nodes": int(len(node_id)), "edges": int(len(u))},
    }

    cells = sorted({int(c) for c in node_cell[node_cell >= 0]})
    node_writer = pq.ParquetWriter(
        directory / NODES_FILE, pa.schema(NODE_COLUMNS), compression="zstd"
    )
    edge_writer = pq.ParquetWriter(
        directory / EDGES_FILE, pa.schema(EDGE_COLUMNS), compression="zstd"
    )
    node_rg = edge_rg = 0
    try:
        for cell in cells:
            n_idx = node_order[node_cell[node_order] == cell]
            e_idx = edge_order[edge_cell[edge_order] == cell]

            node_writer.write_table(
                pa.table(
                    {
                        "cell": np.full(len(n_idx), cell, dtype=np.int32),
                        "node_id": node_id[n_idx],
                        "x": x[n_idx].astype(np.float32),
                        "y": y[n_idx].astype(np.float32),
                        "street_count": _clip(nodes["street_count"], np.int16)[n_idx],
                        "elevation": np.asarray(nodes["elevation"], dtype=np.float32)[n_idx],
                    },
                    schema=pa.schema(NODE_COLUMNS),
                )
            )
            entry = {
                "nodes_rg": node_rg,
                "n_nodes": int(len(n_idx)),
                "n_nodes_sc3": int(
                    (np.asarray(nodes["street_count"], dtype=np.int64)[n_idx] >= 3).sum()
                ),
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
                            "key": np.asarray(edges.get("key", np.zeros(len(u))), dtype=np.int32)[
                                e_idx
                            ],
                            "length": np.asarray(edges["length"], dtype=np.float32)[e_idx],
                            "travel_time": np.asarray(edges["travel_time"], dtype=np.float32)[
                                e_idx
                            ],
                            "speed_kph": np.asarray(edges["speed_kph"], dtype=np.float32)[e_idx],
                            "lanes": _clip(edges["lanes"], np.int16)[e_idx],
                            "elev_gain": np.asarray(edges["elev_gain"], dtype=np.float32)[e_idx],
                            "highway": [str(edges["highway"][i]) for i in e_idx]
                            if "highway" in edges
                            else [""] * len(e_idx),
                            "name": [str(edges["name"][i]) for i in e_idx]
                            if "name" in edges
                            else [""] * len(e_idx),
                            "geom_xy": [
                                np.asarray(geometry[i], dtype=np.float32).reshape(-1) for i in e_idx
                            ],
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
DENSITY_REFINE = 5


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


class GraphStore:
    """Read-only view of a store. Keeps the index, not the data."""

    def __init__(self, directory, index: dict):
        self.directory = Path(directory)
        self.index = index
        self.grid = Grid(**index["grid"])
        self.cells = {int(k): v for k, v in index["cells"].items()}
        self.coverage_bbox = index.get("coverage_bbox")
        self._nodes = pq.ParquetFile(self.directory / NODES_FILE)
        self._edges = pq.ParquetFile(self.directory / EDGES_FILE)

    @classmethod
    def open(cls, directory) -> "GraphStore":
        directory = Path(directory)
        index = json.loads((directory / INDEX_FILE).read_text())
        version = index.get("format_version")
        if version != FORMAT_VERSION:
            raise ValueError(
                f"graph store {directory} is version {version}, this code reads {FORMAT_VERSION}"
            )
        return cls(directory, index)

    @property
    def totals(self) -> dict:
        return self.index["totals"]

    def cells_for_circle(self, lon: float, lat: float, radius_m: float) -> List[int]:
        """Cells the circle touches that the store actually has."""
        return [c for c in self.grid.cells_in_circle(lon, lat, radius_m) if c in self.cells]

    def cells_for_bbox(self, minlon, minlat, maxlon, maxlat) -> List[int]:
        return [
            c for c in self.grid.cells_in_bbox(minlon, minlat, maxlon, maxlat) if c in self.cells
        ]

    def counts_for(self, cells: Iterable[int]) -> dict:
        """Upper bound on what these cells hold, without reading them."""
        nodes = edges = sc3 = 0
        for cell in cells:
            entry = self.cells.get(int(cell))
            if entry:
                nodes += entry["n_nodes"]
                sc3 += entry["n_nodes_sc3"]
                edges += entry["n_edges"]
        return {"n_nodes": nodes, "n_nodes_sc3": sc3, "n_edges": edges}

    def read_nodes(self, cells: Sequence[int]) -> Dict[str, np.ndarray]:
        groups = [self.cells[int(c)]["nodes_rg"] for c in cells if int(c) in self.cells]
        if not groups:
            return {k: np.empty(0, dtype=np.float64) for k in NODE_COLUMNS}
        table = self._nodes.read_row_groups(sorted(groups), columns=list(NODE_COLUMNS))
        return {name: table[name].to_numpy(zero_copy_only=False) for name in NODE_COLUMNS}

    def read_edges(
        self, cells: Sequence[int], with_geometry: bool = False
    ) -> Dict[str, np.ndarray]:
        """Edges starting in these cells.

        With `with_geometry`, the coordinates come back as one flat float32
        array plus offsets, so nothing is turned into python lists.
        """
        groups = sorted(
            {
                self.cells[int(c)]["edges_rg"]
                for c in cells
                if int(c) in self.cells and self.cells[int(c)]["edges_rg"] is not None
            }
        )
        columns = list(HOT_EDGE_COLUMNS)
        if with_geometry:
            columns += ["highway", "name", "geom_xy"]
        if not groups:
            out = {name: np.empty(0, dtype=np.float64) for name in HOT_EDGE_COLUMNS}
            if with_geometry:
                out["highway"] = []
                out["name"] = []
                out["geom_flat"] = np.empty(0, dtype=np.float32)
                out["geom_offsets"] = np.zeros(1, dtype=np.int64)
            return out

        table = self._edges.read_row_groups(groups, columns=columns)
        out = {name: table[name].to_numpy(zero_copy_only=False) for name in HOT_EDGE_COLUMNS}
        if with_geometry:
            out["highway"] = table["highway"].to_pylist()
            out["name"] = table["name"].to_pylist()
            geom = table["geom_xy"].combine_chunks()
            out["geom_flat"] = np.asarray(geom.flatten(), dtype=np.float32)
            out["geom_offsets"] = np.asarray(geom.offsets, dtype=np.int64)
        return out
