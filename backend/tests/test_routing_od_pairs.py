"""The OD pair count is a per-request choice, and the sets are nested.

N pairs are the first N of the set sampled at startup, so the baseline for N
must be exactly what routing those first N pairs gives.

The graph is the real one, but OD_PAIRS_MAX is lowered so the test stays fast.
"""

from pathlib import Path

import numpy as np
import pytest

from app.config import settings
from app.models.route import EdgeModification, RecalculateRequest
from app.services.graph_service import GraphService
from app.services.routing_engine import route_pairs

# Resolved from this file, so the suite runs from the repo root too.
GRAPH = Path(__file__).resolve().parents[1] / "data" / "lausanne.graphml"
MAX_PAIRS = 2000
DEFAULT_PAIRS = 600


@pytest.fixture(scope="module")
def service():
    """A service with a small OD sample, so the module runs in a few seconds."""
    old_max, old_default = settings.od_pairs_max, settings.od_pairs
    settings.od_pairs_max, settings.od_pairs = MAX_PAIRS, DEFAULT_PAIRS
    if not GRAPH.exists():
        pytest.skip(f"graph not found: {GRAPH}")
    svc = GraphService()
    svc.load_graph(str(GRAPH))
    svc.initialize_default_routes_sync(seed=42, sampling_method="research")
    yield svc
    settings.od_pairs_max, settings.od_pairs = old_max, old_default


def test_startup_samples_the_max(service):
    assert len(service.default_pairs) <= MAX_PAIRS
    assert len(service.default_pairs) > MAX_PAIRS * 0.9


def test_baseline_for_n_equals_routing_the_first_n_pairs(service):
    n = DEFAULT_PAIRS
    base = service.baseline_for(n)
    first_n = service.default_pairs.prefix(n)

    assert np.array_equal(base.pairs.origins, first_n.origins)
    assert np.array_equal(base.pairs.destinations, first_n.destinations)

    fresh = route_pairs(service.mirror, first_n, service.mirror.travel_time)
    assert np.array_equal(base.counts, fresh.edge_counts(service.mirror.n_edges))
    assert base.routes.n_found == fresh.n_found


def test_smaller_set_is_a_subset_not_a_different_sample(service):
    small = service.baseline_for(DEFAULT_PAIRS)
    full = service.baseline_for(MAX_PAIRS)

    assert len(small.pairs) < len(full.pairs)
    assert small.usage_rows != full.usage_rows
    # nested: every edge used by the small set is used by the full one, at
    # least as often
    assert np.all(full.counts >= small.counts)


def test_betweenness_does_not_depend_on_the_pair_count(service):
    """It is a property of the graph, which is why its cache key has no N."""
    small = service.baseline_for(DEFAULT_PAIRS)
    full = service.baseline_for(MAX_PAIRS)
    assert np.array_equal(small.bc, full.bc)


def test_recalculate_reports_the_count_it_used(service):
    rows = service.baseline.usage_rows
    mod = [EdgeModification(u=rows[0]["u"], v=rows[0]["v"], action="remove")]

    default_run = service.recalculate_with_modifications(edge_modifications=mod)
    assert default_run["od_pairs"] == DEFAULT_PAIRS

    asked = service.recalculate_with_modifications(edge_modifications=mod, od_pairs=300)
    assert asked["od_pairs"] == 300
    assert asked["impact_statistics"]["total_routes"] <= 300

    bigger = service.recalculate_with_modifications(edge_modifications=mod, od_pairs=MAX_PAIRS)
    assert bigger["od_pairs"] == len(service.default_pairs)
    assert bigger["impact_statistics"]["total_routes"] >= asked["impact_statistics"]["total_routes"]


def test_asking_for_more_pairs_than_sampled_is_refused():
    with pytest.raises(ValueError):
        RecalculateRequest(od_pairs=settings.od_pairs_max + 1)


def test_route_i_describes_pair_i(service):
    """Routes come back in the caller's order, whatever the origin grouping."""
    pairs = service.default_pairs.prefix(200)
    shuffled = pairs.subset(np.random.default_rng(0).permutation(len(pairs)))

    routes = route_pairs(service.mirror, shuffled, service.mirror.travel_time)

    assert np.array_equal(routes.origins, shuffled.origins)
    assert np.array_equal(routes.destinations, shuffled.destinations)
    for i in range(len(shuffled)):
        if routes.found[i]:
            path = routes.node_path(service.mirror, i)
            assert path[0] == shuffled.origins[i]
            assert path[-1] == shuffled.destinations[i]


def test_route_edges_are_int32(service):
    """Half the memory of a baseline route set, and 2 billion edges is plenty."""
    assert service.baseline.routes.edges.dtype == np.int32
