"""Route calculation endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.models.route import (
    GraphData,
    NodePair,
    RandomPairsRequest,
    RecalculateRequest,
    RecalculateResponse,
    RouteRequest,
    RouteResponse,
)
from app.services.graph_service import GraphService

router = APIRouter(prefix="/routes", tags=["routes"])

# Initialize graph service (will be properly initialized with graph data)
graph_service = GraphService()


class GraphInfoResponse(BaseModel):
    """Graph information response."""

    node_count: int
    edge_count: int
    sample_nodes: List[int]


@router.get("/graph-info", response_model=GraphInfoResponse)
async def get_graph_info():
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
async def calculate_routes(request: RouteRequest):
    """
    Calculate shortest paths between origin-destination pairs.

    Args:
        request: Route calculation request with pairs of nodes

    Returns:
        Calculated routes with paths and metadata
    """
    try:
        routes = await graph_service.calculate_routes(
            pairs=request.pairs,
            weight=request.weight,
        )
        return RouteResponse(routes=routes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate", response_model=RecalculateResponse)
async def recalculate_routes(request: RecalculateRequest):
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
        result = await graph_service.recalculate_with_modifications(
            pairs=request.pairs,
            edge_modifications=request.edge_modifications,
            weight=request.weight,
            use_congestion=request.use_congestion,
            congestion_iterations=request.congestion_iterations,
            resample_destinations=request.resample_destinations,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph", response_model=GraphData)
async def get_graph():
    """
    Get complete graph data for visualization.

    Returns:
        Complete graph with all edges and their geometries
    """
    try:
        graph_data = graph_service.get_graph_data()
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/random-pairs", response_model=List[NodePair])
async def generate_random_pairs(request: RandomPairsRequest):
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
            pairs = generate_research_based_pairs(
                graph_service.graph,
                n_pairs=request.count,
                config=config,
                seed=request.seed or 42,
            )
        else:
            pairs = graph_service.generate_random_pairs(
                count=request.count,
                seed=request.seed,
                radius_km=request.radius_km,
            )
        return pairs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_cache():
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


@router.get("/edge-geometries")
async def get_edge_geometries(response: Response, limit: Optional[int] = None):
    """
    Get all edge geometries from the graph for Deck.gl visualization.

    Args:
        limit: Optional limit on number of edges to return (for testing)

    Returns:
        List of edges with u, v node IDs and coordinate arrays
    """
    import json
    import time

    try:
        request_start = time.time()

        data_start = time.time()
        edges = graph_service.get_edge_geometries(limit=limit)
        data_time = time.time() - data_start

        # Manually serialize to check size
        json_start = time.time()
        json_str = json.dumps(edges)
        json_time = time.time() - json_start
        uncompressed_size = len(json_str) / (1024 * 1024)  # MB

        total_time = time.time() - request_start

        print(f"[PERF] Data generation: {data_time:.3f}s for {len(edges)} edges")
        print(f"[PERF] JSON serialization: {json_time:.3f}s")
        print(f"[PERF] Uncompressed JSON size: {uncompressed_size:.2f} MB")
        print(f"[PERF] Total endpoint time: {total_time:.3f}s")

        # Add Server-Timing headers
        response.headers["Server-Timing"] = (
            f"data;dur={data_time*1000:.1f}, "
            f"json;dur={json_time*1000:.1f}, "
            f"total;dur={total_time*1000:.1f}"
        )

        return edges
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/habitat-geojson")
async def get_habitat_geojson():
    """
    Get habitat density as a GeoJSON FeatureCollection for MapLibre visualization.
    """
    try:
        graph = graph_service.graph
        features = []
        for u, v, data in graph.edges(data=True):
            coords = (
                [[lon, lat] for lon, lat in data["geometry"].coords]
                if "geometry" in data
                else [
                    [graph.nodes[u]["x"], graph.nodes[u]["y"]],
                    [graph.nodes[v]["x"], graph.nodes[v]["y"]],
                ]
            )
            length = float(data.get("length", 1.0) or 1.0)
            habitat = float(data.get("habitat_area_m2", 0.0) or 0.0)
            density = habitat / length if length > 0 else 0.0
            if habitat > 0:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {
                            "u": int(u),
                            "v": int(v),
                            "habitat_density_m2_per_m": density,
                        },
                    }
                )
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
