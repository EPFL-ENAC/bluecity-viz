"""Pick an area of Switzerland and get a routing graph for it."""

import logging
from typing import Optional

import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.models.area import (
    MAX_MUNICIPALITIES,
    AreaCreateRequest,
    AreaInfo,
    AreaLimits,
    AreaPreview,
)
from app.services import area_builder
from app.services.area_builder import AreaRejected, AreaSpec, CircleSpec, MunicipalitySpec
from app.services.area_graph import AreaGraph, AreaNotReady
from app.services.area_registry import AreaNotLoaded
from app.services.sampling.config import SamplingConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/areas", tags=["areas"])

# Set by main.py when the Swiss store is on disk. None means no routing at
# all (not even the default area), and every endpoint here answers 503.
graph_store = None
# Set by main.py when the municipalities file is on disk. None means only the
# circle works.
municipalities = None


def _store():
    if graph_store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "no_swiss_graph",
                "message": (
                    "this server has no Swiss road network, so it can only run "
                    "on the city it was started with"
                ),
            },
        )
    return graph_store


def _municipalities():
    if municipalities is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "no_municipalities",
                "message": "this server has no municipal boundaries, pick a circle instead",
            },
        )
    return municipalities


def _service():
    from app.api.v1.routes import graph_service

    return graph_service


def _spec(request: AreaCreateRequest) -> AreaSpec:
    if request.circle is not None:
        circle = request.circle
        return CircleSpec.from_circle(circle.lon, circle.lat, circle.radius_m)
    return MunicipalitySpec.from_ids(request.municipalities, _municipalities())


def _info(area: AreaGraph) -> dict:
    meta = area.meta
    return {
        "id": meta.id,
        "kind": meta.kind,
        "name": meta.name,
        "circle": meta.circle,
        "municipalities": meta.municipalities,
        "outline": meta.outline,
        "bbox": meta.bbox,
        "node_count": area.mirror.n_nodes,
        "edge_count": area.mirror.n_edges,
        "scc_fraction": meta.scc_fraction,
        "od_pairs": len(area.pairs) if area.pairs else 0,
        "od_pairs_default": settings.od_pairs,
        "od_pairs_max": settings.od_pairs_max,
        "cvrp": _service().runs_cvrp(area),
        "ready": area.ready,
    }


def _loaded(area_id: str) -> AreaGraph:
    """The area, or the 404 the frontend answers by creating it again."""
    try:
        return _service().area(area_id)
    except AreaNotLoaded as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "area_not_loaded", "message": f"area {area_id!r} is not in memory"},
        ) from exc


@router.get("/limits", response_model=AreaLimits)
def get_limits():
    """The rules the picker checks while the user drags the circle."""
    store = graph_store
    return {
        "min_junctions": settings.area_min_junctions,
        "max_nodes": settings.area_max_nodes,
        "max_edges": settings.area_max_edges,
        "min_scc_fraction": settings.area_min_scc_fraction,
        "min_radius_m": settings.area_min_radius_m,
        "max_radius_m": settings.area_max_radius_m,
        "coverage_bbox": store.coverage_bbox if store else None,
        "has_municipalities": store is not None and municipalities is not None,
        "max_municipalities": MAX_MUNICIPALITIES,
    }


@router.post("/preview", response_model=AreaPreview)
def preview_area(request: AreaCreateRequest):
    """Can the tool run on this shape. Reads the cells, builds nothing."""
    return area_builder.preview(_store(), _spec(request))


@router.post("", response_model=AreaInfo, status_code=status.HTTP_201_CREATED)
async def create_area(request: AreaCreateRequest):
    """Build the routing graph of a shape, or return it if it is already loaded.

    The id comes from the geometry (or the sorted municipality numbers), so
    asking twice for the same spot gives the same area and the second call is
    free.

    The answer comes after the first build phase: the streets and their
    betweenness. The trips are drawn and routed after, in the background, and
    the area says `ready: false` until then (poll GET /areas/{id}).
    """
    store = _store()
    spec = _spec(request)
    service = _service()

    existing = service.registry.get_optional(spec.id)
    if existing is not None:
        return _info(existing)

    # One config for both phases: the trips must be drawn on the pool the
    # betweenness was computed on.
    config = SamplingConfig()

    def start():
        return area_builder.start(store, spec, config)

    def finish(area: AreaGraph):
        return area_builder.finish(area, config)

    try:
        area = await anyio.to_thread.run_sync(
            lambda: service.registry.get_or_build(spec.id, start, finish)
        )
    except AreaRejected as rejected:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": rejected.code,
                "message": rejected.message,
                "bbox": spec.bbox,
                "outline": spec.outline,
                **rejected.counts,
            },
        ) from rejected
    return _info(area)


@router.get("/{area_id}", response_model=AreaInfo)
def get_area(area_id: str):
    """One loaded area. The frontend polls it until `ready` is true."""
    return _info(_loaded(area_id))


@router.get("/{area_id}/betweenness")
def get_area_betweenness(area_id: str, request: Request):
    """The betweenness of every street, `{u, v, betweenness_centrality}` rows.

    There as soon as the area is created, before its trips. Served from bytes
    with an ETag. It never changes for one area, but the same id can come back
    after an eviction, so the browser asks again each time.
    """
    from app.api.v1.routes import _json_or_304, _not_ready

    area = _loaded(area_id)
    try:
        data, etag = area.payloads.get_or_build("betweenness", area.betweenness_rows)
    except AreaNotReady as exc:
        # an area made from a whole graph (the tests), before its baseline
        raise _not_ready(exc) from exc
    return _json_or_304(request, data, etag, "no-cache")


@router.get("/{area_id}/edges")
def get_area_edges(area_id: str, request: Request):
    """The area's streets, in the shape the map already reads.

    Built once when the area is created and served from bytes with an ETag.
    """
    from app.api.v1.routes import _json_or_304

    area = _loaded(area_id)

    def missing():
        # Every area gets its rows at build time, the default one too, so
        # reaching this is a bug and an empty network on screen would hide it.
        raise HTTPException(status_code=500, detail=f"area {area_id!r} has no edge payload")

    data, etag = area.payloads.get_or_build("edges", missing)
    return _json_or_304(request, data, etag, "public, max-age=86400")


def set_store(store: Optional[object]) -> None:
    """Called by the lifespan once it knows whether the store is on disk."""
    global graph_store
    graph_store = store


def set_municipalities(table: Optional[object]) -> None:
    """Called by the lifespan once it knows whether the boundaries are on disk."""
    global municipalities
    municipalities = table
