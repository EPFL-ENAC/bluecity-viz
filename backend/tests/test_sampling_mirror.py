"""What the OD sampler promises.

Every frequency, CO2 and betweenness number a user sees comes from the sample
this module draws, so the properties it relies on are pinned here: the draw is
reproducible, a prefix of N pairs is a valid smaller sample, and the origins
and destinations come from the junction pool.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.graph_mirror import GraphMirror
from app.services.sampling.config import SamplingConfig
from app.services.sampling.node_pool import (
    POPULATION_SCORE_FLOOR,
    RESIDENT_SHARE,
    junction_pool,
    population_score,
)
from app.services.sampling.od_sampler import generate_research_based_pairs_mirror

GRAPH = Path(__file__).resolve().parents[1] / "data" / "lausanne.graphml"

# Sampled from data/lausanne.graphml at seed 42, n_pairs=3000, default config.
# Last moved when the sampler and the map were put on one betweenness and one
# speed (see docs/routing-model.md): a different draw of the same distribution.
# It changes only when the model changes, which is a decision, never a
# side effect: regenerate it in the same commit and say why.
LAUSANNE_GOLDEN = "69669c2b882be0f4f7e38b4c4486ca6c"
LAUSANNE_PAIRS = 3000


def pairs_digest(pairs) -> str:
    d = hashlib.blake2b(digest_size=16)
    d.update(np.ascontiguousarray(pairs.origins).tobytes())
    d.update(np.ascontiguousarray(pairs.destinations).tobytes())
    return d.hexdigest()


# ── The draw ──────────────────────────────────────────────────────────────────


@pytest.fixture
def config():
    return SamplingConfig(n_nodes_preprocess=100, n_destinations_per_origin=5)


def test_the_same_seed_draws_the_same_pairs(synthetic_graph, config):
    mirror = GraphMirror(synthetic_graph)
    once = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=42).pairs
    twice = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=42).pairs

    assert pairs_digest(once) == pairs_digest(twice)
    # at most what we asked: an origin with no reachable destination is dropped
    assert 0 < len(once) <= 40


def test_another_seed_draws_other_pairs(synthetic_graph, config):
    mirror = GraphMirror(synthetic_graph)
    once = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=42).pairs
    other = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=7).pairs

    assert pairs_digest(once) != pairs_digest(other)


def test_a_prefix_of_the_sample_spreads_over_several_origins(synthetic_graph, config):
    """What makes "the first N pairs" a usable smaller sample.

    A request asks for N pairs and gets the first N of the startup set
    (`PairArrays.prefix`), so the origin draws must be in random order: a
    prefix that held a single origin would be a sample of one neighbourhood.
    """
    mirror = GraphMirror(synthetic_graph)
    pairs = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=42).pairs

    prefix = pairs.prefix(len(pairs) // 2)
    assert prefix.n_origins > 1
    assert np.array_equal(prefix.origins, pairs.origins[: len(prefix)])


def test_the_pairs_come_from_the_junction_pool(synthetic_graph, config):
    mirror = GraphMirror(synthetic_graph)
    sample = generate_research_based_pairs_mirror(mirror, n_pairs=40, config=config, seed=42)
    pairs = sample.pairs

    pool = set(int(n) for n in sample.nodes.index)
    assert set(int(o) for o in pairs.origins) <= pool
    assert set(int(d) for d in pairs.destinations) <= pool


def test_asking_for_no_pair_is_an_error(synthetic_graph, config):
    with pytest.raises(ValueError, match="n_pairs"):
        generate_research_based_pairs_mirror(
            GraphMirror(synthetic_graph), n_pairs=0, config=config, seed=42
        )


# ── The junction pool ─────────────────────────────────────────────────────────


def test_the_pool_keeps_junctions_only(synthetic_graph):
    mirror = GraphMirror(synthetic_graph)
    pool = junction_pool(mirror, np.random.RandomState(42), 100, "dummy")

    keep = mirror.street_count >= 3
    assert list(pool.index) == list(mirror.node_ids[keep])
    assert list(pool.columns) == ["origin", "destination"]
    assert set(pool.values.ravel()) == {1}


def test_node_pool_refuses_a_column_the_mirror_does_not_have(synthetic_graph):
    with pytest.raises(ValueError, match="node_weight_col"):
        junction_pool(GraphMirror(synthetic_graph), np.random.RandomState(42), 100, "elevation")


# ── Population weight ─────────────────────────────────────────────────────────


def test_the_score_is_the_mean_of_the_two_percentiles():
    # 20 nodes, counts 1..20: the node with 15 residents is at the 75th
    # percentile, the node with 17 jobs at the 85th.
    residents = np.arange(1, 21)
    jobs = np.arange(1, 21)
    jobs[[14, 16]] = jobs[[16, 14]]  # node 14 now has 17 jobs

    score = population_score(residents, jobs)

    assert score[14] == pytest.approx(80.0)
    assert score.max() == pytest.approx(100.0)
    assert np.all((score >= POPULATION_SCORE_FLOOR) & (score <= 100.0))


def test_a_node_with_nobody_keeps_the_floor():
    residents = np.array([0, 10, 0, 50])
    jobs = np.array([0, 0, 5, 20])

    score = population_score(residents, jobs)

    assert score[0] == POPULATION_SCORE_FLOOR, "no resident, no job: floor, not out of the draw"
    # a zero ranks 0, it does not share the average rank of all the zeros
    assert score[1] == pytest.approx(100 * (0.75 + 0) / 2)
    assert score[3] == pytest.approx(100.0)


def test_the_resident_share_moves_the_score_from_jobs_to_residents():
    residents = np.array([0, 10, 0, 50])
    jobs = np.array([0, 0, 5, 20])

    homes = population_score(residents, jobs, resident_share=1.0)
    work = population_score(residents, jobs, resident_share=0.0)

    # the residents rank alone, then the jobs rank alone
    assert homes == pytest.approx([POPULATION_SCORE_FLOOR, 75.0, POPULATION_SCORE_FLOOR, 100.0])
    assert work == pytest.approx([POPULATION_SCORE_FLOOR, POPULATION_SCORE_FLOOR, 75.0, 100.0])
    # the daily average is the mean of the two ranks, and it is the default
    assert population_score(residents, jobs) == pytest.approx(
        [POPULATION_SCORE_FLOOR, 37.5, 37.5, 100.0]
    )


def test_the_population_pool_carries_the_score(synthetic_graph):
    graph = synthetic_graph.copy()
    for i, node in enumerate(graph.nodes):
        graph.nodes[node]["residents"] = i * 10
        graph.nodes[node]["jobs_fte"] = 0.0 if i % 2 else float(i)
    mirror = GraphMirror(graph)

    pool = junction_pool(mirror, np.random.RandomState(42), 100, "population")

    keep = mirror.street_count >= 3
    assert list(pool.index) == list(mirror.node_ids[keep])
    score = population_score(mirror.residents[keep], mirror.jobs_fte[keep])
    # the daily average weighs both ends the same
    assert np.allclose(pool["origin"], score)
    assert np.allclose(pool["destination"], score)
    assert mirror.has_population


def homes_and_offices(synthetic_graph) -> GraphMirror:
    """Residents on the even nodes, jobs on the odd ones, nobody does both."""
    graph = synthetic_graph.copy()
    for i, node in enumerate(graph.nodes):
        graph.nodes[node]["residents"] = 0 if i % 2 else 10 * (i + 1)
        graph.nodes[node]["jobs_fte"] = float(10 * (i + 1)) if i % 2 else 0.0
    return GraphMirror(graph)


def test_the_weekday_pools_put_residents_and_jobs_at_opposite_ends(synthetic_graph):
    mirror = homes_and_offices(synthetic_graph)
    keep = mirror.street_count >= 3
    residents, jobs = mirror.residents[keep], mirror.jobs_fte[keep]

    morning = junction_pool(mirror, np.random.RandomState(42), 100, "weekday_morning")
    evening = junction_pool(mirror, np.random.RandomState(42), 100, "weekday_evening")

    assert RESIDENT_SHARE["weekday_morning"] == (1.0, 0.0)
    # morning: from home to work
    assert np.allclose(morning["origin"], population_score(residents, jobs, 1.0))
    assert np.allclose(morning["destination"], population_score(residents, jobs, 0.0))
    # evening: the way back
    assert np.allclose(evening["origin"], morning["destination"])
    assert np.allclose(evening["destination"], morning["origin"])
    # the same junctions: the pool draw does not look at the weights
    assert list(morning.index) == list(evening.index)


def test_a_morning_sample_goes_from_homes_to_offices(synthetic_graph):
    mirror = homes_and_offices(synthetic_graph)
    config = SamplingConfig(n_nodes_preprocess=100, n_destinations_per_origin=5)
    homes = set(int(n) for n in mirror.node_ids[mirror.residents > 0])

    def share_at_home(nodes):
        return np.mean([int(n) in homes for n in nodes])

    morning = generate_research_based_pairs_mirror(
        mirror, n_pairs=400, config=config.model_copy(update={"node_weight_col": "weekday_morning"})
    ).pairs
    evening = generate_research_based_pairs_mirror(
        mirror, n_pairs=400, config=config.model_copy(update={"node_weight_col": "weekday_evening"})
    ).pairs

    # a node with nobody keeps the floor of 1 against up to 100, so it is rare
    assert share_at_home(morning.origins) > 0.9
    assert share_at_home(morning.destinations) < 0.1
    assert share_at_home(evening.origins) < 0.1
    assert share_at_home(evening.destinations) > 0.9


def test_a_skewed_population_still_draws_a_small_pool(synthetic_graph):
    """One node holds almost everybody: the pool draw must not refuse it.

    The pool is drawn uniformly, the score only weighs the OD draws later.
    """
    graph = synthetic_graph.copy()
    for i, node in enumerate(graph.nodes):
        graph.nodes[node]["residents"] = 10_000 if i == 0 else 0
        graph.nodes[node]["jobs_fte"] = 0.0
    mirror = GraphMirror(graph)
    score = pd.Series(population_score(mirror.residents, mirror.jobs_fte), index=mirror.node_ids)

    pool = junction_pool(mirror, np.random.RandomState(42), 5, "population")

    assert len(pool) == 5
    assert np.allclose(pool["origin"], score[pool.index].values)


def test_a_graph_without_population_says_so(synthetic_graph):
    assert not GraphMirror(synthetic_graph).has_population


# ── The real graph ────────────────────────────────────────────────────────────


@pytest.mark.skipif(not GRAPH.exists(), reason=f"graph not found: {GRAPH}")
def test_the_lausanne_sample_does_not_move():
    """The graph with its 71 parallel edges and its 3,752 candidate nodes."""
    import osmnx as ox

    mirror = GraphMirror(ox.load_graphml(str(GRAPH)))
    pairs = generate_research_based_pairs_mirror(
        mirror, n_pairs=LAUSANNE_PAIRS, config=SamplingConfig(), seed=42
    ).pairs

    assert len(pairs) == LAUSANNE_PAIRS
    assert pairs_digest(pairs) == LAUSANNE_GOLDEN
