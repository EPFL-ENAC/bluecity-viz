"""Turning a scenario (closed streets, new speed limits) into weight arrays.

A request never mutates the graph. It derives its own per-edge arrays from the
area's base ones, so two requests can run at the same time and there is
nothing to roll back.
"""

from typing import List, Tuple

import numpy as np

from app.models.route import EdgeModification
from app.services.co2_calculator import CO2Calculator


def modifications_to_arrays(
    mirror,
    base_travel_time: np.ndarray,
    base_speed: np.ndarray,
    base_co2_g: np.ndarray,
    modifications: List[EdgeModification],
) -> Tuple[list, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Turn edge modifications into per-request weight arrays.

    Nothing is written to the shared graph. A removed edge gets a travel time
    of +inf, which igraph treats as "do not use", so there is no rollback and
    two requests cannot see each other's changes.

    Returns:
        (applied, travel_time, speed, co2_g, blocked, changed_edge_ids)
    """
    travel_time = base_travel_time.copy()
    speed = base_speed.copy()
    co2_g = base_co2_g.copy()
    blocked = np.zeros(mirror.n_edges, dtype=bool)

    applied: list = []
    changed: List[int] = []

    for mod in modifications:
        ids = mirror.edge_ids_for(mod.u, mod.v)
        if ids is None:
            continue

        if mod.action == "remove":
            blocked[ids] = True
            travel_time[ids] = np.inf
            applied.append(mod)
            changed.extend(int(i) for i in ids)

        elif mod.action == "modify" and mod.speed_kph is not None:
            keep = ids[np.abs(speed[ids] - mod.speed_kph) >= 0.1]
            if len(keep) > 0:
                speed[keep] = mod.speed_kph
                travel_time[keep] = mirror.length[keep] / (mod.speed_kph / 3.6)
                co2_g[keep] = CO2Calculator.edge_co2_array(
                    mirror.length[keep],
                    np.full(len(keep), float(mod.speed_kph)),
                    mirror.elev_gain[keep],
                )
                changed.extend(int(i) for i in keep)
            applied.append(mod)

    return (
        applied,
        travel_time,
        speed,
        co2_g,
        blocked,
        np.asarray(sorted(set(changed)), dtype=np.int64),
    )
