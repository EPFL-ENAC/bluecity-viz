"""The CO2 of an edge is the CO2 of the traffic on it, per km.

One vehicle over the edge, times the number of routes on it, divided by the
length. Times the length and summed over all the edges it must give the CO2 of
all the routes, before and after a change, because both come from the same
grams per edge.
"""

import numpy as np
import pytest

from app.models.route import EdgeModification
from app.services.co2_calculator import CO2Calculator

# Rows are rounded to 0.1 g/km, so a row can be off by 0.05 g/km.
ROUND = 0.05


def km(mirror, row):
    ids = mirror.edge_ids_for(row["u"], row["v"])
    assert len(ids) == 1  # the grid has no parallel edges
    return mirror.length[ids][0] / 1000.0


def grams(mirror, rows, key="co2_g_per_km"):
    """Back from g/km to grams, summed over the rows."""
    return sum(r.get(key, 0.0) * km(mirror, r) for r in rows)


def tolerance(mirror, rows):
    return ROUND * sum(km(mirror, r) for r in rows)


@pytest.fixture
def area(graph_service):
    graph_service.initialize_default_routes_sync(count=60, sampling_method="random", seed=1)
    return graph_service.default_area


def test_baseline_edges_add_up_to_the_routes(area):
    rows = area.baseline.usage_rows

    assert rows
    assert grams(area.mirror, rows) == pytest.approx(
        area.baseline.routes.co2.sum(), abs=tolerance(area.mirror, rows)
    )


def test_edge_co2_is_one_vehicle_times_the_count_per_km(area):
    mirror = area.mirror
    for row in area.baseline.usage_rows:
        ids = mirror.edge_ids_for(row["u"], row["v"])
        per_vehicle = area.base_co2_g[ids][0]
        count = area.baseline.counts[ids][0]
        assert row["co2_g_per_km"] == pytest.approx(
            per_vehicle * count / km(mirror, row), abs=ROUND
        )


def test_closing_a_street_moves_the_co2_and_the_totals_still_match(area, monkeypatch):
    from app.services import recalculate as pipeline

    mirror = area.mirror
    captured = {}
    targeted = pipeline._assign_targeted

    def spy(*args, **kwargs):
        assignment = targeted(*args, **kwargs)
        captured["assignment"] = assignment
        return assignment

    monkeypatch.setattr(pipeline, "_assign_targeted", spy)

    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])
    result = area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=busiest["u"], v=busiest["v"], action="remove")]
    )
    new, original = result["new_edge_usage"], result["original_edge_usage"]
    tol = tolerance(mirror, new) + tolerance(mirror, original)

    # the routes after the change: the untouched ones, plus the rerouted ones
    routes = area.baseline.routes
    assignment = captured["assignment"]
    affected = assignment.rerouted
    assert len(affected) > 0
    expected = routes.co2.sum() - routes.co2[affected].sum() + assignment.routes.co2.sum()
    assert grams(mirror, new) == pytest.approx(expected, abs=tol)

    # the deltas add up to the real change, the closed street included
    delta = grams(mirror, new, "delta_co2_g_per_km")
    assert delta == pytest.approx(grams(mirror, new) - grams(mirror, original), abs=tol)
    closed = next(r for r in new if (r["u"], r["v"]) == (busiest["u"], busiest["v"]))
    assert closed["count"] == 0
    assert closed["co2_g_per_km"] == 0
    assert closed["delta_co2_g_per_km"] == pytest.approx(-busiest["co2_g_per_km"], abs=ROUND)

    # the traffic went somewhere: other streets gained CO2
    gained = [
        r
        for r in new
        if r["delta_co2_g_per_km"] > 0 and (r["u"], r["v"]) != (busiest["u"], busiest["v"])
    ]
    assert gained


def test_a_speed_limit_changes_the_co2_of_its_own_edge(area):
    mirror = area.mirror
    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])
    u, v = busiest["u"], busiest["v"]
    ids = mirror.edge_ids_for(u, v)

    result = area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=u, v=v, action="modify", speed_kph=20)]
    )
    row = next(r for r in result["new_edge_usage"] if (r["u"], r["v"]) == (u, v))

    slow = CO2Calculator.edge_co2_array(mirror.length[ids], np.full(1, 20.0), mirror.elev_gain[ids])
    # one vehicle emits more at 20 km/h than at 50 km/h, and the row uses the new grams
    assert slow[0] > area.base_co2_g[ids][0]
    assert row["co2_g_per_km"] == pytest.approx(row["count"] * slow[0] / km(mirror, row), abs=ROUND)
