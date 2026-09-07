"""Route calculation endpoints."""

import hashlib
import logging
import threading
import traceback
from typing import Callable, List, Optional

import orjson
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

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
from app.services.graph_helpers import habitat_geojson
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routes", tags=["routes"])

# Initialize graph service (will be properly initialized with graph data)
graph_service = GraphService()

# Payloads that only depend on the graph: built once, then served from bytes
# with an ETag. The graph never changes while the process runs.
_payload_cache: dict = {}
_payload_lock = threading.Lock()
STATIC_CACHE_CONTROL = "public, max-age=86400"


def _cached_json(key: str, build: Callable[[], object]) -> tuple:
    """Return (bytes, etag) for a payload that never changes, building it once."""
    hit = _payload_cache.get(key)
    if hit is None:
        with _payload_lock:
            hit = _payload_cache.get(key)
            if hit is None:
                data = orjson.dumps(build())
                etag = '"' + hashlib.blake2b(data, digest_size=16).hexdigest() + '"'
                hit = (data, etag)
                _payload_cache[key] = hit
                logger.info("[CACHE] built %s payload, %.1f MB", key, len(data) / 1e6)
    return hit


def _json_or_304(request: Request, data: bytes, etag: str, cache_control: str) -> Response:
    """Serve cached bytes, or 304 when the client already has this version."""
    headers = {"ETag": etag, "Cache-Control": cache_control}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type="application/json", headers=headers)


class GraphInfoResponse(BaseModel):
    """Graph information response."""

    node_count: int
    edge_count: int
    sample_nodes: List[int]
    od_pairs: int = 0


@router.get("/graph-info", response_model=GraphInfoResponse)
def get_graph_info():
    """
    Get information about the loaded graph including sample node IDs.

    Returns:
        Graph statistics and sample node IDs for testing
    """
    try:
        info = graph_service.get_graph_info()
        return info
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
        with graph_service.lock:
            routes = graph_service.calculate_routes(
                pairs=request.pairs,
                weight=request.weight,
            )
        return RouteResponse(routes=routes)
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
        result = graph_service.recalculate_with_modifications(
            pairs=request.pairs,
            edge_modifications=request.edge_modifications,
            weight=request.weight,
            use_congestion=request.use_congestion,
            congestion_iterations=request.congestion_iterations,
            resample_destinations=request.resample_destinations,
            include_baseline=request.include_baseline,
        )
        result.pop("_timing_raw", None)
        return ORJSONResponse(result)
    except Exception as e:
        logger.error("Recalculate error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/baseline",
    response_model=None,
    responses={200: {"model": BaselineResponse}},
)
def get_baseline(request: Request):
    """
    Edge usage of the unmodified network.

    It is the same for every client and does not change until the server
    restarts, so it is served with an ETag. Fetch it once, then call
    /recalculate with include_baseline=false.
    """
    try:
        data, etag = _cached_json("baseline", graph_service.baseline_payload)
        return _json_or_304(request, data, etag, "no-cache")
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
        graph_service.clear_route_cache()

        if request.sampling_method == "research":
            from app.services.node_sampling_service import (
                SamplingConfig,
                generate_research_based_pairs,
            )

            config = request.sampling_config or SamplingConfig()
            with graph_service.lock:
                pairs = generate_research_based_pairs(
                    graph_service.graph,
                    n_pairs=request.count,
                    config=config,
                    seed=request.seed or 42,
                )
        else:
            with graph_service.lock:
                pairs = graph_service.generate_random_pairs(
                    count=request.count,
                    seed=request.seed,
                    radius_km=request.radius_km,
                )
        return pairs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
def clear_cache():
    """
    Clear the route calculation cache.

    Returns:
        Status message
    """
    try:
        graph_service.clear_route_cache()
        return {"status": "ok", "message": "Cache cleared"}
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
