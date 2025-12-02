"""Route models for API requests and responses."""

from typing import List, Optional

from pydantic import BaseModel, Field


class NodePair(BaseModel):
    """Origin-destination node pair."""

    origin: int = Field(..., description="Origin node ID")
    destination: int = Field(..., description="Destination node ID")


class Edge(BaseModel):
    """Graph edge representation."""

    u: int = Field(..., description="Start node ID")
    v: int = Field(..., description="End node ID")


class EdgeModification(BaseModel):
    """Edge modification: remove or change properties."""

    u: int = Field(..., description="Start node ID")
    v: int = Field(..., description="End node ID")
    action: str = Field(default="remove", description="Action: 'remove' or 'modify'")
    speed_kph: Optional[float] = Field(None, description="New speed in km/h (for 'modify' action)")


class PathGeometry(BaseModel):
    """Path geometry as list of coordinates."""

    coordinates: List[List[float]] = Field(..., description="List of [lon, lat] coordinates")


class Route(BaseModel):
    """Calculated route information."""

    origin: int
    destination: int
    path: List[int] = Field(..., description="List of node IDs in the path")
    travel_time: Optional[float] = Field(None, description="Total travel time in seconds")
    distance: Optional[float] = Field(None, description="Total distance in meters")
    elevation_gain: Optional[float] = Field(None, description="Total elevation gain in meters")
    co2_emissions: Optional[float] = Field(None, description="Total CO2 emissions in grams")


class RouteRequest(BaseModel):
    """Request to calculate routes."""

    pairs: List[NodePair] = Field(..., description="List of origin-destination pairs")
    weight: str = Field(default="travel_time", description="Edge weight attribute")
    include_geometry: bool = Field(default=False, description="Include path geometry")


class RouteResponse(BaseModel):
    """Response with calculated routes."""

    routes: List[Route]


class RecalculateRequest(BaseModel):
    """Request to recalculate routes with edge modifications."""

    pairs: Optional[List[NodePair]] = Field(
        None, description="List of origin-destination pairs (uses default if not provided)"
    )
    edge_modifications: List[EdgeModification] = Field(
        default_factory=list, description="Edge modifications (remove or change speed)"
    )
    weight: str = Field(default="travel_time", description="Edge weight attribute")
    include_geometry: bool = Field(default=False, description="Include path geometry")


class RouteComparison(BaseModel):
    """Comparison between original and recalculated route."""

    origin: int
    destination: int
    original_route: Route
    new_route: Route
    modified_edge_on_path: Optional[EdgeModification] = None
    distance_delta: Optional[float] = Field(
        None, description="Additional distance in meters (new - original)"
    )
    distance_delta_percent: Optional[float] = Field(
        None, description="Percentage increase in distance"
    )
    time_delta: Optional[float] = Field(
        None, description="Additional travel time in seconds (new - original)"
    )
    time_delta_percent: Optional[float] = Field(
        None, description="Percentage increase in travel time"
    )
    is_affected: bool = Field(
        False, description="Whether this route was affected by edge modifications"
    )
    route_failed: bool = Field(
        False, description="Whether route calculation failed (no path found)"
    )


class EdgeUsageStats(BaseModel):
    """Edge usage statistics."""

    u: int = Field(..., description="Start node ID")
    v: int = Field(..., description="End node ID")
    count: int = Field(..., description="Number of times this edge was used")
    frequency: float = Field(..., description="Usage frequency (count / total_routes)")
    delta_count: Optional[int] = Field(None, description="Change in usage count (new - original)")
    delta_frequency: Optional[float] = Field(
        None, description="Change in frequency (new - original)"
    )
    co2_per_use: Optional[float] = Field(
        None, description="CO2 emissions per use of this edge in grams"
    )


class ImpactStatistics(BaseModel):
    """Aggregate statistics about the impact of removed edges."""

    total_routes: int = Field(..., description="Total number of routes analyzed")
    affected_routes: int = Field(..., description="Number of routes impacted by removed edges")
    failed_routes: int = Field(0, description="Number of routes that became impossible")
    total_distance_increase_km: float = Field(
        0.0, description="Total additional distance across all routes (km)"
    )
    total_time_increase_minutes: float = Field(
        0.0, description="Total additional travel time across all routes (minutes)"
    )
    avg_distance_increase_km: float = Field(
        0.0, description="Average additional distance per affected route (km)"
    )
    avg_time_increase_minutes: float = Field(
        0.0, description="Average additional travel time per affected route (minutes)"
    )
    max_distance_increase_km: float = Field(
        0.0, description="Maximum additional distance for a single route (km)"
    )
    max_time_increase_minutes: float = Field(
        0.0, description="Maximum additional travel time for a single route (minutes)"
    )
    avg_distance_increase_percent: float = Field(
        0.0, description="Average percentage increase in distance for affected routes"
    )
    avg_time_increase_percent: float = Field(
        0.0, description="Average percentage increase in travel time for affected routes"
    )
    total_co2_increase_grams: float = Field(
        0.0, description="Total additional CO2 emissions across all routes (grams)"
    )
    avg_co2_increase_grams: float = Field(
        0.0, description="Average additional CO2 emissions per affected route (grams)"
    )
    max_co2_increase_grams: float = Field(
        0.0, description="Maximum additional CO2 emissions for a single route (grams)"
    )
    avg_co2_increase_percent: float = Field(
        0.0, description="Average percentage increase in CO2 emissions for affected routes"
    )


class RecalculateResponse(BaseModel):
    """Response with edge usage statistics."""

    applied_modifications: List[EdgeModification]
    original_edge_usage: List[EdgeUsageStats] = Field(
        ..., description="Edge usage in original routes"
    )
    new_edge_usage: List[EdgeUsageStats] = Field(
        ..., description="Edge usage in new routes with delta"
    )
    impact_statistics: ImpactStatistics = Field(
        ..., description="Aggregate statistics about the impact of edge modifications"
    )
    routes: List[Route] = Field(
        default_factory=list, description="Calculated routes with paths for visualization"
    )


class GraphEdge(BaseModel):
    """Graph edge with geometry and metadata."""

    u: int = Field(..., description="Start node ID")
    v: int = Field(..., description="End node ID")
    geometry: PathGeometry = Field(..., description="Edge geometry")
    name: Optional[str] = Field(None, description="Street name")
    highway: Optional[str] = Field(None, description="Highway type")
    speed_kph: Optional[float] = Field(None, description="Speed limit in km/h")
    length: Optional[float] = Field(None, description="Length in meters")
    travel_time: Optional[float] = Field(None, description="Travel time in seconds")


class GraphData(BaseModel):
    """Complete graph data for visualization."""

    edges: List[GraphEdge] = Field(..., description="All graph edges")
    node_count: int = Field(..., description="Total number of nodes")
    edge_count: int = Field(..., description="Total number of edges")


class RandomPairsRequest(BaseModel):
    """Request to generate random node pairs."""

    count: int = Field(default=100, ge=1, le=10000, description="Number of pairs to generate")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    radius_km: Optional[float] = Field(
        default=2.0, ge=0.1, le=50.0, description="Radius in km from city center to sample nodes"
    )
