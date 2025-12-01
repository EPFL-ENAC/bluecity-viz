"""Impact calculation for route comparisons."""

from typing import List, Tuple

from app.models.route import Edge, ImpactStatistics, Route, RouteComparison


def find_affected_routes(
    original_routes: List[Route], removed_edges_set: set
) -> Tuple[List[int], List[Route]]:
    """Find routes that pass through removed edges. Returns (indices, routes)."""
    indices = []
    for i, route in enumerate(original_routes):
        for j in range(len(route.path) - 1):
            if (route.path[j], route.path[j + 1]) in removed_edges_set:
                indices.append(i)
                break
    return indices


def find_removed_edge_on_path(route: Route, removed_edges: List[Edge]) -> Edge | None:
    """Find which removed edge was on a route's original path."""
    for edge in removed_edges:
        for i in range(len(route.path) - 1):
            if route.path[i] == edge.u and route.path[i + 1] == edge.v:
                return edge
    return None


def calculate_route_deltas(orig: Route, new: Route) -> dict:
    """Calculate deltas between original and new route."""
    result = {
        "distance_delta": None,
        "distance_delta_percent": None,
        "time_delta": None,
        "time_delta_percent": None,
        "co2_delta": None,
        "co2_delta_percent": None,
        "is_affected": False,
    }

    if orig.distance and new.distance:
        result["distance_delta"] = new.distance - orig.distance
        if orig.distance > 0:
            result["distance_delta_percent"] = (result["distance_delta"] / orig.distance) * 100
        if result["distance_delta"] >= 0:
            result["is_affected"] = True

    if orig.travel_time and new.travel_time:
        result["time_delta"] = new.travel_time - orig.travel_time
        if orig.travel_time > 0:
            result["time_delta_percent"] = (result["time_delta"] / orig.travel_time) * 100
        if result["time_delta"] >= 0:
            result["is_affected"] = True

    if orig.co2_emissions and new.co2_emissions:
        result["co2_delta"] = new.co2_emissions - orig.co2_emissions
        if orig.co2_emissions > 0:
            result["co2_delta_percent"] = (result["co2_delta"] / orig.co2_emissions) * 100

    return result


def compute_impact_statistics(
    original_routes: List[Route],
    new_routes_by_index: dict,
    affected_indices: List[int],
    removed_edges: List[Edge],
) -> Tuple[ImpactStatistics, List[RouteComparison]]:
    """Compute impact statistics and route comparisons."""
    total = len(original_routes)
    affected = failed = 0
    dist_inc = time_inc = co2_inc = 0.0
    max_dist = max_time = max_co2 = 0.0
    dist_pcts, time_pcts, co2_pcts = [], [], []
    comparisons = []

    for idx in affected_indices:
        orig = original_routes[idx]
        new = new_routes_by_index.get(idx)

        if not new or not new.path:
            failed += 1
            comparisons.append(
                RouteComparison(
                    origin=orig.origin,
                    destination=orig.destination,
                    original_route=orig,
                    new_route=new or orig,
                    is_affected=True,
                    route_failed=True,
                )
            )
            continue

        deltas = calculate_route_deltas(orig, new)
        if deltas["is_affected"]:
            affected += 1

            if deltas["distance_delta"] and deltas["distance_delta"] >= 0:
                dist_inc += deltas["distance_delta"]
                max_dist = max(max_dist, deltas["distance_delta"])
                if deltas["distance_delta_percent"]:
                    dist_pcts.append(deltas["distance_delta_percent"])

            if deltas["time_delta"] and deltas["time_delta"] >= 0:
                time_inc += deltas["time_delta"]
                max_time = max(max_time, deltas["time_delta"])
                if deltas["time_delta_percent"]:
                    time_pcts.append(deltas["time_delta_percent"])

            if deltas["co2_delta"] and deltas["co2_delta"] >= 0:
                co2_inc += deltas["co2_delta"]
                max_co2 = max(max_co2, deltas["co2_delta"])
                if deltas["co2_delta_percent"]:
                    co2_pcts.append(deltas["co2_delta_percent"])

        comparisons.append(
            RouteComparison(
                origin=orig.origin,
                destination=orig.destination,
                original_route=orig,
                new_route=new,
                removed_edge_on_path=find_removed_edge_on_path(orig, removed_edges),
                distance_delta=deltas["distance_delta"],
                distance_delta_percent=deltas["distance_delta_percent"],
                time_delta=deltas["time_delta"],
                time_delta_percent=deltas["time_delta_percent"],
                is_affected=deltas["is_affected"],
                route_failed=False,
            )
        )

    avg = lambda lst: sum(lst) / len(lst) if lst else 0.0

    stats = ImpactStatistics(
        total_routes=total,
        affected_routes=affected,
        failed_routes=failed,
        total_distance_increase_km=dist_inc / 1000,
        total_time_increase_minutes=time_inc / 60,
        avg_distance_increase_km=(dist_inc / 1000 / affected) if affected else 0,
        avg_time_increase_minutes=(time_inc / 60 / affected) if affected else 0,
        max_distance_increase_km=max_dist / 1000,
        max_time_increase_minutes=max_time / 60,
        avg_distance_increase_percent=avg(dist_pcts),
        avg_time_increase_percent=avg(time_pcts),
        total_co2_increase_grams=co2_inc,
        avg_co2_increase_grams=(co2_inc / affected) if affected else 0,
        max_co2_increase_grams=max_co2,
        avg_co2_increase_percent=avg(co2_pcts),
    )

    return stats, comparisons
