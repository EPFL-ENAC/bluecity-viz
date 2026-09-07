"""BPR congestion model and betweenness centrality, on the graph mirror.

The Bureau of Public Roads speed-reduction formula is used everywhere:

    speed_cong = speed_free / (1 + flow / (lanes * betweenness_to_slowdown))

where `flow` is in veh/day and betweenness_to_slowdown is the flow at which
the speed is halved. `flow` is either the betweenness centrality (theoretical
load) or the measured route volume, depending on the strategy.

Everything here works on numpy arrays indexed by igraph edge id and returns
new arrays. Nothing is written to the shared NetworkX graph.
"""

import logging
import time
from typing import List, Optional

import numpy as np

from app.services.co2_calculator import CO2Calculator
from app.services.routing_engine import RouteSet, route_pairs

logger = logging.getLogger(__name__)

# Betweenness is computed in chunks of source nodes so a single igraph call
# does not hold the GIL for too long. python-igraph never releases it, so an
# uninterrupted call of 500 ms freezes every other request for 500 ms.
# Betweenness is a sum over (source, target) pairs, so chunking the sources
# and adding the results gives exactly the same values.
# 50 sources per chunk measured best: 20 was 10 % slower overall without
# cutting the worst latency spike, which comes from elsewhere (numpy and
# orjson also hold the GIL).
BC_SOURCE_CHUNK = 50


def congested_travel_time(
    mirror,
    flow: np.ndarray,
    speed_kph: np.ndarray,
    blocked: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Travel time in seconds under the BPR speed reduction, per edge.

        speed_cong = speed_free / (1 + flow / (lanes * betweenness_to_slowdown))
        time_s     = length_m / (speed_cong / 3.6)

    `blocked` marks removed edges: they get +inf so no route uses them.
    """
    from app.services.sampling.config import SamplingConfig

    config = SamplingConfig()
    speed_cong = speed_kph / (1.0 + flow / (mirror.lanes * config.betweenness_to_slowdown))
    with np.errstate(divide="ignore", invalid="ignore"):
        seconds = np.where(speed_cong > 0, mirror.length / (speed_cong / 3.6), np.inf)
    if blocked is not None:
        seconds = np.where(blocked, np.inf, seconds)
    return seconds


def normalise_flow(mirror, counts: np.ndarray, config) -> np.ndarray:
    """Turn simulated route counts into daily vehicle flow (veh/day).

    factor = daily_km_driven * 1000 / sum(count * length)
    """
    total_veh_m = float((counts * mirror.length).sum())
    factor = (config.daily_km_driven * 1000.0 / total_veh_m) if total_veh_m > 0 else 1.0
    return counts * factor


def compute_betweenness(
    mirror,
    weights: np.ndarray,
    sample_vertices: List[int],
    config,
    label: str = "BC",
) -> np.ndarray:
    """Sampled edge betweenness on the mirror, normalised to veh/day.

    The same node sample is reused across calls so baseline and modified BC
    stay comparable. Returns one value per igraph edge id.
    """
    t0 = time.perf_counter()
    raw = np.zeros(mirror.n_edges, dtype=np.float64)

    for start in range(0, len(sample_vertices), BC_SOURCE_CHUNK):
        chunk = sample_vertices[start : start + BC_SOURCE_CHUNK]
        # numpy array, not a list: igraph converts a python list of 10k floats
        # on every call, which cost more than the chunking saved.
        part = mirror.h.edge_betweenness(True, None, weights, chunk, sample_vertices)
        raw += np.asarray(part, dtype=np.float64)

    total = float((raw * mirror.length).sum())
    factor = (config.daily_km_driven * 1000.0 / total) if total > 0 else 1.0
    logger.debug(
        "[TIMING] %s | nodes=%d | chunks=%d | %.0f ms",
        label,
        len(sample_vertices),
        (len(sample_vertices) + BC_SOURCE_CHUNK - 1) // BC_SOURCE_CHUNK,
        (time.perf_counter() - t0) * 1000,
    )
    return raw * factor


def co2_per_km(mirror, speed_kph: np.ndarray) -> np.ndarray:
    """CO2 in g/km per edge at the given speeds (grade aware)."""
    co2_g = CO2Calculator.edge_co2_array(mirror.length, speed_kph, mirror.elev_gain)
    length_km = mirror.length / 1000.0
    return np.where(length_km > 0, co2_g / np.where(length_km > 0, length_km, 1.0), 0.0)


def congested_speed(mirror, flow: np.ndarray, speed_kph: np.ndarray, config) -> np.ndarray:
    """BPR congested speed per edge, in km/h."""
    return speed_kph / (1.0 + flow / (mirror.lanes * config.betweenness_to_slowdown))


def run_congestion_routing(
    mirror,
    pairs,
    travel_time: np.ndarray,
    speed_kph: np.ndarray,
    blocked: Optional[np.ndarray],
    n_iterations: int,
    config,
) -> RouteSet:
    """Route every pair, then iterate volume -> speed -> reroute toward equilibrium.

    Iteration 0 is free flow. Each later iteration re-routes on travel times
    derived from the volumes seen so far. Volumes are averaged with MSA
    (method of successive averages), so the flow does not flip between two
    extreme assignments and 2 iterations already converge reasonably.
    """
    routes = route_pairs(mirror, pairs, travel_time)
    volumes = routes.edge_counts(mirror.n_edges)

    for k in range(2, n_iterations + 2):
        flow = normalise_flow(mirror, volumes, config)
        weights = congested_travel_time(mirror, flow, speed_kph, blocked)
        routes = route_pairs(mirror, pairs, weights)
        # MSA: x_k = x_{k-1} + (y_k - x_{k-1}) / k
        volumes = volumes + (routes.edge_counts(mirror.n_edges) - volumes) / k

    return routes
