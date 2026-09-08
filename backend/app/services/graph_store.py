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
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

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
