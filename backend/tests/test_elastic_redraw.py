"""What the elastic redraw promises.

Elastic demand draws the destinations again on the modified network. The
redraw is paired with the startup draw (see `resample_od_destinations`), and
the comparison Model against Scenario rests on what that pairing gives: on the
untouched network nobody moves, and a trip moves only when the scenario
changed something for it.
"""

import numpy as np
import pytest

from app.services.graph_mirror import GraphMirror
from app.services.routing_engine import PairArrays
from app.services.sampling.config import SamplingConfig
from app.services.sampling.od_sampler import (
    destination_probabilities,
    generate_research_based_pairs_mirror,
    resample_od_destinations,
)

SEED = 42


@pytest.fixture
def config():
    return SamplingConfig(n_nodes_preprocess=100, n_destinations_per_origin=20)


@pytest.fixture
def mirror(synthetic_graph):
    return GraphMirror(synthetic_graph)


@pytest.fixture
def sample(mirror, config):
    return generate_research_based_pairs_mirror(mirror, n_pairs=200, config=config, seed=SEED)


def closed(mirror, base, *streets):
    """The times of `base` with these streets closed both ways."""
    times = base.copy()
    for u, v in streets:
        times[mirror.edge_ids_for(u, v)] = np.inf
        times[mirror.edge_ids_for(v, u)] = np.inf
    return times


def redraw(sample, mirror, config, times, pairs=None):
    return resample_od_destinations(
        pairs if pairs is not None else sample.pairs,
        sample.nodes,
        mirror,
        sample.congested_time,
        times,
        config,
        SEED,
    )


def test_on_the_untouched_network_nobody_moves(sample, mirror, config):
    """The redraw on the untouched network is the startup draw itself."""
    same = redraw(sample, mirror, config, sample.congested_time.copy())

    assert len(same.moved) == 0
    np.testing.assert_array_equal(same.pairs.origins, sample.pairs.origins)
    np.testing.assert_array_equal(same.pairs.destinations, sample.pairs.destinations)


def test_a_closure_moves_some_trips_and_keeps_the_origins(sample, mirror, config):
    times = closed(mirror, sample.congested_time, (1005, 1006), (1009, 1010))
    after = redraw(sample, mirror, config, times)

    assert 0 < len(after.moved) < len(sample.pairs)
    np.testing.assert_array_equal(after.pairs.origins, sample.pairs.origins)
    moved = np.zeros(len(sample.pairs), dtype=bool)
    moved[after.moved] = True
    assert np.array_equal(moved, after.pairs.destinations != sample.pairs.destinations)


def test_an_origin_whose_times_did_not_change_keeps_every_destination(sample, mirror, config):
    # On this grid, closing 1012-1013 leaves four of the seven origins alone.
    times = closed(mirror, sample.congested_time, (1012, 1013))
    after = redraw(sample, mirror, config, times)

    nodes = list(sample.nodes.index)
    targets = [mirror.node_index[int(n)] for n in nodes]
    unchanged = set()
    for origin in np.unique(sample.pairs.origins):
        source = mirror.node_index[int(origin)]
        before_row = mirror.h.distances(source, targets, weights=sample.congested_time)
        after_row = mirror.h.distances(source, targets, weights=times)
        if before_row == after_row:
            unchanged.add(int(origin))

    assert unchanged, "pick a closure that leaves some origin alone"
    assert len(after.moved) > 0, "pick a closure that moves some trip"
    for i, origin in enumerate(sample.pairs.origins):
        if int(origin) in unchanged:
            assert after.pairs.destinations[i] == sample.pairs.destinations[i]


def test_a_destination_out_of_reach_always_moves(sample, mirror, config):
    """Close every street around one junction: no trip can still end there."""
    target = 1005
    times = closed(
        mirror, sample.congested_time, (1005, 1001), (1005, 1004), (1005, 1006), (1005, 1009)
    )
    after = redraw(sample, mirror, config, times)

    going_there = (sample.pairs.destinations == target) & (sample.pairs.origins != target)
    assert going_there.any(), "pick a junction some trip goes to"
    assert not np.any(after.pairs.destinations[going_there] == target)


def test_a_prefix_redraws_like_the_full_sample(sample, mirror, config):
    """The trip counts are nested, so their redraws must be too."""
    times = closed(mirror, sample.congested_time, (1005, 1006))
    full = redraw(sample, mirror, config, times)
    head = redraw(sample, mirror, config, times, pairs=sample.pairs.subset(np.arange(120)))

    np.testing.assert_array_equal(head.pairs.destinations, full.pairs.destinations[:120])


def test_the_same_request_gives_the_same_answer(sample, mirror, config):
    times = closed(mirror, sample.congested_time, (1005, 1006))
    once = redraw(sample, mirror, config, times)
    twice = redraw(sample, mirror, config, times)

    np.testing.assert_array_equal(once.pairs.destinations, twice.pairs.destinations)


def test_the_new_destinations_follow_the_scenario_times(sample, mirror, config):
    """Pairing changes which trips move, not the distribution they end up in.

    One origin, many trips drawn on the startup times, then redrawn on the
    scenario times: the share of each destination must be the scenario one.
    """
    origin = 1000
    nodes = sample.nodes
    candidates = np.asarray(nodes.index, dtype=np.int64)
    weights = nodes.values.astype(float)
    targets = [mirror.node_index[int(n)] for n in candidates]
    source = mirror.node_index[origin]
    times = closed(mirror, sample.congested_time, (1004, 1005), (1001, 1005))

    def probabilities(edge_times):
        row = np.asarray([mirror.h.distances(source, targets, weights=edge_times)[0]])
        return destination_probabilities(row, weights, config)[0]

    before, after = probabilities(sample.congested_time), probabilities(times)
    assert not np.allclose(before, after), "the closure must change this origin's draw"

    n = 40_000
    rng = np.random.default_rng(7)
    start = candidates[rng.choice(len(candidates), size=n, p=before)]
    pairs = PairArrays(origins=np.full(n, origin, dtype=np.int64), destinations=start)

    out = redraw(sample, mirror, config, times, pairs=pairs)
    share = np.array([(out.pairs.destinations == c).mean() for c in candidates])

    assert np.abs(share - after).max() < 0.01
