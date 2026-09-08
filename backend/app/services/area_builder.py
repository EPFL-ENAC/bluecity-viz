"""Cut an area out of the Swiss graph store and make a routing graph of it.

The rules an area has to pass, in this order:

  outside_coverage  the shape is not where the store has data, or the radius
                    is outside what the tool accepts
  too_sparse        not enough junctions: the OD sampler needs a pool of nodes
                    with three streets or more, and a handful of country roads
                    gives meaningless trips
  too_large         more nodes or edges than the routing budget allows, so a
                    recalculate would stop feeling instant
  disconnected      the nodes do not form one network. A circle cut by a lake
                    or a mountain gives two islands and half the trips fail.

Size is checked before connectivity so a 40 km circle fails without paying for
the component search.
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import igraph as ig
import numpy as np

from app.config import settings
from app.services.area_graph import AreaGraph, AreaMeta
from app.services.graph_mirror import GraphMirror
from app.services.graph_store import GraphStore, distance_m

logger = logging.getLogger(__name__)


class AreaRejected(ValueError):
    """The shape cannot be used. Carries the code the frontend shows."""

    def __init__(self, code: str, message: str, counts: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.counts = counts or {}


@dataclass(frozen=True)
class AreaSpec:
    """A circle, and the id derived from it.

    The id comes from the rounded geometry, not from a counter: two users who
    pick the same spot share one area, and an investigation saved yesterday
    finds its area again after a restart or an eviction.
    """

    lon: float
    lat: float
    radius_m: float

    @classmethod
    def from_circle(cls, lon: float, lat: float, radius_m: float) -> "AreaSpec":
        # about 10 m of rounding, so a pixel of drag does not make a new area
        return cls(
            lon=round(float(lon), 4),
            lat=round(float(lat), 4),
            radius_m=float(round(radius_m)),
        )

    @property
    def id(self) -> str:
        return f"c_{self.lon:.4f}_{self.lat:.4f}_{int(self.radius_m)}"

    @property
    def name(self) -> str:
        return f"{self.radius_m / 1000:.1f} km around {self.lat:.3f}, {self.lon:.3f}"

    @property
    def bbox(self) -> List[float]:
        dlat = self.radius_m / 111_320.0
        dlon = self.radius_m / max(111_320.0 * math.cos(math.radians(self.lat)), 1.0)
        return [self.lon - dlon, self.lat - dlat, self.lon + dlon, self.lat + dlat]

    def contains(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Which points are inside the circle."""
        return distance_m(x, y, self.lon, self.lat) <= self.radius_m

    def cells(self, store: GraphStore) -> List[int]:
        return store.cells_for_circle(self.lon, self.lat, self.radius_m)


@dataclass
class Selection:
    """The nodes and edges a shape keeps, before any rule is applied."""

    node_id: np.ndarray
    x: np.ndarray
    y: np.ndarray
    street_count: np.ndarray
    elevation: np.ndarray
    edges: Dict[str, np.ndarray]

    @property
    def n_nodes(self) -> int:
        return len(self.node_id)

    @property
    def n_edges(self) -> int:
        return len(self.edges["u"])

    @property
    def n_junctions(self) -> int:
        return int((self.street_count >= 3).sum())


def select(store: GraphStore, spec: AreaSpec, with_geometry: bool = False) -> Selection:
    """Nodes inside the shape, and the edges with both ends inside."""
    cells = spec.cells(store)
    nodes = store.read_nodes(cells)
    if len(nodes["node_id"]) == 0:
        empty = np.empty(0, dtype=np.int64)
        return Selection(empty, empty, empty, empty, empty, {"u": empty, "v": empty})

    inside = spec.contains(nodes["x"], nodes["y"])
    node_id = nodes["node_id"][inside]

    edges = store.read_edges(cells, with_geometry=with_geometry)
    keep_u = np.isin(edges["u"], node_id)
    keep_v = np.isin(edges["v"], node_id)
    keep = keep_u & keep_v

    return Selection(
        node_id=node_id,
        x=nodes["x"][inside],
        y=nodes["y"][inside],
        street_count=nodes["street_count"][inside],
        elevation=nodes["elevation"][inside],
        edges=_take_edges(edges, keep),
    )


def _take_edges(edges: Dict[str, np.ndarray], keep: np.ndarray) -> Dict[str, np.ndarray]:
    """Filter every edge column, geometry included."""
    out = {}
    for name, values in edges.items():
        if name in ("geom_flat", "geom_offsets"):
            continue
        if isinstance(values, list):
            out[name] = [values[i] for i in np.nonzero(keep)[0]]
        else:
            out[name] = values[keep]
    if "geom_offsets" in edges:
        starts = edges["geom_offsets"][:-1][keep]
        stops = edges["geom_offsets"][1:][keep]
        lengths = stops - starts
        offsets = np.zeros(len(lengths) + 1, dtype=np.int64)
        np.cumsum(lengths, out=offsets[1:])
        total = int(offsets[-1])
        if total:
            block = np.repeat(starts, lengths)
            inner = np.arange(total, dtype=np.int64) - np.repeat(offsets[:-1], lengths)
            out["geom_flat"] = edges["geom_flat"][block + inner]
        else:
            out["geom_flat"] = np.empty(0, dtype=np.float32)
        out["geom_offsets"] = offsets
    return out


def giant_component(selection: Selection) -> Tuple[np.ndarray, float]:
    """Mask of the largest strongly connected component, and its share."""
    n = selection.n_nodes
    if n == 0:
        return np.zeros(0, dtype=bool), 0.0

    # Node ids to positions without a python dict: the store writes the nodes
    # sorted, so searchsorted is the lookup.
    order = np.argsort(selection.node_id)
    sorted_ids = selection.node_id[order]
    u_pos = order[np.searchsorted(sorted_ids, selection.edges["u"])]
    v_pos = order[np.searchsorted(sorted_ids, selection.edges["v"])]
    h = ig.Graph(n=n, edges=np.column_stack((u_pos, v_pos)).tolist(), directed=True)
    membership = np.asarray(h.connected_components(mode="strong").membership)
    if len(membership) == 0:
        return np.zeros(n, dtype=bool), 0.0
    biggest = np.bincount(membership).argmax()
    mask = membership == biggest
    return mask, float(mask.sum()) / n


def restrict(selection: Selection, mask: np.ndarray) -> Selection:
    """Keep only these nodes, and the edges between them."""
    node_id = selection.node_id[mask]
    keep = np.isin(selection.edges["u"], node_id) & np.isin(selection.edges["v"], node_id)
    return Selection(
        node_id=node_id,
        x=selection.x[mask],
        y=selection.y[mask],
        street_count=selection.street_count[mask],
        elevation=selection.elevation[mask],
        edges=_take_edges(selection.edges, keep),
    )


def check(
    store: GraphStore, spec: AreaSpec, selection: Optional[Selection] = None
) -> Tuple[dict, np.ndarray]:
    """Run the rules. Returns the counts and the main network mask.

    The mask is the expensive half, so build takes it from here instead of
    searching the components a second time.
    """
    bbox = spec.bbox
    coverage = store.coverage_bbox
    if not (settings.area_min_radius_m <= spec.radius_m <= settings.area_max_radius_m):
        raise AreaRejected(
            "outside_coverage",
            f"the radius must be between {settings.area_min_radius_m / 1000:.1f} km "
            f"and {settings.area_max_radius_m / 1000:.0f} km",
        )
    if coverage and (
        bbox[2] < coverage[0]
        or bbox[0] > coverage[2]
        or bbox[3] < coverage[1]
        or bbox[1] > coverage[3]
    ):
        raise AreaRejected("outside_coverage", "there is no road network here")

    if selection is None:
        selection = select(store, spec)

    counts = {
        "node_count": selection.n_nodes,
        "edge_count": selection.n_edges,
        "junction_count": selection.n_junctions,
        "scc_fraction": 0.0,
    }

    if selection.n_junctions < settings.area_min_junctions:
        raise AreaRejected(
            "too_sparse",
            f"only {selection.n_junctions} junctions here, the tool needs "
            f"{settings.area_min_junctions}",
            counts,
        )
    if selection.n_nodes > settings.area_max_nodes or selection.n_edges > settings.area_max_edges:
        raise AreaRejected(
            "too_large",
            f"{selection.n_nodes} nodes and {selection.n_edges} streets, the tool "
            f"takes at most {settings.area_max_nodes} and {settings.area_max_edges}",
            counts,
        )

    mask, fraction = giant_component(selection)
    counts["scc_fraction"] = round(fraction, 4)
    if fraction < settings.area_min_scc_fraction:
        raise AreaRejected(
            "disconnected",
            "this area is cut in pieces, so most trips could not be routed",
            counts,
        )
    return counts, mask


def preview(store: GraphStore, spec: AreaSpec) -> dict:
    """Can the tool run here. Reads the cells, but samples nothing."""
    try:
        counts, _mask = check(store, spec)
    except AreaRejected as rejected:
        return {
            "ok": False,
            "code": rejected.code,
            "message": rejected.message,
            "bbox": spec.bbox,
            **{
                "node_count": 0,
                "edge_count": 0,
                "junction_count": 0,
                "scc_fraction": 0.0,
                **rejected.counts,
            },
        }
    return {"ok": True, "code": None, "message": "", "bbox": spec.bbox, **counts}


def build(store: GraphStore, spec: AreaSpec, config=None, seed: int = 42) -> AreaGraph:
    """Cut the area, sample its OD pairs and compute its baseline."""
    from app.services.sampling.config import SamplingConfig

    config = config or SamplingConfig()
    started = time.perf_counter()

    # The rules run on the hot columns first, so a circle over half the country
    # is refused before its geometry is read.
    counts, mask = check(store, spec, select(store, spec))
    fraction = counts["scc_fraction"]
    selection = select(store, spec, with_geometry=True)

    # Keep the giant component only: the rest cannot be reached anyway, and a
    # node with no route pollutes the sampling.
    if not mask.all():
        selection = restrict(selection, mask)
        logger.info(
            "[AREA %s] dropped %d nodes outside the main network",
            spec.id,
            int((~mask).sum()),
        )

    meta = AreaMeta(
        id=spec.id,
        name=spec.name,
        circle={"lon": spec.lon, "lat": spec.lat, "radius_m": spec.radius_m},
        bbox=spec.bbox,
        scc_fraction=fraction,
    )

    edges = selection.edges
    mirror = GraphMirror.from_arrays(
        node_ids=selection.node_id,
        edge_u=edges["u"],
        edge_v=edges["v"],
        edge_key=edges["key"],
        length=edges["length"],
        travel_time=edges["travel_time"],
        speed_raw=edges["speed_kph"],
        lanes=edges["lanes"],
        elev_gain=edges["elev_gain"],
        node_x=selection.x,
        node_y=selection.y,
        street_count=selection.street_count,
    )
    area = AreaGraph(meta, mirror, dynamic=True)

    # Serialise the geometry now and drop the python objects: the frontend
    # asks for it right after the area is created, and the bytes are what the
    # registry budget counts.
    area.payloads.get_or_build("edges", lambda: _edge_rows(selection))

    n_pairs = settings.od_pairs_max
    area_config = _scaled_config(config, mirror)
    area.sample_research_pairs(n_pairs, area_config, seed)
    area.build_baseline(area_config, seed)

    meta.build_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info(
        "[AREA %s] built in %.1f s: %d nodes, %d edges, %d pairs",
        spec.id,
        meta.build_ms / 1000,
        counts["node_count"],
        counts["edge_count"],
        len(area.pairs),
    )
    return area


def _scaled_config(config, mirror):
    """The sampling config of this area.

    daily_km_driven is calibrated on Lausanne. Using it as is on a small area
    would inflate the flows and the BPR slowdown, so it follows the road
    length.
    """
    total_km = float(mirror.length.sum()) / 1000.0
    scaled = config.model_copy(
        update={
            "daily_km_driven": max(
                1.0, config.daily_km_driven * total_km / settings.reference_network_km
            )
        }
    )
    return scaled


def _edge_rows(selection: Selection) -> List[dict]:
    """The area's edges in the shape the frontend already reads."""
    edges = selection.edges
    offsets = edges["geom_offsets"]
    # Round every coordinate in one pass: about 10 cm, and it takes a third off
    # the payload. Per point it was two python floats and a round() each.
    points = np.round(edges["geom_flat"].astype(np.float64).reshape(-1, 2), 6).tolist()
    u = edges["u"].tolist()
    v = edges["v"].tolist()
    travel_time = edges["travel_time"].astype(np.float64).tolist()
    length = edges["length"].astype(np.float64).tolist()
    speed = edges["speed_kph"].astype(np.float64).tolist()

    return [
        {
            "u": u[i],
            "v": v[i],
            "coordinates": points[offsets[i] // 2 : offsets[i + 1] // 2],
            "travel_time": travel_time[i],
            "length": length[i],
            "speed_kph": speed[i],
            "name": edges["name"][i] or None,
            "highway": edges["highway"][i] or "unknown",
        }
        for i in range(len(u))
    ]
