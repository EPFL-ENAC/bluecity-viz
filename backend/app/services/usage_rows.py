"""The per-street rows of a routing result.

One row per (u, v) group of the graph mirror: how many routed trips use it,
how that compares with the unmodified network, the CO2 of that traffic and the
betweenness of the street. This is the shape the API returns and the frontend
colours the map with.
"""

import logging
import time
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def build_edge_usage_rows(
    mirror,
    counts: np.ndarray,
    total_routes: int,
    co2_per_km: np.ndarray,
    original_counts: Optional[np.ndarray] = None,
    original_co2_per_km: Optional[np.ndarray] = None,
    betweenness: Optional[np.ndarray] = None,
    delta_betweenness: Optional[np.ndarray] = None,
) -> List[dict]:
    """Build the per-(u, v) usage rows of a recalculate response.

    Every array is indexed by (u, v) group, see GraphMirror.uv_group. Only
    groups used by a route produce a row. With `original_counts`, a group used
    before the change also gets one, with a count of 0: a closed street has to
    show what it lost, or the deltas do not add up to the real change.

    `co2_per_km` is the CO2 of the traffic on each group, in g/km: the grams of
    one vehicle over the edge times the number of routes on it, divided by the
    length. Times the length and summed over every group, it is the sum of the
    CO2 of all the routes. `original_co2_per_km` is the same before the
    modification, and gives `delta_co2_g_per_km`.

    Values are rounded here:
    the payload holds about 6,400 rows twice, and full float precision adds
    around 30 % of bytes that no one reads.
    """
    t0 = time.perf_counter()
    in_use = counts > 0
    if original_counts is not None:
        in_use |= original_counts > 0
    used = np.flatnonzero(in_use)
    if len(used) == 0:
        return []

    freq = counts[used] / total_routes if total_routes > 0 else np.zeros(len(used))
    order = np.argsort(-freq, kind="stable")
    used = used[order]
    freq = freq[order]

    us = mirror.uv_u[used]
    vs = mirror.uv_v[used]
    cnt = counts[used].astype(np.int64)
    co2 = np.round(co2_per_km[used], 1)
    freq_r = np.round(freq, 6)

    delta_cnt = delta_freq = None
    if original_counts is not None:
        delta_cnt = (counts[used] - original_counts[used]).astype(np.int64)
        orig_freq = original_counts[used] / total_routes if total_routes > 0 else 0.0
        delta_freq = np.round(freq - orig_freq, 6)

    d_co2 = (
        np.round(co2_per_km[used] - original_co2_per_km[used], 1)
        if original_co2_per_km is not None
        else None
    )
    bc = np.round(betweenness[used], 2) if betweenness is not None else None
    d_bc = np.round(delta_betweenness[used], 2) if delta_betweenness is not None else None

    # Keys whose value would be null are left out. The frontend reads every
    # optional field with `?? 0`, and 3 nulls per row cost about 400 kB.
    rows = []
    for i in range(len(used)):
        row = {
            "u": int(us[i]),
            "v": int(vs[i]),
            "count": int(cnt[i]),
            "frequency": float(freq_r[i]),
            "co2_g_per_km": float(co2[i]),
        }
        if delta_cnt is not None:
            row["delta_count"] = int(delta_cnt[i])
            row["delta_frequency"] = float(delta_freq[i])
        if d_co2 is not None:
            row["delta_co2_g_per_km"] = float(d_co2[i])
        if bc is not None:
            row["betweenness_centrality"] = float(bc[i])
        if d_bc is not None:
            row["delta_betweenness"] = float(d_bc[i])
        rows.append(row)

    logger.debug(
        "[TIMING] edge usage rows | %d rows | %.1f ms", len(rows), (time.perf_counter() - t0) * 1000
    )
    return rows
