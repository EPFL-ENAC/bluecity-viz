"""Impact calculation for route comparisons."""

from typing import Tuple

import numpy as np

from app.models.route import ImpactStatistics


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
