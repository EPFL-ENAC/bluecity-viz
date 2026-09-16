"""Write the municipalities file the reader opens.

Only the build script calls this. It sits beside the reader so the columns are
written and read from one place, and a request never imports it.
"""

import logging
from pathlib import Path
from typing import List, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from app.services.municipalities import FORMAT_VERSION

logger = logging.getLogger(__name__)

# Two communes are neighbours when their borders share a line. A single corner
# point is not enough: the region would be one only on paper.
SHARED_BORDER = "****1****"


def neighbours_of(geometries: Sequence[shapely.Geometry], ids: Sequence[int]) -> List[List[int]]:
    """For every commune, the sorted ids of the communes it shares a border with.

    Run it on the full geometry, before any simplification, so a thin shared
    border is never lost.
    """
    geometries = np.asarray(geometries, dtype=object)
    ids = [int(i) for i in ids]
    tree = shapely.STRtree(geometries)
    left, right = tree.query(geometries, predicate="intersects")
    keep = left < right
    left, right = left[keep], right[keep]
    touching = shapely.relate_pattern(geometries[left], geometries[right], SHARED_BORDER)

    neighbours: List[set] = [set() for _ in ids]
    for a, b in zip(left[touching], right[touching]):
        neighbours[a].add(ids[b])
        neighbours[b].add(ids[a])
    return [sorted(n) for n in neighbours]


def simplify_coverage(geometries: Sequence[shapely.Geometry], tolerance: float) -> np.ndarray:
    """Simplify the communes together, so a shared border stays the same line.

    Simplifying one polygon at a time moves each side of a border its own way,
    which leaves gaps and overlaps between neighbours.
    """
    geometries = np.asarray(geometries, dtype=object)
    if not tolerance:
        return geometries
    simple = shapely.coverage_simplify(geometries, tolerance)
    if shapely.coverage_is_valid(simple):
        return simple
    logger.warning("coverage simplify gave an invalid coverage, simplifying one by one")
    return shapely.make_valid(shapely.simplify(geometries, tolerance, preserve_topology=True))


def write_municipalities(
    path,
    *,
    bfs: Sequence[int],
    name: Sequence[str],
    canton: Sequence[int],
    neighbours: Sequence[Sequence[int]],
    geometry: Sequence[shapely.Geometry],
    source: str = "",
    simplify_deg: float = 0.0,
) -> Path:
    """Write one row per commune, sorted by BFS number. Geometry is EPSG:4326."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    order = np.argsort(np.asarray(bfs, dtype=np.int64), kind="stable")
    geometry = np.asarray(geometry, dtype=object)[order]
    bounds = np.round(shapely.bounds(geometry), 5)

    table = pa.table(
        {
            "bfs": pa.array([int(bfs[i]) for i in order], type=pa.int32()),
            "name": pa.array([str(name[i]) for i in order], type=pa.string()),
            "canton": pa.array([int(canton[i]) for i in order], type=pa.int16()),
            "neighbours": pa.array(
                [[int(n) for n in neighbours[i]] for i in order], type=pa.list_(pa.int32())
            ),
            "bbox": pa.array([list(map(float, b)) for b in bounds], type=pa.list_(pa.float64())),
            "geometry": pa.array(shapely.to_wkb(geometry).tolist(), type=pa.binary()),
        }
    )
    table = table.replace_schema_metadata(
        {
            "format_version": str(FORMAT_VERSION),
            "source": source,
            "simplify_deg": str(simplify_deg),
        }
    )
    pq.write_table(table, path, compression="zstd")
    logger.info("wrote %d municipalities to %s", table.num_rows, path)
    return path
