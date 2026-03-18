"""CVRP API endpoints for waste collection route optimization."""

from fastapi import APIRouter, HTTPException

from app.models.cvrp import CVRPRequest, CVRPSolveResponse
from app.services.cvrp_service import CVRPService

router = APIRouter(prefix="/cvrp", tags=["cvrp"])

# Module-level service instance, initialized in main.py lifespan
cvrp_service: CVRPService = CVRPService()


@router.get("/centroids")
async def get_centroids(waste_type: str = "DI"):
    """Return pre-snapped waste collection centroids as GeoJSON FeatureCollection."""
    if not cvrp_service.is_ready(waste_type):
        raise HTTPException(
            status_code=404,
            detail=f"Waste type '{waste_type}' not available. "
            f"Service may not be initialized or CSV not found.",
        )
    return cvrp_service.get_centroids_geojson(waste_type)


@router.post("/solve", response_model=CVRPSolveResponse)
async def solve_cvrp(request: CVRPRequest):
    """Solve the CVRP for waste collection routing.

    Applies any edge modifications (speed limits, road closures) before solving,
    then returns vehicle routes and edge load statistics.
    """
    try:
        return await cvrp_service.solve(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
