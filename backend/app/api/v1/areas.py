"""Pick an area of Switzerland and get a routing graph for it."""

import logging
from typing import Optional

import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.models.area import AreaCreateRequest, AreaInfo, AreaLimits, AreaPreview
from app.services import area_builder
from app.services.area_builder import AreaRejected, AreaSpec
from app.services.area_graph import DEFAULT_AREA_ID, AreaGraph
from app.services.area_registry import AreaNotLoaded
from app.services.sampling.config import SamplingConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/areas", tags=["areas"])

# Set by main.py when the Swiss store is on disk. None means the app runs on
# the default city only, and every endpoint here answers 503.
graph_store = None


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


def _service():
    from app.api.v1.routes import graph_service

    return graph_service


def _spec(request: AreaCreateRequest) -> AreaSpec:
    return AreaSpec.from_circle(request.circle.lon, request.circle.lat, request.circle.radius_m)


def _info(area: AreaGraph) -> dict:
    meta = area.meta
    return {
        "id": meta.id,
        "circle": meta.circle,
        "bbox": meta.bbox,
        "node_count": area.mirror.n_nodes,
        "edge_count": area.mirror.n_edges,
        "scc_fraction": meta.scc_fraction,
        "od_pairs": len(area.pairs) if area.pairs else 0,
        "od_pairs_default": settings.od_pairs,
        "od_pairs_max": settings.od_pairs_max,
    }


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
    }


@router.post("/preview", response_model=AreaPreview)
def preview_area(request: AreaCreateRequest):
    """Can the tool run on this shape. Reads the cells, builds nothing."""
    return area_builder.preview(_store(), _spec(request))


@router.post("", response_model=AreaInfo, status_code=status.HTTP_201_CREATED)
async def create_area(request: AreaCreateRequest):
    """Build the routing graph of a circle, or return it if it is already loaded.

    The id comes from the geometry, so asking twice for the same spot gives
    the same area and the second call is free.
    """
    store = _store()
    spec = _spec(request)
    service = _service()

    existing = service.registry.get_optional(spec.id)
    if existing is not None:
        return _info(existing)

    def build():
        return area_builder.build(store, spec, SamplingConfig())

    try:
        area = await anyio.to_thread.run_sync(lambda: service.registry.get_or_build(spec.id, build))
    except AreaRejected as rejected:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": rejected.code,
                "message": rejected.message,
                "bbox": spec.bbox,
                **rejected.counts,
            },
        ) from rejected
    return _info(area)


@router.get("/{area_id}/edges")
def get_area_edges(area_id: str, request: Request):
    """The area's streets, in the shape the map already reads.

    Built once when the area is created and served from bytes with an ETag.
    """
    from app.api.v1.routes import _json_or_304

    service = _service()
    try:
        area = service.area(area_id)
    except AreaNotLoaded as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "area_not_loaded", "message": f"area {area_id!r} is not in memory"},
        ) from exc

    def missing():
        # Every drawn area gets its rows at build time, so reaching this is a
        # bug and an empty network on screen would hide it.
        raise HTTPException(status_code=500, detail=f"area {area_id!r} has no edge payload")

    # The default city has no store behind it: its geometry still comes from
    # the NetworkX graph.
    build = service.get_edge_geometries if area.meta.id == DEFAULT_AREA_ID else missing
    data, etag = area.payloads.get_or_build("edges", build)
    return _json_or_304(request, data, etag, "public, max-age=86400")


def set_store(store: Optional[object]) -> None:
    """Called by the lifespan once it knows whether the store is on disk."""
    global graph_store
    graph_store = store
