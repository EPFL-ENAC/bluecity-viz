"""Running one scenario: what changes when a street closes.

The question the tool answers is a comparison. The same trips are routed
twice, once on the untouched network (the *baseline*) and once on the network
the user modified, and the answer is the difference.

So both sides have to be built the same way. Routes are chosen on congested
travel times, distances and durations are reported free flow, and the trips
are the same ones. A scenario that changes nothing then changes no number,
which is the property every mode here has to keep.

The pipeline, in order:

    1. pick the trips and their baseline  (`_baseline_run`)
    2. build the scenario arrays          (`modifications.build_scenario`)
    3. assign the trips to the modified network, one of three ways below
    4. compare the two runs               (`impact`)
    5. turn the counts into per-street rows (`usage_rows`)

Step 3 is the modelling choice, and the three ways differ in what they let the
traveller change:

    targeted      only the trips that used a modified street pick a new route,
                  on travel times that betweenness says are congested.
                  Cheap, and what the tool runs by default.
    equilibrium   every trip is re-routed, repeatedly, on the travel times the
                  volumes themselves imply. Congestion moves load across the
                  whole network, so nothing can be held fixed.
    elastic       trips keep their origin but choose a new destination: a
                  traveller whose destination became unreachable goes
                  somewhere else rather than driving twice as far.

Every strategy returns an `Assignment`, and the rest of the pipeline does not
care which one produced it.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from app.config import settings
from app.models.route import EdgeModification, NodePair, TimingStats
from app.services import bpr
from app.services.impact import compare_runs, elastic_impact
from app.services.modifications import Scenario, build_scenario
from app.services.routing_engine import PairArrays, RouteSet, route_pairs
from app.services.usage_rows import build_edge_usage_rows
from app.services.utils.timing import timed

logger = logging.getLogger(__name__)


@dataclass
class Assignment:
    """Where the trips went on the modified network.

    Attributes:
        routes    the new routes. When `rerouted` is None this covers every
                  trip; otherwise one route per entry of `rerouted`, in order.
        rerouted  indices of the trips that were routed again, or None when
                  every trip was. Knowing which is which is what lets the
                  edge counts be patched instead of recomputed.
        bc        betweenness of the modified network, per igraph edge, or
                  None when the scenario changed nothing.
        elastic   True when the trips drew new destinations, so trip i of
                  `routes` is not trip i of the baseline and only totals can
                  be compared.
        counts    the edge counts to report, when they are not simply the
                  edges of `routes`. The equilibrium model sets it: what it
                  puts on the map is the volume averaged over its passes, not
                  the last assignment.
    """

    routes: RouteSet
    rerouted: Optional[np.ndarray]
    bc: Optional[np.ndarray]
    elastic: bool = False
    counts: Optional[np.ndarray] = None

    @property
    def is_full_reroute(self) -> bool:
        return self.rerouted is None


@dataclass
class BaselineRun:
    """The untouched network, for the trips this request is about."""

    pairs: PairArrays
    routes: RouteSet
    counts: np.ndarray  # per igraph edge
    counts_group: np.ndarray  # per street
    co2_per_km_group: np.ndarray  # per street
    rows: list  # the usage rows, already built when this is a cached baseline


def recalculate(
    area,
    pairs: Optional[List[NodePair]] = None,
    edge_modifications: Optional[List[EdgeModification]] = None,
    use_congestion: bool = False,
    congestion_iterations: int = 1,
    resample_destinations: bool = False,
    include_baseline: bool = True,
    od_pairs: Optional[int] = None,
    node_weighting: str = "uniform",
) -> dict:
    """Route a scenario and return the per-street usage, against the baseline.

    `node_weighting` picks the OD sample: the trips, the baseline they are
    compared with, and the pool elastic demand draws destinations from.
    """
    if not area.mirror:
        raise RuntimeError("Graph not loaded")
    # Drawn on the first request that asks for it, so outside the timings.
    # Raises when the baseline is missing, or the area has no population.
    od = area.od_set(node_weighting)

    mirror = area.mirror
    t_total = time.perf_counter()
    timing: dict = {}

    # The equilibrium model needs a baseline run the same way, or its deltas
    # would show congestion spreading traffic rather than the scenario.
    equilibrium_iterations = congestion_iterations if use_congestion else None

    with timed("cache_lookup", timing):
        base = _baseline_run(area, od, pairs, od_pairs, node_weighting, equilibrium_iterations)

    with timed("apply_modifications", timing):
        scenario = build_scenario(mirror, area.base_co2_g, edge_modifications or [])

    if resample_destinations and od.nodes is not None and area.sampling_config:
        assignment = _assign_elastic(area, base, od.nodes, scenario, timing)
    elif use_congestion:
        assignment = _assign_equilibrium(area, base, scenario, congestion_iterations, timing)
    else:
        assignment = _assign_targeted(area, base, scenario, timing)

    with timed("impact_stats", timing):
        if assignment.elastic:
            impact = elastic_impact(base.routes, assignment.routes)
        else:
            impact = compare_runs(base.routes, assignment)

    with timed("edge_usage", timing):
        rows = _usage_rows(area, base, assignment, scenario, include_baseline)

    timing["total"] = (time.perf_counter() - t_total) * 1000
    logger.debug("[TIMING] recalculate | %s", " ".join(f"{k}={v:.1f}ms" for k, v in timing.items()))

    return {
        "od_pairs": len(base.pairs),
        "applied_modifications": [m.model_dump() for m in scenario.applied],
        "original_edge_usage": rows["original"],
        "new_edge_usage": rows["new"],
        "impact_statistics": impact.model_dump(),
        "timing": _timing_stats(timing).model_dump(),
        "_timing_raw": timing,
    }


# ── 1. the trips and their baseline ───────────────────────────────────────────


def _baseline_run(
    area,
    od,
    pairs,
    od_pairs: Optional[int],
    node_weighting: str,
    equilibrium_iterations: Optional[int] = None,
) -> BaselineRun:
    """The untouched network for the trips of this request.

    Normally the trips are the first N of the area's OD sample, whose baseline
    was computed at startup and only has to be sliced. A client may also send
    its own pairs, and then the baseline is routed here and memoised.

    `equilibrium_iterations` asks for the baseline of the equilibrium model
    instead: the same trips on the same untouched network, but assigned by the
    same MSA loop the scenario will run. Built on first use, then cached.
    """
    mirror = area.mirror
    if pairs:
        pairs = PairArrays.coerce(pairs)
        routes = area.route_set_for(pairs)
        counts = routes.edge_counts(mirror.n_edges)
        return BaselineRun(
            pairs=pairs,
            routes=routes,
            counts=counts,
            counts_group=mirror.group_sum(counts),
            co2_per_km_group=area.traffic_co2_per_km(area.base_co2_g, counts),
            rows=[],
        )

    if od.pairs is None:
        raise RuntimeError("No pairs available")
    n_pairs = min(od_pairs or settings.od_pairs, len(od.pairs))
    if equilibrium_iterations is not None:
        cached = area.equilibrium_baseline_for(n_pairs, equilibrium_iterations, node_weighting)
    else:
        cached = area.baseline_for(n_pairs, node_weighting)
    return BaselineRun(
        pairs=cached.pairs,
        routes=cached.routes,
        counts=cached.counts,
        counts_group=cached.counts_group,
        co2_per_km_group=cached.co2_per_km_group,
        rows=cached.usage_rows,
    )


# ── 3. the three ways to assign the trips ─────────────────────────────────────


def _assign_targeted(area, base: BaselineRun, scenario: Scenario, timing: dict) -> Assignment:
    """Re-route only the trips that used a modified street.

    Everybody else keeps the route they had, which is what makes this cheap:
    closing one street usually touches a small share of the trips.

    The new route is chosen on the betweenness of the *modified* network, put
    through the BPR curve, which is the rule the baseline was routed with on
    the untouched network. Same rule on both sides, so the difference is the
    scenario and nothing else. Without congestion in it, every displaced trip
    would pile onto the single next-fastest street.

    Two limits worth knowing. Closing a street moves the betweenness of every
    other street a little, so in principle a trip that never used it could
    prefer another route; it keeps the one it had. And a street made *faster*
    only draws the trips already on it, since nobody else is re-routed.
    """
    mirror = area.mirror

    with timed("affected_routes", timing):
        rerouted = base.routes.routes_using(scenario.changed)

    with timed("delta_bc", timing):
        bc = None
        weights = area.congested_time
        if not scenario.is_empty:
            bc = area.betweenness_for(scenario)
            weights = bpr.congested_travel_time(
                mirror,
                bc,
                scenario.speed_kph,
                area.sampling_config.betweenness_to_slowdown,
                scenario.blocked,
            )

    with timed("route_calculation", timing):
        routes = route_pairs(mirror, base.pairs.subset(rerouted), weights)
        routes.compute_metrics(mirror, scenario.travel_time, scenario.co2_g)

    return Assignment(routes=routes, rerouted=rerouted, bc=bc)


def _assign_equilibrium(
    area, base: BaselineRun, scenario: Scenario, iterations: int, timing: dict
) -> Assignment:
    """Re-route every trip, iterating volume -> speed -> reroute.

    Congestion moves load across the whole network, so no trip can be assumed
    unaffected: a street far from the closure gets slower because the traffic
    that left the closure arrived on it. See `bpr.run_congestion_routing`.

    The baseline this is compared with is an MSA run of the same length on the
    untouched network (`area.equilibrium_baseline_for`), not the free-flow
    one: otherwise the deltas would mostly show congestion spreading traffic
    around, which happens with or without the scenario.

    The map gets the averaged volumes, the impact table the routes of the last
    pass, which is the only thing a per-trip comparison can be made on.
    """
    mirror = area.mirror

    with timed("delta_bc", timing):
        bc = area.betweenness_for(scenario) if not scenario.is_empty else None

    with timed("route_calculation", timing):
        routes, volumes = bpr.run_congestion_routing(
            mirror,
            base.pairs,
            scenario.travel_time,
            scenario.speed_kph,
            scenario.blocked,
            iterations,
            area.sampling_config,
        )
        routes.compute_metrics(mirror, scenario.travel_time, scenario.co2_g)

    return Assignment(routes=routes, rerouted=None, bc=bc, counts=volumes)


def _assign_elastic(
    area, base: BaselineRun, od_nodes, scenario: Scenario, timing: dict
) -> Assignment:
    """Draw new destinations, then route the trips that result.

    Fixed demand says a traveller drives to the same place whatever it costs.
    Elastic demand lets the destination move: closing a road then shows up as
    trips getting shorter, not as an implausible total travel time.

    The draw and the routing both use the congested times of the modified
    network, which is the rule the startup draw followed on the untouched one.
    A destination is picked on how long it really takes to get there, so a
    closed street pushes the draw away from what is behind it.
    """
    from app.services.sampling.od_sampler import resample_od_destinations

    mirror = area.mirror

    with timed("delta_bc", timing):
        bc = None
        weights = area.congested_time
        if not scenario.is_empty:
            bc = area.betweenness_for(scenario)
            weights = bpr.congested_travel_time(
                mirror,
                bc,
                scenario.speed_kph,
                area.sampling_config.betweenness_to_slowdown,
                scenario.blocked,
            )

    with timed("od_resampling", timing):
        new_pairs = resample_od_destinations(
            base.pairs,
            od_nodes,
            mirror,
            area.congested_time,
            weights,
            area.sampling_config,
            area.seed,
        ).pairs

    with timed("route_calculation", timing):
        routes = route_pairs(mirror, new_pairs, weights)
        routes.compute_metrics(mirror, scenario.travel_time, scenario.co2_g)

    return Assignment(routes=routes, rerouted=None, bc=bc, elastic=True)


# ── 5. the per-street rows ────────────────────────────────────────────────────


def counts_after(mirror, base: BaselineRun, assignment: Assignment) -> np.ndarray:
    """How many trips use each edge once the scenario is applied.

    An assignment that brought its own counts (the equilibrium model, whose
    answer is an averaged volume) reports them. A full reroute is simply
    counted. A targeted one is patched onto the baseline counts: take away the
    old routes of the trips that moved, add their new ones, and every trip
    that did not move keeps counting.
    """
    if assignment.counts is not None:
        return assignment.counts
    if assignment.is_full_reroute:
        return assignment.routes.edge_counts(mirror.n_edges)

    counts = base.counts.copy()
    counts -= base.routes.counts_for(assignment.rerouted, mirror.n_edges)
    counts += assignment.routes.edge_counts(mirror.n_edges)
    return np.maximum(counts, 0.0)


def _usage_rows(
    area, base: BaselineRun, assignment: Assignment, scenario: Scenario, include_baseline: bool
) -> dict:
    """The two row sets a recalculate response carries."""
    mirror = area.mirror
    counts = counts_after(mirror, base, assignment)
    counts_group = mirror.group_sum(counts)
    # scenario.co2_g, not the base array: a speed limit changes the grams of
    # its own street, the same way it changed the trips' totals.
    co2_per_km = area.traffic_co2_per_km(scenario.co2_g, counts)
    total_routes = base.routes.n_found
    baseline_bc_group = area.baseline.bc_group
    delta_bc_group = (
        mirror.group_sum(assignment.bc - area.baseline.bc) if assignment.bc is not None else None
    )

    if not include_baseline:
        # The baseline never changes. A client that already has it from
        # GET /routes/baseline saves about 1 MB per request.
        original = []
    elif base.rows:
        original = base.rows
    else:
        original = build_edge_usage_rows(
            mirror,
            base.counts_group,
            total_routes,
            base.co2_per_km_group,
            betweenness=baseline_bc_group,
        )

    new = build_edge_usage_rows(
        mirror,
        counts_group,
        total_routes,
        co2_per_km,
        original_counts=base.counts_group,
        original_co2_per_km=base.co2_per_km_group,
        betweenness=baseline_bc_group,
        delta_betweenness=delta_bc_group,
    )
    return {"original": original, "new": new}


def _timing_stats(timing: dict) -> TimingStats:
    def ms(key):
        return round(timing[key], 1) if key in timing else None

    return TimingStats(
        cache_lookup_ms=ms("cache_lookup") or 0.0,
        apply_modifications_ms=ms("apply_modifications") or 0.0,
        od_resampling_ms=ms("od_resampling"),
        affected_routes_ms=ms("affected_routes"),
        delta_bc_ms=ms("delta_bc"),
        route_calculation_ms=ms("route_calculation") or 0.0,
        impact_stats_ms=ms("impact_stats") or 0.0,
        edge_usage_stats_ms=ms("edge_usage") or 0.0,
        total_ms=round(timing["total"], 1),
    )
