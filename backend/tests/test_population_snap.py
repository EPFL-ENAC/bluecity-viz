"""Residents and jobs from the federal hectares, snapped to the road nodes.

The hectares are given in Swiss LV95 metres and the nodes in lon/lat, so the
test places each hectare a few metres from a node of the synthetic graph and
checks the counts land on that node.
"""

import numpy as np
from pyproj import Transformer

from app.services.graph_mirror import GraphMirror
from app.services.graph_store_writer import population_columns, snap_hectares
from app.services.sampling.node_pool import POPULATION_SCORE_FLOOR, population_score


def lv95(x, y):
    to_lv95 = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
    return to_lv95.transform(np.asarray(x), np.asarray(y))


def nodes_of(graph):
    ids = np.array(list(graph.nodes), dtype=np.int64)
    x = np.array([graph.nodes[n]["x"] for n in ids])
    y = np.array([graph.nodes[n]["y"] for n in ids])
    return ids, x, y


def test_each_hectare_goes_to_its_nearest_node(synthetic_graph):
    ids, x, y = nodes_of(synthetic_graph)
    e, n = lv95(x, y)
    lonely = 7  # no hectare is near this node

    # one hectare 10 m east of every node but the lonely one
    others = np.array([i for i in range(len(ids)) if i != lonely])
    hect_e = e[others] + 10.0
    hect_n = n[others]
    residents = others + 1
    jobs = (others + 1) * 0.5

    # and a second hectare on node 0, 10 m north: the two add up
    hect_e = np.append(hect_e, e[0])
    hect_n = np.append(hect_n, n[0] + 10.0)
    residents = np.append(residents, 100)
    jobs = np.append(jobs, 40.0)

    snapped_res, snapped_jobs = snap_hectares(x, y, hect_e, hect_n, residents, jobs)

    assert snapped_res.dtype == np.int32 and snapped_jobs.dtype == np.float32
    assert snapped_res[lonely] == 0 and snapped_jobs[lonely] == 0
    assert snapped_res[0] == 1 + 100
    assert snapped_jobs[0] == np.float32(0.5 + 40.0)
    for i in others[1:]:
        assert snapped_res[i] == i + 1
        assert snapped_jobs[i] == np.float32((i + 1) * 0.5)
    assert snapped_res.sum() == residents.sum(), "no person is lost"


def test_a_node_with_no_hectare_still_gets_sampled(synthetic_graph):
    """The whole chain on a synthetic graph: snap, store columns, score."""
    graph = synthetic_graph.copy()
    ids, x, y = nodes_of(graph)
    e, n = lv95(x, y)
    lonely = 3

    others = np.array([i for i in range(len(ids)) if i != lonely])
    residents, jobs = snap_hectares(
        x, y, e[others], n[others], np.full(len(others), 3), np.full(len(others), 2.0)
    )
    for i, node in enumerate(ids):
        graph.nodes[int(node)]["residents"] = int(residents[i])
        graph.nodes[int(node)]["jobs_fte"] = float(jobs[i])

    mirror = GraphMirror(graph)
    score = population_score(mirror.residents, mirror.jobs_fte)

    assert score[lonely] == POPULATION_SCORE_FLOOR
    assert np.all(np.delete(score, lonely) > POPULATION_SCORE_FLOOR)


def test_no_hectare_at_all_gives_zeros(synthetic_graph):
    _ids, x, y = nodes_of(synthetic_graph)

    residents, jobs = snap_hectares(x, y, [], [], [], [])

    assert not residents.any() and not jobs.any()
    assert len(residents) == len(x)


def test_the_writer_fills_zeros_when_the_counts_are_missing():
    residents, jobs = population_columns({"node_id": np.arange(4)}, 4)

    assert residents.dtype == np.int32 and jobs.dtype == np.float32
    assert not residents.any() and not jobs.any()
