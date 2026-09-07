"""Shared fixtures: a small synthetic road network, no lausanne.graphml needed."""

import networkx as nx
import osmnx as ox
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from app.services.cvrp_service import DEPOT_LAT, DEPOT_LON, CVRPService
from app.services.graph_service import GraphService
from app.services.sampling.igraph_utils import networkx_to_igraph_with_indices

# Grid size: 4 columns x 5 rows = 20 nodes.
GRID_COLS = 4
GRID_ROWS = 5
# ~110 m per step. The grid is placed so that the CVRP depot (city centre, see
# cvrp_service.DEPOT_LON / DEPOT_LAT) snaps onto node 1009, in the middle of the
# grid and in the middle of the client rows.
STEP = 0.001
BASE_LON = DEPOT_LON - 1 * STEP
BASE_LAT = DEPOT_LAT - 2 * STEP
DEPOT_NODE = 1009


def _node_id(col: int, row: int) -> int:
    return 1000 + row * GRID_COLS + col


def _add_street(g: nx.MultiDiGraph, u: int, v: int, both_ways: bool = True) -> None:
    """Add an edge with the attributes osmnx and the services expect."""
    for a, b in ((u, v), (v, u)) if both_ways else ((u, v),):
        x1, y1 = g.nodes[a]["x"], g.nodes[a]["y"]
        x2, y2 = g.nodes[b]["x"], g.nodes[b]["y"]
        length = float(ox.distance.great_circle(y1, x1, y2, x2))
        speed_kph = 50.0
        g.add_edge(
            a,
            b,
            0,
            osmid=a * 100000 + b,
            length=length,
            speed_kph=speed_kph,
            travel_time=length / (speed_kph / 3.6),
            highway="residential",
            oneway=not both_ways,
            geometry=LineString([(x1, y1), (x2, y2)]),
        )


def build_synthetic_graph() -> nx.MultiDiGraph:
    """A 4x5 grid of two-way streets, with one node only reachable one way.

    Node 1019 (top right corner) can be entered but not left, so anything that
    routes back to the depot has to treat it as inaccessible.
    """
    g = nx.MultiDiGraph()
    g.graph["crs"] = "EPSG:4326"
    g.graph["simplified"] = True

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            g.add_node(
                _node_id(col, row),
                x=BASE_LON + col * STEP,
                y=BASE_LAT + row * STEP,
                street_count=3,
            )

    trap = _node_id(GRID_COLS - 1, GRID_ROWS - 1)  # 1019
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            here = _node_id(col, row)
            if col + 1 < GRID_COLS:
                right = _node_id(col + 1, row)
                _add_street(g, here, right, both_ways=trap not in (here, right))
            if row + 1 < GRID_ROWS:
                up = _node_id(col, row + 1)
                _add_street(g, here, up, both_ways=trap not in (here, up))
    return g


def build_node_df(graph: nx.MultiDiGraph, idx_maps: dict) -> pd.DataFrame:
    """Client rows for every graph node, in an order that is not the igraph one."""
    nodes = sorted(graph.nodes, reverse=True)  # reversed on purpose
    return pd.DataFrame(
        {
            "node": nodes,
            "centroid_waste": [1 + (n % 3) for n in nodes],
            "x": [graph.nodes[n]["x"] for n in nodes],
            "y": [graph.nodes[n]["y"] for n in nodes],
            "node_ig": [idx_maps["node_nx_to_ig"][n] for n in nodes],
        }
    )


@pytest.fixture(scope="session")
def synthetic_graph() -> nx.MultiDiGraph:
    return build_synthetic_graph()


@pytest.fixture(scope="session")
def graph_path(synthetic_graph, tmp_path_factory):
    """The synthetic graph written as GraphML, so load_graph() runs for real."""
    path = tmp_path_factory.mktemp("graph") / "synthetic.graphml"
    ox.io.save_graphml(synthetic_graph, filepath=str(path))
    return path


@pytest.fixture
def graph_service(graph_path) -> GraphService:
    service = GraphService()
    service.load_graph(str(graph_path))
    return service


@pytest.fixture
def cvrp_service(graph_service) -> CVRPService:
    """A CVRP service with DI centroids on every node, no CSV involved."""
    service = CVRPService()
    service.set_graph_service(graph_service)
    _, idx_maps = networkx_to_igraph_with_indices(graph_service.graph)
    service._node_dfs["DI"] = build_node_df(graph_service.graph, idx_maps)
    return service


@pytest.fixture
def client(graph_service, cvrp_service, monkeypatch):
    """TestClient without the lifespan, so no real graph or centroid CSV is read."""
    from app.api.v1 import routes as routes_module
    from app.main import app

    # routes.py keeps a module-level service; the other session owns that file.
    monkeypatch.setattr(routes_module, "graph_service", graph_service)
    monkeypatch.setattr(app.state, "cvrp_service", cvrp_service)

    if not any(getattr(r, "path", None) == "/_test/boom" for r in app.routes):

        @app.get("/_test/boom")
        async def _boom():
            raise RuntimeError("db password is hunter2")

    return TestClient(app, raise_server_exceptions=False)
