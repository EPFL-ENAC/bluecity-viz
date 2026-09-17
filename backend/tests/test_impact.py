"""What "affected", "failed" and a change of sign mean in the impact table.

Built on hand-made route sets rather than a real graph, so each case is
exactly one situation: a trip that got longer, one that got shorter, one that
lost its route, one that did not move.
"""

import numpy as np
import pytest

from app.services.impact import compare_runs, elastic_impact
from app.services.recalculate import Assignment
from app.services.routing_engine import RouteSet


def route_set(distance, travel_time, co2, found=None) -> RouteSet:
    """A route set with the totals already filled, which is all impact reads."""
    n = len(distance)
    found = np.ones(n, dtype=bool) if found is None else np.asarray(found, dtype=bool)
    return RouteSet(
        origins=np.arange(n, dtype=np.int64),
        destinations=np.arange(n, dtype=np.int64) + 100,
        edges=np.empty(0, dtype=np.int32),
        offsets=np.zeros(n + 1, dtype=np.int64),
        found=found,
        travel_time=np.asarray(travel_time, dtype=np.float64),
        distance=np.asarray(distance, dtype=np.float64),
        co2=np.asarray(co2, dtype=np.float64),
    )


def compare(baseline, new, rerouted=None):
    return compare_runs(baseline, Assignment(routes=new, rerouted=rerouted, bc=None))


def test_a_longer_trip_is_affected_and_counted_positive():
    baseline = route_set([1000], [100], [200])
    new = route_set([1500], [150], [300])

    stats = compare(baseline, new)

    assert stats.affected_routes == 1
    assert stats.failed_routes == 0
    assert stats.total_distance_change_km == pytest.approx(0.5)
    assert stats.total_time_change_minutes == pytest.approx(50 / 60)
    assert stats.total_co2_change_grams == pytest.approx(100)
    assert stats.avg_distance_change_percent == pytest.approx(50.0)


def test_a_shorter_trip_is_affected_too_and_counted_negative():
    """Raising a speed limit makes trips faster, and the table must say so."""
    baseline = route_set([1000], [100], [200])
    new = route_set([1000], [80], [180])

    stats = compare(baseline, new)

    assert stats.affected_routes == 1
    assert stats.total_time_change_minutes == pytest.approx(-20 / 60)
    assert stats.total_co2_change_grams == pytest.approx(-20)
    assert stats.avg_time_change_percent == pytest.approx(-20.0)
    # nothing got worse, so there is no worst trip
    assert stats.max_time_increase_minutes == 0.0


def test_a_saving_and_a_detour_cancel_in_the_total_and_both_count_as_affected():
    baseline = route_set([1000, 1000], [100, 100], [200, 200])
    new = route_set([1400, 600], [140, 60], [280, 120])

    stats = compare(baseline, new)

    assert stats.affected_routes == 2
    assert stats.total_distance_change_km == pytest.approx(0.0)
    # the worst single trip is still reported
    assert stats.max_distance_increase_km == pytest.approx(0.4)


def test_a_trip_that_lost_its_route_is_failed_and_stays_out_of_the_totals():
    baseline = route_set([1000, 1000], [100, 100], [200, 200])
    new = route_set([0, 1200], [0, 120], [0, 240], found=[False, True])

    stats = compare(baseline, new)

    assert stats.failed_routes == 1
    assert stats.affected_routes == 1, "the failed trip is not also an affected one"
    assert stats.total_distance_change_km == pytest.approx(0.2)


def test_a_trip_that_did_not_move_is_not_affected():
    baseline = route_set([1000], [100], [200])
    new = route_set([1000], [100], [200])

    stats = compare(baseline, new)

    assert stats.affected_routes == 0
    assert stats.total_distance_change_km == 0.0
    assert stats.avg_distance_change_km == 0.0


def test_only_the_rerouted_trips_are_compared():
    """The others kept their route, so comparing them would be noise."""
    baseline = route_set([1000, 1000, 1000], [100, 100, 100], [200, 200, 200])
    new = route_set([1500], [150], [300])  # one route, for trip 2

    stats = compare(baseline, new, rerouted=np.array([2]))

    assert stats.total_routes == 3
    assert stats.affected_routes == 1
    assert stats.total_distance_change_km == pytest.approx(0.5)


def test_nothing_rerouted_means_no_impact():
    baseline = route_set([1000], [100], [200])
    new = route_set([], [], [])

    stats = compare(baseline, new, rerouted=np.empty(0, dtype=np.int64))

    assert stats.affected_routes == 0
    assert stats.failed_routes == 0
    assert stats.total_routes == 1


def test_elastic_demand_only_totals_because_the_trips_are_not_the_same_ones():
    baseline = route_set([1000, 2000], [100, 200], [200, 400])
    new = route_set([800, 900], [80, 90], [160, 180])

    stats = elastic_impact(baseline, new)

    assert stats.affected_routes == 0, "no trip can be paired with itself"
    assert stats.total_distance_change_km == pytest.approx((1700 - 3000) / 1000)
    assert stats.total_co2_change_grams == pytest.approx(-260)
