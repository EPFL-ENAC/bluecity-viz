"""In-process CVRP benchmark on the real Lausanne data.

Run from backend/:
    uv run python scripts/bench_cvrp.py [waste_type] [max_runtime]

Loads the graph and the centroid CSVs like the app does, solves once, and prints
the solve time, the solver's total distance and the length of the rendered
segments (great-circle over the returned coordinates). No HTTP call, no server
needed.
"""

import asyncio
import logging
import sys
from pathlib import Path

import osmnx as ox

from app.config import settings
from app.models.cvrp import CVRPRequest
from app.services.cvrp_service import CVRPService
from app.services.graph_service import GraphService

logging.basicConfig(level=logging.WARNING)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def rendered_length_m(segments) -> float:
    total = 0.0
    for seg in segments:
        coords = seg.path_coordinates
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
            total += float(ox.distance.great_circle(lat1, lon1, lat2, lon2))
    return total


async def main() -> None:
    waste_type = sys.argv[1] if len(sys.argv) > 1 else "DI"
    max_runtime = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    graph_service = GraphService()
    graph_service.load_graph(str(BACKEND_DIR / settings.graph_path))

    cvrp = CVRPService()
    cvrp.set_graph_service(graph_service)
    cvrp.initialize(str(BACKEND_DIR / settings.cvrp_centroids_dir))

    request = CVRPRequest(waste_type=waste_type, max_runtime=max_runtime)
    result = await cvrp.solve(request)

    rendered = rendered_length_m(result.route_segments)
    gap = abs(result.total_distance_m - rendered) / max(rendered, 1.0) * 100

    print(f"waste_type        {waste_type}")
    print(f"centroids_used    {result.centroids_used}")
    print(f"n_routes          {result.n_routes}")
    print(f"n_missing         {result.n_missing_clients}")
    print(f"solve_time_ms     {result.solve_time_ms:.0f}")
    print(f"total_distance_m  {result.total_distance_m:.0f}")
    print(f"rendered_m        {rendered:.0f}")
    print(f"gap_percent       {gap:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
