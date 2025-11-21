"""Route calculation endpoints."""

from typing import List, Optional

from app.models.route import (
    GraphData,
    GraphEdge,
    NodePair,
    PathGeometry,
    RandomPairsRequest,
    RecalculateRequest,
    RecalculateResponse,
    RouteRequest,
    RouteResponse,
)
from app.services.graph_service import GraphService
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

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
    Recalculate shortest paths after removing specified edges.

    Args:
        request: Recalculation request with edges to remove and route pairs

    Returns:
        Original and recalculated routes with comparison data
    """
    try:
        result = await graph_service.recalculate_with_removed_edges(
            pairs=request.pairs,
            edges_to_remove=request.edges_to_remove,
            weight=request.weight,
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
    Generate random origin-destination node pairs within specified radius.

    Args:
        request: Request with count, optional seed, and radius from city center

    Returns:
        List of random node pairs within the specified radius
    """
    try:
        # Clear route cache when generating new pairs
        graph_service.clear_route_cache()
        
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
    import time
    import json
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
