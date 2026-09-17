"""Comparing the modified network with the untouched one.

Every number here is *new minus old* over the same trips, so it carries a
sign: closing a street lengthens trips, raising a speed limit shortens them,
and the tool has to be able to say both.

Three groups of trips, and the difference matters when reading the table:

    affected  the trip's route changed. Its distance, time or CO2 is not what
              it was, in either direction. These are the trips the totals and
              the averages are computed over.
    failed    the trip had a route and has none now, because the scenario cut
              its destination off. A failure has no finite cost, so it cannot
              be added to the totals: it is reported on its own, and one
              failed trip is worse news than any amount of detour.
    the rest  same route, same numbers, not counted anywhere.
"""

from typing import Tuple

import numpy as np

from app.models.route import ImpactStatistics


def compare_runs(baseline, assignment) -> ImpactStatistics:
    """Impact statistics for an assignment against the baseline routes.

    `assignment.routes` holds the trips that were routed again: all of them
    when `assignment.rerouted` is None, otherwise one route per entry of
    `rerouted`, in that order. A trip nobody re-routed is unchanged by
    construction, so leaving it out of the comparison is exact, not an
    approximation.
    """
    total = baseline.n_found
    new = assignment.routes
    idx = assignment.rerouted
    if idx is None:
        idx = np.arange(len(baseline))
    if len(idx) == 0:
        return ImpactStatistics(total_routes=total, affected_routes=0, failed_routes=0)

    had_route = baseline.found[idx]
    has_route = new.found
    failed = int((had_route & ~has_route).sum())

    old_d, new_d = baseline.distance[idx], new.distance
    old_t, new_t = baseline.travel_time[idx], new.travel_time
    old_c, new_c = baseline.co2[idx], new.co2

    # A trip we can compare: it had a route, it still has one, and both have
    # a length (a zero would make the percentage meaningless).
    comparable = had_route & has_route & (old_d > 0) & (new_d > 0) & (old_t > 0) & (new_t > 0)
    dd = np.where(comparable, new_d - old_d, 0.0)
    dt = np.where(comparable, new_t - old_t, 0.0)
    dc = np.where(comparable, new_c - old_c, 0.0)

    # Affected: the route really moved. A trip re-routed onto a path that
    # happens to cost exactly the same was not affected by the change.
    affected = comparable & ((dd != 0) | (dt != 0))
    n_affected = int(affected.sum())

    return ImpactStatistics(
        total_routes=total,
        affected_routes=n_affected,
        failed_routes=failed,
        total_distance_change_km=float(dd[affected].sum()) / 1000,
        total_time_change_minutes=float(dt[affected].sum()) / 60,
        total_co2_change_grams=float(dc[affected].sum()),
        avg_distance_change_km=_mean(dd, affected) / 1000,
        avg_time_change_minutes=_mean(dt, affected) / 60,
        avg_co2_change_grams=_mean(dc, affected),
        max_distance_increase_km=_worst(dd, affected) / 1000,
        max_time_increase_minutes=_worst(dt, affected) / 60,
        max_co2_increase_grams=_worst(dc, affected),
        avg_distance_change_percent=_mean_percent(dd, old_d, affected),
        avg_time_change_percent=_mean_percent(dt, old_t, affected),
        avg_co2_change_percent=_mean_percent(dc, old_c, affected),
    )


def elastic_impact(baseline, new) -> ImpactStatistics:
    """Impact when the destinations were drawn again.

    Trip i of the new set is not trip i of the old one, so no per-trip
    comparison means anything. Only the totals over the whole demand do, and
    that is what the panel shows.
    """
    failed = int((~new.found).sum())
    return ImpactStatistics(
        total_routes=baseline.n_found,
        affected_routes=0,
        failed_routes=failed,
        total_distance_change_km=float(new.distance.sum() - baseline.distance.sum()) / 1000,
        total_time_change_minutes=float(new.travel_time.sum() - baseline.travel_time.sum()) / 60,
        total_co2_change_grams=float(new.co2.sum() - baseline.co2.sum()),
    )


def _mean(values: np.ndarray, selected: np.ndarray) -> float:
    n = int(selected.sum())
    return float(values[selected].sum()) / n if n else 0.0


def _worst(values: np.ndarray, selected: np.ndarray) -> float:
    """The largest increase, 0 when nothing got worse."""
    picked = values[selected]
    return float(max(picked.max(), 0.0)) if len(picked) else 0.0


def _mean_percent(delta: np.ndarray, original: np.ndarray, selected: np.ndarray) -> float:
    picked = delta[selected] / original[selected] * 100.0
    return float(picked.mean()) if len(picked) else 0.0


__all__: Tuple[str, ...] = ("compare_runs", "elastic_impact")
