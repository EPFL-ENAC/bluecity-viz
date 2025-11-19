"""Route models for API requests and responses."""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class NodePair(BaseModel):
    """Origin-destination node pair."""

    origin: int = Field(..., description="Origin node ID")
    destination: int = Field(..., description="Destination node ID")


class Edge(BaseModel):
    """Graph edge representation."""

    u: int = Field(..., description="Start node ID")
    v: int = Field(..., description="End node ID")


class PathGeometry(BaseModel):
    """Path geometry as list of coordinates."""

    coordinates: List[List[float]] = Field(
        ..., description="List of [lon, lat] coordinates"
    )


class Route(BaseModel):
    """Calculated route information."""

    origin: int
    destination: int
    path: List[int] = Field(..., description="List of node IDs in the path")
    geometry: Optional[PathGeometry] = None
    travel_time: Optional[float] = Field(None, description="Total travel time")
    distance: Optional[float] = Field(None, description="Total distance in meters")


class RouteRequest(BaseModel):
    """Request to calculate routes."""

    pairs: List[NodePair] = Field(..., description="List of origin-destination pairs")
    weight: str = Field(default="travel_time", description="Edge weight attribute")
    include_geometry: bool = Field(default=True, description="Include path geometry")


class RouteResponse(BaseModel):
    """Response with calculated routes."""

    routes: List[Route]


class RecalculateRequest(BaseModel):
    """Request to recalculate routes with removed edges."""

    pairs: List[NodePair] = Field(..., description="List of origin-destination pairs")
    edges_to_remove: List[Edge] = Field(..., description="Edges to remove from graph")
    weight: str = Field(default="travel_time", description="Edge weight attribute")
    include_geometry: bool = Field(default=True, description="Include path geometry")


class RouteComparison(BaseModel):
    """Comparison between original and recalculated route."""

    origin: int
    destination: int
    original_route: Route
    new_route: Route
    removed_edge_on_path: Optional[Edge] = None


class RecalculateResponse(BaseModel):
    """Response with original and recalculated routes."""

    comparisons: List[RouteComparison]
    removed_edges: List[Edge]
