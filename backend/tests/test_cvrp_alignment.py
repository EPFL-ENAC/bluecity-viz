"""Regression: the solver matrix must match the solver locations.

The old code built the matrix from list(set(node_ig)), whose order is arbitrary,
then indexed it positionally against [depot] + clients. These tests fail on that
code and pass on the aligned one.
"""

import networkx as nx
import pandas as pd
import pytest
from shapely.geometry import LineString

from app.services.cvrp_service import (
    UNREACHABLE_DISTANCE,
    _build_problem_data,
    _create_distance_matrix,
    _ordered_locations,
    _solve_cvrp,
)
from app.services.sampling.igraph_utils import networkx_to_igraph_with_indices

# Five nodes in a directed ring with very different lengths, so any wrong
# pairing of rows and locations shows up as a wrong number.
RING_LENGTHS = {
    (0, 1): 100.0,
    (1, 2): 250.0,
    (2, 3): 400.0,
    (3, 4): 650.0,
    (4, 0): 900.0,
}


@pytest.fixture
def ring():
    """(graph, idx_maps, node_df) — node_df rows are not in igraph id order."""
    g = nx.MultiDiGraph()
    g.graph["crs"] = "EPSG:4326"
    for i in range(5):
        g.add_node(10 + i, x=6.59 + i * 0.001, y=46.52 + i * 0.001)
    for (u, v), length in RING_LENGTHS.items():
        a, b = 10 + u, 10 + v
        g.add_edge(
            a,
            b,
            0,
            length=length,
            speed_kph=50.0,
            travel_time=length / (50.0 / 3.6),
            geometry=LineString(
                [(g.nodes[a]["x"], g.nodes[a]["y"]), (g.nodes[b]["x"], g.nodes[b]["y"])]
            ),
        )

    _, idx_maps = networkx_to_igraph_with_indices(g)
    # Depot is node 10; clients come in a deliberately shuffled order.
    order = [10, 13, 11, 14, 12]
    node_df = pd.DataFrame(
        {
            "node": order,
            "centroid_waste": [0, 3, 1, 4, 2],
            "x": [g.nodes[n]["x"] for n in order],
            "y": [g.nodes[n]["y"] for n in order],
            "node_ig": [idx_maps["node_nx_to_ig"][n] for n in order],
            "isdepot": [True, False, False, False, False],
        }
    )
    return g, idx_maps, node_df


def test_matrix_matches_the_graph_for_every_pair(ring):
    """distance(i, j) in the model == road distance between location i and j."""
    g, _, node_df = ring
    g_ig, _ = networkx_to_igraph_with_indices(g)

    ordered_ig = _ordered_locations(node_df)
    od, inaccessible = _create_distance_matrix(g_ig, ordered_ig)
    data = _build_problem_data(node_df, od, inaccessible)

    expected = g_ig.distances(ordered_ig, ordered_ig, weights="length")
    matrix = data.distance_matrix(0)

    for i in range(len(ordered_ig)):
        for j in range(len(ordered_ig)):
            assert matrix[i][j] == round(expected[i][j]), f"mismatch at ({i}, {j})"


def test_locations_follow_the_node_df_order(ring):
    """Location k + 1 is the k-th client row, coordinates included."""
    _, _, node_df = ring
    g_ig, _ = networkx_to_igraph_with_indices(_ring_graph(node_df))
    ordered_ig = _ordered_locations(node_df)
    od, inaccessible = _create_distance_matrix(g_ig, ordered_ig)
    data = _build_problem_data(node_df, od, inaccessible)

    clients = node_df.loc[~node_df["isdepot"]]
    assert len(data.clients()) == len(clients)
    for client, (_, row) in zip(data.clients(), clients.iterrows()):
        assert client.x == pytest.approx(row["x"])
        assert client.y == pytest.approx(row["y"])
        assert client.delivery[0] == row["centroid_waste"]


def _ring_graph(node_df):
    """Rebuild the ring graph, used where the fixture graph is not handy."""
    g = nx.MultiDiGraph()
    g.graph["crs"] = "EPSG:4326"
    for i in range(5):
        g.add_node(10 + i, x=6.59 + i * 0.001, y=46.52 + i * 0.001)
    for (u, v), length in RING_LENGTHS.items():
        g.add_edge(10 + u, 10 + v, 0, length=length, speed_kph=50.0)
    return g


def test_unreachable_client_is_optional(synthetic_graph):
    """A client that cannot get back to the depot is marked not required."""
    g_ig, idx_maps = networkx_to_igraph_with_indices(synthetic_graph)
    nodes = [1000, 1019, 1005]  # 1019 is the one-way trap
    node_df = pd.DataFrame(
        {
            "node": nodes,
            "centroid_waste": [0, 5, 5],
            "x": [synthetic_graph.nodes[n]["x"] for n in nodes],
            "y": [synthetic_graph.nodes[n]["y"] for n in nodes],
            "node_ig": [idx_maps["node_nx_to_ig"][n] for n in nodes],
            "isdepot": [True, False, False],
        }
    )

    ordered_ig = _ordered_locations(node_df)
    od, inaccessible = _create_distance_matrix(g_ig, ordered_ig)

    assert inaccessible == {1}  # position of node 1019
    assert od[1][0] == UNREACHABLE_DISTANCE

    data = _build_problem_data(node_df, od, inaccessible)
    assert data.clients()[0].required is False
    assert data.clients()[1].required is True


def test_seeded_solve_is_deterministic(ring):
    g, _, node_df = ring
    g_ig, _ = networkx_to_igraph_with_indices(g)
    ordered_ig = _ordered_locations(node_df)
    od, inaccessible = _create_distance_matrix(g_ig, ordered_ig)
    data = _build_problem_data(node_df, od, inaccessible, n_vehicles=2, vehicle_capacity=100)

    first = _solve_cvrp(data, max_runtime=1, seed=42)
    second = _solve_cvrp(data, max_runtime=1, seed=42)

    assert first.best.distance() == second.best.distance()
    assert [r.visits() for r in first.best.routes()] == [r.visits() for r in second.best.routes()]
