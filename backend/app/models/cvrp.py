"""CVRP models for API requests and responses."""

from typing import List

from pydantic import BaseModel, Field

from app.models.route import EdgeModification


class CVRPRequest(BaseModel):
    """Request body for CVRP solve endpoint."""

    waste_type: str = Field(default="DI", description="Waste type: DI, DV, PC, or VE")
    n_vehicles: int = Field(default=5, ge=1, le=50, description="Number of collection vehicles")
    vehicle_capacity: int = Field(default=5000, ge=100, description="Vehicle capacity in kg")
    max_runtime: int = Field(default=10, ge=1, le=120, description="Solver max runtime in seconds")
    waste_per_centroid: int = Field(default=10, ge=1, description="Waste per centroid in kg")
    load_unit: str = Field(default="kg", description="Load unit: 'kg' or 'kg_m'")
    edge_modifications: List[EdgeModification] = Field(
        default_factory=list, description="Edge modifications to respect during routing"
    )


class CVRPRouteSegment(BaseModel):
    """A single routed path segment for one vehicle trip."""

    route_id: int
    trip_id: int
    path_coordinates: List[List[float]]  # [[lon, lat], ...]
    load_kg: float


class CVRPEdgeLoad(BaseModel):
    """Aggregated load passing through a single graph edge."""

    u: int
    v: int
    load: float


class CVRPSolveResponse(BaseModel):
    """Response from CVRP solve endpoint."""

    n_routes: int
    n_missing_clients: int
    total_distance_m: float
    route_segments: List[CVRPRouteSegment]
    edge_loads: List[CVRPEdgeLoad]
    load_unit: str
    solve_time_ms: float
    centroids_used: int
