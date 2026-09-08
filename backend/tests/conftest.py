"""Shared fixtures: a small synthetic road network, no lausanne.graphml needed."""

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from app.config import settings
from app.services.cvrp_service import DEPOT_LAT, DEPOT_LON, CVRPService
from app.services.graph_service import GraphService
from app.services.graph_store import GraphStore, Grid
from app.services.graph_store import distance_m as store_distance
from app.services.graph_store_writer import write_store
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


# ── A small Swiss graph store, for the area tests ─────────────────────────────

STORE_GRID = Grid(lon0=7.0, lat0=46.0, dlon=0.05, dlat=0.05, ncols=8, nrows=8)
STORE_COLS, STORE_ROWS = 40, 40
STORE_STEP = 0.002  # about 160 m, so a 2 km circle holds a few hundred nodes


def build_lattice_store(directory, cut_column=None):
    """A lattice of two-way streets, written as a graph store.

    `cut_column` removes every street crossing that column, which splits the
    lattice in two networks that cannot reach each other. That is the shape a
    circle over a lake or a valley has.
    """
    node_id, xs, ys = [], [], []
    for r in range(STORE_ROWS):
        for c in range(STORE_COLS):
            node_id.append(2000 + r * STORE_COLS + c)
            xs.append(7.05 + c * STORE_STEP)
            ys.append(46.05 + r * STORE_STEP)
    node_id = np.array(node_id, dtype=np.int64)
    xs, ys = np.array(xs), np.array(ys)
    pos = {int(n): i for i, n in enumerate(node_id)}

    u, v = [], []
    for r in range(STORE_ROWS):
        for c in range(STORE_COLS):
            here = 2000 + r * STORE_COLS + c
            if c + 1 < STORE_COLS:
                if cut_column is not None and c == cut_column:
                    continue
                there = 2000 + r * STORE_COLS + c + 1
                u += [here, there]
                v += [there, here]
            if r + 1 < STORE_ROWS:
                there = 2000 + (r + 1) * STORE_COLS + c
                u += [here, there]
                v += [there, here]
    # the vertical streets of the cut column would still join the two halves
    if cut_column is not None:
        keep = [
            i
            for i, (a, b) in enumerate(zip(u, v))
            if not ((pos[a] % STORE_COLS == cut_column) or (pos[b] % STORE_COLS == cut_column))
        ]
        u = [u[i] for i in keep]
        v = [v[i] for i in keep]

    u = np.array(u, dtype=np.int64)
    v = np.array(v, dtype=np.int64)
    n = len(u)
    length = np.array(
        [
            store_distance(xs[pos[int(b)]], ys[pos[int(b)]], xs[pos[int(a)]], ys[pos[int(a)]])
            for a, b in zip(u, v)
        ]
    )
    nodes = {
        "node_id": node_id,
        "x": xs,
        "y": ys,
        "street_count": np.full(len(node_id), 3, dtype=np.int16),
        "elevation": np.zeros(len(node_id)),
    }
    edges = {
        "u": u,
        "v": v,
        "key": np.arange(n, dtype=np.int32),
        "length": length,
        "travel_time": length / (50 / 3.6),
        "speed_kph": np.full(n, 50.0),
        "lanes": np.full(n, 2, dtype=np.int16),
        "elev_gain": np.zeros(n),
        "highway": ["residential"] * n,
        "name": ["Rue du Test"] * n,
    }
    write_store(directory, nodes, edges, grid=STORE_GRID)
    return directory


@pytest.fixture(scope="session")
def swiss_store_dir(tmp_path_factory):
    return build_lattice_store(tmp_path_factory.mktemp("swiss_store"))


@pytest.fixture
def swiss_store(swiss_store_dir):
    return GraphStore.open(swiss_store_dir)


@pytest.fixture
def small_area_limits(monkeypatch):
    """Thresholds and OD pair counts that fit the lattice and run fast."""
    monkeypatch.setattr(settings, "area_min_junctions", 100)
    monkeypatch.setattr(settings, "area_max_nodes", 2_000)
    monkeypatch.setattr(settings, "area_max_edges", 8_000)
    monkeypatch.setattr(settings, "area_min_radius_m", 100.0)
    monkeypatch.setattr(settings, "area_max_radius_m", 20_000.0)
    monkeypatch.setattr(settings, "od_pairs_max", 400)
    monkeypatch.setattr(settings, "od_pairs", 200)
    monkeypatch.setattr(settings, "reference_network_km", 100.0)


@pytest.fixture
def make_store(tmp_path):
    """Build a lattice store on demand, with an optional cut in the middle."""

    def _make(cut_column=None):
        directory = tmp_path / f"store_{cut_column}"
        build_lattice_store(directory, cut_column=cut_column)
        return GraphStore.open(directory)

    return _make
