"""Congestion: how traffic slows a street down.

The model is the speed form of the Bureau of Public Roads curve. A street
carrying `flow` vehicles a day, with `lanes` lanes, drives at

    speed(flow) = speed_free / (1 + flow / (lanes · k))

where `k` is `SamplingConfig.betweenness_to_slowdown`, the flow per lane at
which the speed halves (at flow = lanes·k the denominator is 2). In travel
time that is

    time(flow) = length / (speed(flow) / 3.6) = time_free · (1 + flow / (lanes · k))

which is the standard BPR curve `t = t0 · (1 + a·(v/c)^b)` with capacity
c = lanes·k, a = 1 and **b = 1**. The usual road-engineering values are
a = 0.15 and b = 4, a curve that stays flat until capacity and then explodes.
This one is linear: it spreads traffic away from busy streets gently, and it
never produces the sharp jams of a real assignment model.

`flow` comes from one of two places, and that is the difference between the
two scenario modes:
  * the **betweenness** of the network, a structural estimate of the load
  * the **volumes** the routed trips actually put on each street

Everything here works on numpy arrays indexed by igraph edge id and returns
new arrays. Nothing is written to the mirror or to the NetworkX graph.
"""

import logging
from typing import Optional

import numpy as np

from app.services.routing_engine import RouteSet, route_pairs

logger = logging.getLogger(__name__)


def congested_speed(
    mirror, flow: np.ndarray, speed_kph: np.ndarray, betweenness_to_slowdown: float
) -> np.ndarray:
    """BPR congested speed per edge, in km/h. See the module docstring."""
    return speed_kph / (1.0 + flow / (mirror.lanes * betweenness_to_slowdown))


def congested_travel_time(
    mirror,
    flow: np.ndarray,
    speed_kph: np.ndarray,
    betweenness_to_slowdown: float,
    blocked: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Travel time in seconds under the BPR speed reduction, per edge.

    `blocked` marks closed streets: they get +inf, which igraph reads as
    "never use this edge".
    """
    speed = congested_speed(mirror, flow, speed_kph, betweenness_to_slowdown)
    with np.errstate(divide="ignore", invalid="ignore"):
        seconds = np.where(speed > 0, mirror.length / (speed / 3.6), np.inf)
    if blocked is not None:
        seconds = np.where(blocked, np.inf, seconds)
    return seconds


def flow_from_counts(mirror, counts: np.ndarray, daily_km_driven: float) -> np.ndarray:
    """Turn simulated trip counts into a daily vehicle flow (veh/day).

    The OD sample is a few tens of thousands of trips, not a day of traffic,
    so the counts are scaled to the vehicle-km the city really drives:

        flow = counts · daily_km_driven · 1000 / Σ(counts · length)

    which is the same normalisation betweenness gets, so the two are
    interchangeable inside the BPR formula.
    """
    total_veh_m = float((counts * mirror.length).sum())
    factor = (daily_km_driven * 1000.0 / total_veh_m) if total_veh_m > 0 else 1.0
    return counts * factor


def run_congestion_routing(
    mirror,
    pairs,
    travel_time: np.ndarray,
    speed_kph: np.ndarray,
    blocked: Optional[np.ndarray],
    n_iterations: int,
    config,
) -> RouteSet:
    """Route every trip, then iterate volume -> speed -> reroute.

    The first pass is free flow: everybody takes the fastest empty-city route,
    which overloads the same few streets. Each further pass re-routes on the
    travel times the volumes seen so far imply, moving toward the state where
    no driver can do better by switching route (a Wardrop user equilibrium).

    Volumes are averaged with MSA (method of successive averages,
    ``x_k = x_{k-1} + (y_k - x_{k-1}) / k``) so the assignment does not flip
    between two extremes, and two iterations already converge reasonably.

    Note the returned routes are the last assignment, not the averaged
    volumes: the map shows one plausible assignment, close to but not exactly
    the averaged equilibrium.
    """
    routes = route_pairs(mirror, pairs, travel_time)
    volumes = routes.edge_counts(mirror.n_edges)

    # k is the MSA step number: the pass above produced x_1, so the first
    # update below is x_2 = x_1 + (y_2 - x_1) / 2.
    for k in range(2, n_iterations + 2):
        flow = flow_from_counts(mirror, volumes, config.daily_km_driven)
        weights = congested_travel_time(
            mirror, flow, speed_kph, config.betweenness_to_slowdown, blocked
        )
        routes = route_pairs(mirror, pairs, weights)
        volumes = volumes + (routes.edge_counts(mirror.n_edges) - volumes) / k

    return routes
