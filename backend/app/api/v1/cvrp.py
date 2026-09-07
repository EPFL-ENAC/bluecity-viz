"""CVRP API endpoints for waste collection route optimization."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.cvrp import CVRPRequest, CVRPSolveResponse, WasteType
from app.services.cvrp_service import CVRPService

router = APIRouter(prefix="/cvrp", tags=["cvrp"])

# Default service instance. main.py puts it on app.state at startup; tests put
# their own there, so nothing reads this module attribute directly.
cvrp_service: CVRPService = CVRPService()


def get_cvrp_service(request: Request) -> CVRPService:
    """Return the CVRP service held on the application state."""
    return request.app.state.cvrp_service


@router.get("/centroids")
async def get_centroids(
    waste_type: WasteType = "DI",
    service: CVRPService = Depends(get_cvrp_service),
):
    """Return pre-snapped waste collection centroids as GeoJSON FeatureCollection."""
    if not service.is_ready(waste_type):
        raise HTTPException(
            status_code=404,
            detail=f"Waste type '{waste_type}' not available. "
            f"Service may not be initialized or CSV not found.",
        )
    return service.get_centroids_geojson(waste_type)


@router.post("/solve", response_model=CVRPSolveResponse)
async def solve_cvrp(
    request: CVRPRequest,
    service: CVRPService = Depends(get_cvrp_service),
):
    """Solve the CVRP for waste collection routing.

    Applies any edge modifications (speed limits, road closures) before solving,
    then returns vehicle routes and edge load statistics.
    """
    try:
        return await service.solve(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
