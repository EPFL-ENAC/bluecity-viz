"""Route calculation endpoints."""

import logging
import traceback
from typing import Callable, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

from app.config import settings
from app.models.route import (
    BaselineResponse,
    GraphData,
    NodePair,
    RandomPairsRequest,
    RecalculateRequest,
    RecalculateResponse,
    RouteRequest,
    RouteResponse,
)
from app.services.area_registry import AreaNotLoaded
from app.services.graph_helpers import habitat_geojson
from app.services.graph_service import GraphService
from app.services.payload_cache import PayloadCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routes", tags=["routes"])

# Initialize graph service (will be properly initialized with graph data)
graph_service = GraphService()

# Payloads of the NetworkX graph: built once, then served from bytes with an
# ETag. That graph never changes while the process runs. Payloads that belong
# to an area live on the area, so evicting it frees them too.
_payload_cache = PayloadCache()
STATIC_CACHE_CONTROL = "public, max-age=86400"


def _cached_json(key: str, build: Callable[[], object]) -> tuple:
    """Return (bytes, etag) for a payload that never changes, building it once."""
    return _payload_cache.get_or_build(key, build)


def _area(area_id: Optional[str]):
    """The area a request names, as a 404 when it is gone."""
    try:
        return graph_service.area(area_id)
    except AreaNotLoaded as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "area_not_loaded",
                "message": (
                    f"area {exc.area_id!r} is not in memory: create it again "
                    "with POST /api/v1/areas"
                ),
            },
        ) from exc


def _json_or_304(request: Request, data: bytes, etag: str, cache_control: str) -> Response:
    """Serve cached bytes, or 304 when the client already has this version."""
    headers = {"ETag": etag, "Cache-Control": cache_control}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type="application/json", headers=headers)


class GraphInfoResponse(BaseModel):
    """Graph information response."""

    area_id: str = ""
    bbox: Optional[List[float]] = None
    scc_fraction: float = 1.0
    node_count: int
    edge_count: int
    sample_nodes: List[int]
    od_pairs: int = 0
    od_pairs_default: int = 0
    od_pairs_max: int = 0
    od_origins: int = 0
    n_destinations_per_origin: Optional[int] = None


@router.get("/graph-info", response_model=GraphInfoResponse)
def get_graph_info(
    area_id: Optional[str] = Query(
        None, description="Which area to read. None means the default one."
    ),
):
    """
    Get information about an area: its size, its OD pairs and sample node IDs.

    Returns:
        Graph statistics and sample node IDs for testing
    """
    try:
        return _area(area_id).graph_info()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate", response_model=RouteResponse)
def calculate_routes(request: RouteRequest):
    """
    Calculate shortest paths between origin-destination pairs.

    Args:
        request: Route calculation request with pairs of nodes

    Returns:
        Calculated routes with paths and metadata
    """
    try:
        routes = _area(request.area_id).calculate_routes(
            pairs=request.pairs,
            weight=request.weight,
        )
        return RouteResponse(routes=routes)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/recalculate",
    response_model=None,
    responses={200: {"model": RecalculateResponse}},
)
def recalculate_routes(request: RecalculateRequest) -> dict:
    """
    Recalculate shortest paths after applying edge modifications.
    Modifications can remove edges or change their speed.
    Uses default pre-calculated pairs if none provided in request.

    Args:
        request: Recalculation request with edge modifications and optional route pairs

    Returns:
        Original and recalculated routes with comparison data
    """
    try:
        result = _area(request.area_id).recalculate_with_modifications(
            pairs=request.pairs,
            edge_modifications=request.edge_modifications,
            weight=request.weight,
            use_congestion=request.use_congestion,
            congestion_iterations=request.congestion_iterations,
            resample_destinations=request.resample_destinations,
            include_baseline=request.include_baseline,
            od_pairs=request.od_pairs,
        )
        phases = result.pop("_timing_raw", {})
        # Server-Timing shows the phases in the browser network panel, so the
        # per-request [TIMING] log line can stay at DEBUG.
        headers = {
            "Server-Timing": ", ".join(f"{name};dur={ms:.1f}" for name, ms in phases.items())
        }
        return ORJSONResponse(result, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recalculate error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/baseline",
    response_model=None,
    responses={200: {"model": BaselineResponse}},
)
def get_baseline(
    request: Request,
    od_pairs: Optional[int] = Query(
        None,
        ge=1,
        description="How many OD pairs. Defaults to the OD_PAIRS setting.",
    ),
    area_id: Optional[str] = Query(
        None, description="Which area to read. None means the default one."
    ),
):
    """
    Edge usage of the unmodified network, for a given number of OD pairs.

    It does not change until the server restarts, so it is served with an
    ETag, one per pair count. Fetch it once, then call /recalculate with the
    same od_pairs and include_baseline=false.
    """
    if od_pairs is not None and od_pairs > settings.od_pairs_max:
        raise HTTPException(
            status_code=422,
            detail=(
                f"od_pairs must be at most {settings.od_pairs_max} "
                f"(OD_PAIRS_MAX, the set sampled at startup)"
            ),
        )
    try:
        area = _area(area_id)
        n = min(od_pairs or settings.od_pairs, settings.od_pairs_max)
        # The cache lives on the area, so two areas never share an ETag and
        # evicting an area frees its payloads.
        data, etag = area.payloads.get_or_build(f"baseline:{n}", lambda: area.baseline_payload(n))
        return _json_or_304(request, data, etag, "no-cache")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/graph",
    response_model=None,
    responses={200: {"model": GraphData}},
    deprecated=True,
)
def get_graph(request: Request):
    """
    Get complete graph data for visualization.

    Deprecated: the frontend loads /geodata/lausanne.geojson instead. Kept for
    scripts and notebooks. Served from a cached payload with an ETag.
    """
    try:
        data, etag = _cached_json("graph", graph_service.get_graph_data)
        return _json_or_304(request, data, etag, STATIC_CACHE_CONTROL)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/random-pairs", response_model=List[NodePair])
def generate_random_pairs(request: RandomPairsRequest):
    """
    Generate random origin-destination node pairs.

    Supports two sampling methods:
    - 'simple': Random uniform sampling within radius (fast)
    - 'research': Research-based sampling with betweenness centrality and
                  lognormal trip distribution (realistic, slower)

    Args:
        request: Request with count, optional seed, and sampling method/config

    Returns:
        List of node pairs
    """
    try:
        # Clear route cache when generating new pairs
        graph_service.clear_route_cache(request.area_id)

        if request.sampling_method == "research":
            from app.services.sampling import (
                SamplingConfig,
                generate_research_based_pairs_mirror,
            )

            config = request.sampling_config or SamplingConfig()
            pairs = generate_research_based_pairs_mirror(
                _area(request.area_id).mirror,
                n_pairs=request.count,
                config=config,
                seed=request.seed or 42,
            ).to_nodepairs()
        else:
            pairs = _area(request.area_id).generate_random_pairs(
                count=request.count,
                seed=request.seed,
                radius_km=request.radius_km,
            )
        return pairs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
def clear_cache(
    area_id: Optional[str] = Query(
        None, description="Which area to clear. None clears every loaded area."
    ),
):
    """
    Clear the route calculation cache.

    Returns:
        Status message
    """
    try:
        graph_service.clear_route_cache(area_id)
        return {"status": "ok", "message": "Cache cleared"}
    except AreaNotLoaded:
        raise HTTPException(status_code=404, detail={"code": "area_not_loaded"}) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EdgeGeometry(BaseModel):
    """Edge geometry for frontend visualization."""

    u: int
    v: int
    coordinates: List[List[float]]
    travel_time: Optional[float] = None
    length: Optional[float] = None
    name: Optional[str] = None
    highway: Optional[str] = None


@router.get("/edge-geometries", deprecated=True)
def get_edge_geometries(request: Request, limit: Optional[int] = None):
    """
    Get all edge geometries from the graph for Deck.gl visualization.

    Deprecated: the frontend loads /geodata/lausanne.geojson instead. The full
    payload is built once and served from bytes with an ETag. A `limit` is only
    for quick tests, so it is built on the fly and not cached.
    """
    try:
        if limit is not None:
            return ORJSONResponse(graph_service.get_edge_geometries(limit=limit))
        data, etag = _cached_json("edge-geometries", graph_service.get_edge_geometries)
        return _json_or_304(request, data, etag, STATIC_CACHE_CONTROL)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/habitat-geojson")
def get_habitat_geojson(request: Request):
    """
    Get habitat density as a GeoJSON FeatureCollection for MapLibre visualization.

    The graph does not change while the process runs, so the payload is built
    once and served from bytes with an ETag.
    """
    try:

        def build():
            with graph_service.lock:
                return habitat_geojson(graph_service.graph)

        data, etag = _cached_json("habitat-geojson", build)
        return _json_or_304(request, data, etag, STATIC_CACHE_CONTROL)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
