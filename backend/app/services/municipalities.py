"""The Swiss municipalities, read at request time to cut an area by boundaries.

One parquet file, written by `municipalities_writer` from swissBOUNDARIES3D:
one row per commune with its BFS number, its name, its canton, the communes it
shares a border with, its bbox and its simplified polygon (EPSG:4326).

The neighbours are computed once at build time on the full geometry, so
telling whether a selection is one region is a walk on a small graph, not a
polygon operation.
"""

import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pyarrow.parquet as pq
import shapely

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1

# The longest name an area gets, same cut as the frontend.
MAX_LABEL = 60

# About a metre. The outline is for the screen, not for the cut.
OUTLINE_GRID_DEG = 1e-5


@dataclass(frozen=True)
class Commune:
    bfs: int
    name: str
    canton: int
    neighbours: Tuple[int, ...]
    bbox: Tuple[float, float, float, float]
    geometry: shapely.Geometry


class Municipalities:
    """Every commune, by BFS number."""

    def __init__(self, communes: Dict[int, Commune], source: str = ""):
        self._communes = communes
        self.source = source

    @classmethod
    def open(cls, path) -> "Municipalities":
        path = Path(path)
        table = pq.read_table(path)
        metadata = {k.decode(): v.decode() for k, v in (table.schema.metadata or {}).items()}
        version = metadata.get("format_version")
        if version != str(FORMAT_VERSION):
            raise ValueError(
                f"municipalities file {path} is version {version}, this code reads {FORMAT_VERSION}"
            )
        columns = table.to_pydict()
        geometries = shapely.from_wkb(columns["geometry"])
        communes = {}
        for i, bfs in enumerate(columns["bfs"]):
            communes[int(bfs)] = Commune(
                bfs=int(bfs),
                name=columns["name"][i],
                canton=int(columns["canton"][i]),
                neighbours=tuple(int(n) for n in columns["neighbours"][i]),
                bbox=tuple(float(v) for v in columns["bbox"][i]),
                geometry=geometries[i],
            )
        return cls(communes, source=metadata.get("source", ""))

    def __len__(self) -> int:
        return len(self._communes)

    def __contains__(self, bfs: int) -> bool:
        return bfs in self._communes

    def get(self, bfs: int) -> Optional[Commune]:
        return self._communes.get(bfs)

    def names(self, ids: Iterable[int]) -> List[str]:
        return [self._communes[i].name for i in ids if i in self._communes]

    def contiguous(self, ids: Sequence[int]) -> bool:
        """Do these communes form one region, border to border.

        True for a single commune, False for none. Unknown ids count as apart.
        """
        wanted = set(ids)
        if not wanted:
            return False
        if any(i not in self._communes for i in wanted):
            return False
        start = next(iter(wanted))
        seen = {start}
        queue = deque([start])
        while queue:
            here = queue.popleft()
            for there in self._communes[here].neighbours:
                if there in wanted and there not in seen:
                    seen.add(there)
                    queue.append(there)
        return seen == wanted

    def union(self, ids: Sequence[int]) -> shapely.Geometry:
        """The communes as one shape, prepared for fast point tests."""
        geometry = shapely.union_all([self._communes[i].geometry for i in ids])
        shapely.prepare(geometry)
        return geometry


def normalise_ids(ids: Iterable[int]) -> Tuple[int, ...]:
    """Deduplicated and sorted as numbers, the order the area id uses."""
    return tuple(sorted({int(i) for i in ids}))


def label(names: Sequence[str]) -> str:
    """The name of an area made of these communes."""
    if not names:
        return ""
    if len(names) == 1:
        text = names[0]
    elif len(names) == 2:
        text = f"{names[0]} + {names[1]}"
    else:
        text = f"{names[0]}, {names[1]} + {len(names) - 2} more"
    if len(text) > MAX_LABEL:
        text = text[: MAX_LABEL - 1].rstrip() + "…"
    return text


def outline_geojson(geometry: shapely.Geometry) -> dict:
    """The shape as a GeoJSON geometry, rounded for the screen."""
    rounded = shapely.set_precision(geometry, OUTLINE_GRID_DEG)
    return json.loads(shapely.to_geojson(rounded))
