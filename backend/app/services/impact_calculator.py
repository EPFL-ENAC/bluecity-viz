"""Impact calculation for route comparisons."""

from typing import List, Tuple

import numpy as np

from app.models.route import EdgeModification, ImpactStatistics, Route, RouteComparison


def _positive(values: np.ndarray, selected: np.ndarray) -> Tuple[float, float]:
    """Sum and max of the selected values, 0 when nothing is selected."""
    picked = values[selected]
    if len(picked) == 0:
        return 0.0, 0.0
    return float(picked.sum()), float(picked.max())


def compute_impact_statistics_arrays(
    original,
    new,
    affected_idx: np.ndarray,
) -> ImpactStatistics:
    """Impact statistics from two RouteSets, without building Route objects.

    `new` holds the recalculated routes, one per entry of `affected_idx`, in
    the same order. Same rules as the per-object version: a route counts as
    affected when its distance or its time did not go down, and only increases
    are summed.
    """
    total = original.n_found
    if len(affected_idx) == 0:
        return ImpactStatistics(total_routes=total, affected_routes=0, failed_routes=0)

    ok = new.found
    failed = int((~ok).sum())

    od, nd = original.distance[affected_idx], new.distance
    ot, nt = original.travel_time[affected_idx], new.travel_time
    oc, nc = original.co2[affected_idx], new.co2

    def deltas(o, n):
        valid = ok & (o > 0) & (n > 0)
        return np.where(valid, n - o, np.nan), valid

    dd, _ = deltas(od, nd)
    dt, _ = deltas(ot, nt)
    dc, _ = deltas(oc, nc)

    with np.errstate(invalid="ignore"):
        is_affected = (dd >= 0) | (dt >= 0)
        sel_d = is_affected & (dd > 0)
        sel_t = is_affected & (dt > 0)
        sel_c = is_affected & (dc > 0)

    affected = int(is_affected.sum())
    dist_inc, max_dist = _positive(dd, sel_d)
    time_inc, max_time = _positive(dt, sel_t)
    co2_inc, max_co2 = _positive(dc, sel_c)

    def mean_percent(delta, orig, selected):
        picked = delta[selected] / orig[selected] * 100.0
        return float(picked.mean()) if len(picked) else 0.0

    return ImpactStatistics(
        total_routes=total,
        affected_routes=affected,
        failed_routes=failed,
        total_distance_increase_km=dist_inc / 1000,
        total_time_increase_minutes=time_inc / 60,
        avg_distance_increase_km=(dist_inc / 1000 / affected) if affected else 0.0,
        avg_time_increase_minutes=(time_inc / 60 / affected) if affected else 0.0,
        max_distance_increase_km=max_dist / 1000,
        max_time_increase_minutes=max_time / 60,
        avg_distance_increase_percent=mean_percent(dd, od, sel_d),
        avg_time_increase_percent=mean_percent(dt, ot, sel_t),
        total_co2_increase_grams=co2_inc,
        avg_co2_increase_grams=(co2_inc / affected) if affected else 0.0,
        max_co2_increase_grams=max_co2,
        avg_co2_increase_percent=mean_percent(dc, oc, sel_c),
    )


def find_affected_routes(original_routes: List[Route], modified_edges_set: set) -> List[int]:
    """Find routes that pass through modified edges. Returns indices."""
    indices = []
    for i, route in enumerate(original_routes):
        for j in range(len(route.path) - 1):
            if (route.path[j], route.path[j + 1]) in modified_edges_set:
                indices.append(i)
                break
    return indices


def find_modified_edge_on_path(
    route: Route, modifications: List[EdgeModification]
) -> EdgeModification | None:
    """Find which modified edge was on a route's original path."""
    for mod in modifications:
        for i in range(len(route.path) - 1):
            if route.path[i] == mod.u and route.path[i + 1] == mod.v:
                return mod
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
    modifications: List[EdgeModification],
    compute_comparisons: bool = True,
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
            if compute_comparisons:
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

        if compute_comparisons:
            comparisons.append(
                RouteComparison(
                    origin=orig.origin,
                    destination=orig.destination,
                    original_route=orig,
                    new_route=new,
                    modified_edge_on_path=find_modified_edge_on_path(orig, modifications),
                    distance_delta=deltas["distance_delta"],
                    distance_delta_percent=deltas["distance_delta_percent"],
                    time_delta=deltas["time_delta"],
                    time_delta_percent=deltas["time_delta_percent"],
                    is_affected=deltas["is_affected"],
                    route_failed=False,
                )
            )

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

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
