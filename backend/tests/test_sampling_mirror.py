"""The mirror sampler must draw exactly the same OD pairs as the old one.

Every frequency, CO2 and betweenness number a user sees comes from this
sample, so porting it off NetworkX is only allowed if the pairs do not move.
Two guards: the two implementations are compared on the same graph, and the
Lausanne result is pinned to a hash so a change in both at once is caught.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.graph_mirror import GraphMirror
from app.services.sampling.betweenness import (
    POPULATION_SCORE_FLOOR,
    considered_nodes_from_mirror,
    get_considered_nodes,
    population_score,
)
from app.services.sampling.config import SamplingConfig
from app.services.sampling.od_sampler import (
    generate_research_based_pairs,
    generate_research_based_pairs_mirror,
)

GRAPH = Path(__file__).resolve().parents[1] / "data" / "lausanne.graphml"

# Sampled from data/lausanne.graphml at seed 42, n_pairs=3000, default config.
LAUSANNE_GOLDEN = "d2b4abaf6afc74fdf6fadd891e9003bb"
LAUSANNE_PAIRS = 3000


def pairs_digest(pairs) -> str:
    d = hashlib.blake2b(digest_size=16)
    d.update(np.ascontiguousarray(pairs.origins).tobytes())
    d.update(np.ascontiguousarray(pairs.destinations).tobytes())
    return d.hexdigest()


def assert_same_pairs(graph, n_pairs, config):
    """The NetworkX pipeline and the mirror pipeline, pair by pair."""
    # generate_research_based_pairs writes weight attributes on the graph it
    # gets, so each side works on its own copy.
    old = generate_research_based_pairs(graph.copy(), n_pairs=n_pairs, config=config, seed=42)
    new = generate_research_based_pairs_mirror(
        GraphMirror(graph.copy()), n_pairs=n_pairs, config=config, seed=42
    )

    assert len(new) == len(old)
    assert np.array_equal(new.origins, [p.origin for p in old])
    assert np.array_equal(new.destinations, [p.destination for p in old])
    return new


def test_same_pairs_on_the_synthetic_graph(synthetic_graph):
    config = SamplingConfig(n_nodes_preprocess=100, n_destinations_per_origin=5)
    pairs = assert_same_pairs(synthetic_graph, 40, config)
    assert len(pairs) > 0


def test_same_node_pool_on_the_synthetic_graph(synthetic_graph):
    config = SamplingConfig(n_nodes_preprocess=100)
    old = get_considered_nodes(
        synthetic_graph.copy(), np.random.RandomState(42), 100, config.node_weight_col
    )
    new = considered_nodes_from_mirror(
        GraphMirror(synthetic_graph.copy()), np.random.RandomState(42), 100, config.node_weight_col
    )
    assert list(new.index) == list(old.index)
    assert list(new.values) == list(old.values)


def test_node_pool_refuses_a_column_the_mirror_does_not_have(synthetic_graph):
    with pytest.raises(ValueError, match="node_weight_col"):
        considered_nodes_from_mirror(
            GraphMirror(synthetic_graph), np.random.RandomState(42), 100, "elevation"
        )


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


def test_the_population_pool_carries_the_score(synthetic_graph):
    graph = synthetic_graph.copy()
    for i, node in enumerate(graph.nodes):
        graph.nodes[node]["residents"] = i * 10
        graph.nodes[node]["jobs_fte"] = 0.0 if i % 2 else float(i)
    mirror = GraphMirror(graph)

    pool = considered_nodes_from_mirror(mirror, np.random.RandomState(42), 100, "population")

    keep = mirror.street_count >= 3
    assert list(pool.index) == list(mirror.node_ids[keep])
    assert np.allclose(pool.values, population_score(mirror.residents[keep], mirror.jobs_fte[keep]))
    assert mirror.has_population


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

    pool = considered_nodes_from_mirror(mirror, np.random.RandomState(42), 5, "population")

    assert len(pool) == 5
    assert np.allclose(pool.values, score[pool.index].values)


def test_a_graph_without_population_says_so(synthetic_graph):
    assert not GraphMirror(synthetic_graph).has_population


@pytest.mark.skipif(not GRAPH.exists(), reason=f"graph not found: {GRAPH}")
def test_same_pairs_on_lausanne():
    """The real graph, with its 71 parallel edges and its 3,752 candidate nodes."""
    import osmnx as ox

    graph = ox.load_graphml(str(GRAPH))
    pairs = assert_same_pairs(graph, LAUSANNE_PAIRS, SamplingConfig())
    assert pairs_digest(pairs) == LAUSANNE_GOLDEN
