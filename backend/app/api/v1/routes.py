"""Route calculation endpoints."""

from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel

from app.models.route import (
    RouteRequest,
    RouteResponse,
    RecalculateRequest,
    RecalculateResponse,
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
