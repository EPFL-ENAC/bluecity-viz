"""A scenario: the streets the user closed or slowed down.

A request never touches the graph. It copies the area's base arrays, writes
its changes into the copies and routes on those, so two requests run side by
side without seeing each other and there is nothing to roll back. A closed
street is a travel time of +inf, which igraph reads as "never use this edge".
"""

from dataclasses import dataclass, field
from typing import List

import numpy as np

from app.models.route import EdgeModification
from app.services.co2_calculator import CO2Calculator

# Two speeds this close are the same speed limit; asking for 50 on a street
# already at 50 changes nothing.
SPEED_TOLERANCE_KPH = 0.1


@dataclass
class Scenario:
    """The network as this request sees it, one value per igraph edge.

    Attributes:
        travel_time  free-flow seconds, +inf on a closed street
        speed_kph    the speed limit in force
        co2_g        grams one vehicle emits driving the edge at that speed
        blocked      True on a closed street
        changed      igraph ids of the edges this scenario really changed
        applied      the modifications that really changed something, echoed
                     back to the client
    """

    travel_time: np.ndarray
    speed_kph: np.ndarray
    co2_g: np.ndarray
    blocked: np.ndarray
    changed: np.ndarray
    applied: List[EdgeModification] = field(default_factory=list)

    @property
    def key(self) -> tuple:
        """A hashable identity, for memoising what depends on the scenario."""
        return tuple(sorted((m.u, m.v, m.action, m.speed_kph) for m in self.applied))

    @property
    def is_empty(self) -> bool:
        """True when nothing changed, so the result is the baseline."""
        return len(self.changed) == 0


def build_scenario(mirror, base_co2_g: np.ndarray, modifications: List[EdgeModification]):
    """Apply the modifications to copies of the area's base arrays.

    A modification that changes nothing is not applied: a street the client
    asks to set to 50 km/h when it is already at 50, or one the graph does not
    have. `applied` therefore says what really happened, not what was asked.
    """
    scenario = Scenario(
        travel_time=mirror.travel_time.copy(),
        speed_kph=mirror.speed_kph.copy(),
        co2_g=base_co2_g.copy(),
        blocked=np.zeros(mirror.n_edges, dtype=bool),
        changed=np.empty(0, dtype=np.int64),
    )
    changed: List[int] = []

    for mod in modifications:
        ids = mirror.edge_ids_for(mod.u, mod.v)
        if ids is None:
            continue

        if mod.action == "remove":
            scenario.blocked[ids] = True
            scenario.travel_time[ids] = np.inf
            scenario.applied.append(mod)
            changed.extend(int(i) for i in ids)

        elif mod.action == "modify" and mod.speed_kph is not None:
            # A street is several igraph edges when osmnx split it; only the
            # ones not already at that speed change.
            keep = ids[np.abs(scenario.speed_kph[ids] - mod.speed_kph) >= SPEED_TOLERANCE_KPH]
            if len(keep) == 0:
                continue
            scenario.speed_kph[keep] = mod.speed_kph
            scenario.travel_time[keep] = mirror.length[keep] / (mod.speed_kph / 3.6)
            scenario.co2_g[keep] = CO2Calculator.edge_co2_array(
                mirror.length[keep],
                np.full(len(keep), float(mod.speed_kph)),
                mirror.elev_gain[keep],
            )
            scenario.applied.append(mod)
            changed.extend(int(i) for i in keep)

    scenario.changed = np.asarray(sorted(set(changed)), dtype=np.int64)
    return scenario
