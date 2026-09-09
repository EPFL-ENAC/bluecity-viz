"""The mirror sampler must draw exactly the same OD pairs as the old one.

Every frequency, CO2 and betweenness number a user sees comes from this
sample, so porting it off NetworkX is only allowed if the pairs do not move.
Two guards: the two implementations are compared on the same graph, and the
Lausanne result is pinned to a hash so a change in both at once is caught.
"""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from app.services.graph_mirror import GraphMirror
from app.services.sampling.betweenness import (
    considered_nodes_from_mirror,
    get_considered_nodes,
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


def test_node_pool_needs_the_graph_for_a_real_weight_column(synthetic_graph):
    with pytest.raises(ValueError, match="node_weight_col"):
        considered_nodes_from_mirror(
            GraphMirror(synthetic_graph), np.random.RandomState(42), 100, "population"
        )


@pytest.mark.skipif(not GRAPH.exists(), reason=f"graph not found: {GRAPH}")
def test_same_pairs_on_lausanne():
    """The real graph, with its 71 parallel edges and its 3,752 candidate nodes."""
    import osmnx as ox

    graph = ox.load_graphml(str(GRAPH))
    pairs = assert_same_pairs(graph, LAUSANNE_PAIRS, SamplingConfig())
    assert pairs_digest(pairs) == LAUSANNE_GOLDEN
