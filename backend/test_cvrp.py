"""Integration test for CVRPService.

Run from backend/ directory:
    uv run python test_cvrp.py
"""

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent
GRAPH_PATH = BACKEND_DIR / "data" / "lausanne.graphml"
CENTROIDS_DIR = (
    BACKEND_DIR
    / "../../processing/SP04_Waste"
    / "Waste collection points by types (density-based spatial clustering)"
).resolve()


def check_prerequisites():
    ok = True
    if not GRAPH_PATH.exists():
        print(f"ERROR: Graph not found at {GRAPH_PATH}")
        ok = False
    if not CENTROIDS_DIR.exists():
        print(f"ERROR: Centroids dir not found at {CENTROIDS_DIR}")
        ok = False
    return ok


async def run_test():
    from app.models.cvrp import CVRPRequest
    from app.services.cvrp_service import CVRPService
    from app.services.graph_service import GraphService

    # 1. Load graph
    print("Loading graph …")
    graph_service = GraphService()
    graph_service.load_graph(str(GRAPH_PATH))
    print(f"  {len(graph_service.graph.nodes)} nodes, {len(graph_service.graph.edges)} edges")

    # 2. Initialize CVRP service
    print("Initializing CVRP service …")
    cvrp_service = CVRPService()
    cvrp_service.set_graph_service(graph_service)
    cvrp_service.initialize(str(CENTROIDS_DIR))

    available = list(cvrp_service._node_dfs.keys())
    print(f"  Available waste types: {available}")

    if not available:
        print("ERROR: No waste types loaded — check centroid CSV paths")
        sys.exit(1)

    # 3. Solve
    waste_type = available[0]
    print(f"\nSolving CVRP for waste type '{waste_type}' …")
    request = CVRPRequest(
        waste_type=waste_type,
        n_vehicles=3,
        vehicle_capacity=5000,
        max_runtime=5,
        max_centroids=50,   # keep small for quick test
        load_unit="kg",
        edge_modifications=[],
    )

    response = await cvrp_service.solve(request)

    print(f"  Routes:           {response.n_routes}")
    print(f"  Missing clients:  {response.n_missing_clients}")
    print(f"  Total distance:   {response.total_distance_m:.0f} m")
    print(f"  Route segments:   {len(response.route_segments)}")
    print(f"  Edge loads:       {len(response.edge_loads)}")
    print(f"  Solve time:       {response.solve_time_ms:.0f} ms")
    print(f"  Centroids used:   {response.centroids_used}")

    assert response.n_routes > 0, "Expected at least one route"
    assert len(response.edge_loads) > 0, "Expected non-empty edge loads"
    print("\nAll assertions passed!")

    # 4. Test centroids GeoJSON
    geojson = cvrp_service.get_centroids_geojson(waste_type)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) > 0
    print(f"Centroids GeoJSON: {len(geojson['features'])} features")


def main():
    if not check_prerequisites():
        sys.exit(1)

    asyncio.run(run_test())


if __name__ == "__main__":
    main()
