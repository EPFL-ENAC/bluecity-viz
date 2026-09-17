"""The scenario pipeline: what the tool counts, and what it says it applied.

All on the synthetic grid, so a closure can be chosen to affect almost every
trip, which is where the counting used to go wrong.
"""

import math

import numpy as np
import pytest

from app.models.route import EdgeModification, NodePair
from app.services import recalculate as pipeline
from app.services.modifications import build_scenario
from app.services.routing_engine import route_pairs


@pytest.fixture
def area(graph_service):
    graph_service.initialize_default_routes_sync(count=80, sampling_method="random", seed=1)
    return graph_service.default_area


def rows_by_street(rows):
    return {(r["u"], r["v"]): r for r in rows}


def total_count(rows):
    return sum(r["count"] for r in rows)


# ── Counting ──────────────────────────────────────────────────────────────────


def test_no_modification_leaves_every_count_where_it_was(area):
    result = area.recalculate_with_modifications(edge_modifications=[])

    before = rows_by_street(result["original_edge_usage"])
    after = rows_by_street(result["new_edge_usage"])
    assert before.keys() == after.keys()
    for key, row in after.items():
        assert row["count"] == before[key]["count"]
        assert row["delta_count"] == 0


def test_patching_the_counts_never_loses_the_trips_that_did_not_move(area):
    """The bug this pins.

    A targeted run counts the trips it rerouted and patches them onto the
    baseline counts. It used to switch to "just count the new routes" as soon
    as they were 90 % of the total, which silently dropped the traffic of the
    other 10 %: closing one street then made the whole city look emptier.

    Re-routing a subset on the *unchanged* network must give back exactly the
    baseline counts, whatever the size of the subset.
    """
    mirror = area.mirror
    base = pipeline._baseline_run(area, area.od["uniform"], None, None, "uniform")
    n = len(base.routes)

    for share in (0.1, 0.5, 0.95, 1.0):
        rerouted = np.arange(int(n * share), dtype=np.int64)
        same = route_pairs(mirror, base.pairs.subset(rerouted), mirror.travel_time)
        counts = pipeline.counts_after(
            mirror, base, pipeline.Assignment(routes=same, rerouted=rerouted, bc=None)
        )
        assert np.array_equal(counts, base.counts), f"{share:.0%} of the trips rerouted"


def test_closing_a_street_empties_it_and_fills_others(area):
    mirror = area.mirror
    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])
    mods = [EdgeModification(u=busiest["u"], v=busiest["v"], action="remove")]
    scenario = build_scenario(mirror, area.base_co2_g, mods)
    moved = area.baseline.routes.routes_using(scenario.changed)
    assert len(moved) > 0

    result = area.recalculate_with_modifications(edge_modifications=mods)
    after = rows_by_street(result["new_edge_usage"])

    assert after[(busiest["u"], busiest["v"])]["count"] == 0
    assert any(row["delta_count"] > 0 for row in result["new_edge_usage"]), "traffic went nowhere"


def test_the_trips_that_did_not_move_keep_exactly_their_old_routes(area):
    """What makes patching the counts legitimate."""
    mirror = area.mirror
    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])
    mods = [EdgeModification(u=busiest["u"], v=busiest["v"], action="remove")]
    scenario = build_scenario(mirror, area.base_co2_g, mods)

    moved = set(int(i) for i in area.baseline.routes.routes_using(scenario.changed))
    untouched = [i for i in range(len(area.baseline.routes)) if i not in moved]
    assert untouched

    for i in untouched[:20]:
        path = area.baseline.routes.edges[
            area.baseline.routes.offsets[i] : area.baseline.routes.offsets[i + 1]
        ]
        assert not np.isin(path, scenario.changed).any()


# ── What the scenario says it did ─────────────────────────────────────────────


def test_a_speed_limit_that_changes_nothing_is_not_applied(area):
    """Asking for 50 km/h on a street already at 50 is a no-op, and the
    response must not claim otherwise."""
    row = area.baseline.usage_rows[0]
    ids = area.mirror.edge_ids_for(row["u"], row["v"])
    current = float(area.mirror.speed_kph[ids][0])

    result = area.recalculate_with_modifications(
        edge_modifications=[
            EdgeModification(u=row["u"], v=row["v"], action="modify", speed_kph=current)
        ]
    )

    assert result["applied_modifications"] == []


def test_a_real_speed_limit_is_applied(area):
    row = area.baseline.usage_rows[0]

    result = area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=row["u"], v=row["v"], action="modify", speed_kph=10)]
    )

    assert len(result["applied_modifications"]) == 1


def test_a_street_the_graph_does_not_have_is_not_applied(area):
    result = area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=999_999, v=999_998, action="remove")]
    )

    assert result["applied_modifications"] == []


def test_a_scenario_never_touches_the_area(area):
    """Two requests run side by side, so nothing may be written to the mirror."""
    mirror = area.mirror
    before = mirror.travel_time.copy(), mirror.speed_kph.copy()
    row = area.baseline.usage_rows[0]

    area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=row["u"], v=row["v"], action="remove")]
    )

    assert np.array_equal(mirror.travel_time, before[0])
    assert np.array_equal(mirror.speed_kph, before[1])


# ── The three strategies ──────────────────────────────────────────────────────


@pytest.fixture
def closure(area):
    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])
    return [EdgeModification(u=busiest["u"], v=busiest["v"], action="remove")]


def test_the_equilibrium_model_runs_and_reroutes_every_trip(area, closure):
    result = area.recalculate_with_modifications(
        edge_modifications=closure, use_congestion=True, congestion_iterations=2
    )

    assert result["new_edge_usage"]
    assert result["impact_statistics"]["total_routes"] > 0


def test_elastic_demand_gives_the_same_answer_twice(area, closure):
    """It draws new destinations, so it needs a seed like everything else."""
    once = area.recalculate_with_modifications(
        edge_modifications=closure, resample_destinations=True
    )
    twice = area.recalculate_with_modifications(
        edge_modifications=closure, resample_destinations=True
    )

    assert once["new_edge_usage"] == twice["new_edge_usage"]
    assert once["impact_statistics"] == twice["impact_statistics"]


def test_the_congestion_sensitivity_changes_the_result(area, closure):
    """betweenness_to_slowdown used to be read from a fresh default config
    inside the formula, so setting it had no effect at all."""
    strong = area.sampling_config.model_copy(update={"betweenness_to_slowdown": 1.0})
    weak = area.sampling_config.model_copy(update={"betweenness_to_slowdown": 10_000_000.0})

    area.sampling_config = strong
    area.clear_route_cache()
    heavy = area.recalculate_with_modifications(edge_modifications=closure)

    area.sampling_config = weak
    area.clear_route_cache()
    light = area.recalculate_with_modifications(edge_modifications=closure)

    assert heavy["new_edge_usage"] != light["new_edge_usage"]


def test_a_closed_street_carries_nobody_even_when_it_was_the_only_way(area):
    """A trip that only had a route through the closed street has none now.

    igraph reads +inf as a very large cost, not as a missing edge, so without
    a check it hands back a path through the closed street and the street
    keeps its traffic.
    """
    # 1000 is a corner of the grid. Cut both streets that reach it, so the
    # nodes behind them can only be reached through a closed edge.
    mods = [
        EdgeModification(u=1000, v=1001, action="remove"),
        EdgeModification(u=1001, v=1000, action="remove"),
        EdgeModification(u=1000, v=1004, action="remove"),
        EdgeModification(u=1004, v=1000, action="remove"),
    ]
    pairs = [NodePair(origin=1000, destination=1010), NodePair(origin=1010, destination=1000)]
    out = pipeline.recalculate(area, pairs=pairs, edge_modifications=mods)

    rows = rows_by_street(out["new_edge_usage"])
    closed = {(1000, 1001), (1001, 1000), (1000, 1004), (1004, 1000)}
    for street in closed & rows.keys():
        assert rows[street]["count"] == 0, f"{street} still carries traffic"
    # Both trips start or end at the cut-off node, so both fail.
    assert out["impact_statistics"]["failed_routes"] == 2
    assert out["impact_statistics"]["affected_routes"] == 0
    # And the totals stay finite, or the impact panel shows nothing.
    for key, value in out["impact_statistics"].items():
        if isinstance(value, float):
            assert math.isfinite(value), f"{key} is {value}"
