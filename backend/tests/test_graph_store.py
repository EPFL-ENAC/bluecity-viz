"""The Swiss graph on disk: one row group per cell, read a circle in a few ms."""

import json

import numpy as np
import pytest

from app.services.graph_store import (
    DENSITY_FILE,
    FORMAT_VERSION,
    INDEX_FILE,
    GraphStore,
    Grid,
    distance_m,
)
from app.services.graph_store_writer import (
    DENSITY_REFINE,
    M_PER_DEG,
    simplify_geometry,
    write_store,
)

# A small grid of streets spread over several cells, built by hand so the test
# knows exactly what should come back.
GRID = Grid(lon0=6.0, lat0=46.0, dlon=0.05, dlat=0.05, ncols=6, nrows=6)
COLS, ROWS = 12, 12
STEP = 0.02  # about 1.5 km, so a cell holds a few nodes


def build_store(tmp_path, street_count=3):
    """A COLS x ROWS lattice of one-way-free streets, written as a store."""
    node_id, xs, ys = [], [], []
    for r in range(ROWS):
        for c in range(COLS):
            node_id.append(1000 + r * COLS + c)
            xs.append(6.01 + c * STEP)
            ys.append(46.01 + r * STEP)
    node_id = np.array(node_id, dtype=np.int64)
    xs = np.array(xs)
    ys = np.array(ys)
    pos = {int(n): i for i, n in enumerate(node_id)}

    u, v = [], []
    for r in range(ROWS):
        for c in range(COLS):
            here = 1000 + r * COLS + c
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr < ROWS and cc < COLS:
                    there = 1000 + rr * COLS + cc
                    u += [here, there]
                    v += [there, here]
    u = np.array(u, dtype=np.int64)
    v = np.array(v, dtype=np.int64)
    n = len(u)

    length = np.array(
        [
            distance_m(xs[pos[int(b)]], ys[pos[int(b)]], xs[pos[int(a)]], ys[pos[int(a)]])
            for a, b in zip(u, v)
        ]
    )
    nodes = {
        "node_id": node_id,
        "x": xs,
        "y": ys,
        "street_count": np.full(len(node_id), street_count, dtype=np.int16),
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
    index = write_store(tmp_path, nodes, edges, grid=GRID)
    return index, nodes, edges


@pytest.fixture
def store(tmp_path):
    build_store(tmp_path)
    return GraphStore.open(tmp_path)


def test_the_index_records_every_cell_that_has_nodes(tmp_path):
    index, nodes, edges = build_store(tmp_path)

    assert index["format_version"] == FORMAT_VERSION
    assert index["totals"] == {"nodes": len(nodes["node_id"]), "edges": len(edges["u"])}
    assert sum(c["n_nodes"] for c in index["cells"].values()) == len(nodes["node_id"])
    assert sum(c["n_edges"] for c in index["cells"].values()) == len(edges["u"])
    assert len(index["cells"]) > 1, "the lattice should span several cells"


def test_one_row_group_per_cell(store):
    nodes_file = store._nodes
    assert nodes_file.metadata.num_row_groups == len(store.cells)


def test_reading_a_cell_gives_back_its_nodes(store):
    cell = next(iter(store.cells))
    nodes = store.read_nodes([cell])

    assert len(nodes["node_id"]) == store.cells[cell]["n_nodes"]
    assert set(nodes["cell"]) == {cell}

    # The cell column is what counts. Recomputing it from the stored float32
    # coordinates can land next door for a node exactly on a boundary, which
    # is why the reader never recomputes it.
    minlon, minlat, maxlon, maxlat = store.grid.bounds_of(cell)
    eps = 1e-4
    assert np.all((nodes["x"] >= minlon - eps) & (nodes["x"] <= maxlon + eps))
    assert np.all((nodes["y"] >= minlat - eps) & (nodes["y"] <= maxlat + eps))


def test_edges_are_stored_in_the_cell_of_their_start_node(store):
    for cell, entry in store.cells.items():
        if entry["edges_rg"] is None:
            continue
        edges = store.read_edges([cell])
        nodes = store.read_nodes([cell])
        assert set(edges["u"]) <= set(nodes["node_id"])


def test_a_circle_reads_only_the_cells_it_touches(store):
    lon, lat = 6.12, 46.12
    cells = store.cells_for_circle(lon, lat, 2_000)

    assert cells
    assert len(cells) < len(store.cells)
    # every node inside the circle is in one of those cells
    everything = store.read_nodes(sorted(store.cells))
    inside = distance_m(everything["x"], everything["y"], lon, lat) <= 2_000
    picked = store.read_nodes(cells)
    assert set(everything["node_id"][inside]) <= set(picked["node_id"])


def test_a_circle_outside_the_data_reads_nothing(store):
    assert store.cells_for_circle(9.5, 47.5, 3_000) == []
    assert len(store.read_nodes([])["node_id"]) == 0
    assert len(store.read_edges([])["u"]) == 0


def test_counts_come_from_the_index_without_reading(store):
    cells = sorted(store.cells)
    counts = store.counts_for(cells)

    assert counts["n_nodes"] == len(store.read_nodes(cells)["node_id"])
    assert counts["n_edges"] == len(store.read_edges(cells)["u"])
    assert counts["n_nodes_sc3"] == counts["n_nodes"]  # every node has street_count 3


def test_geometry_comes_back_as_a_flat_array(store):
    cells = sorted(store.cells)[:2]
    edges = store.read_edges(cells, with_geometry=True)

    n = len(edges["u"])
    assert len(edges["geom_offsets"]) == n + 1
    assert edges["geom_flat"].dtype == np.float32
    assert edges["highway"][0] == "residential"
    first = edges["geom_flat"][edges["geom_offsets"][0] : edges["geom_offsets"][1]]
    assert len(first) == 4  # a straight line: two points, lon and lat


def test_the_density_file_is_finer_than_the_store_but_adds_up(tmp_path):
    """The picker sums this file, so its cells are smaller than the store's.

    A town is not spread evenly over a 25 km2 cell, so at the store's
    resolution the estimate came out far too low. The totals still have to
    match, cell by cell, once the fine cells are folded back.
    """
    index, _nodes, _edges = build_store(tmp_path)
    density = json.loads((tmp_path / DENSITY_FILE).read_text())
    fine = density["grid"]
    refine = DENSITY_REFINE

    assert fine["lon0"] == GRID.lon0 and fine["lat0"] == GRID.lat0
    assert fine["ncols"] == GRID.ncols * refine
    assert fine["nrows"] == GRID.nrows * refine
    assert fine["dlon"] == pytest.approx(GRID.dlon / refine)
    assert len(density["nodes_sc3"]) == GRID.n_cells * refine * refine

    def folded(values, cell):
        """Sum the fine cells that sit inside one store cell."""
        row, col = divmod(cell, GRID.ncols)
        return sum(
            values[(row * refine + r) * fine["ncols"] + col * refine + c]
            for r in range(refine)
            for c in range(refine)
        )

    for key, entry in index["cells"].items():
        assert folded(density["nodes_sc3"], int(key)) == entry["n_nodes_sc3"]
        assert folded(density["edges"], int(key)) == entry["n_edges"]


def test_an_old_store_is_refused(tmp_path):
    build_store(tmp_path)
    path = tmp_path / INDEX_FILE
    index = json.loads(path.read_text())
    index["format_version"] = FORMAT_VERSION + 1
    path.write_text(json.dumps(index))

    with pytest.raises(ValueError, match="version"):
        GraphStore.open(tmp_path)


def test_cells_in_circle_rejects_the_far_corners():
    grid = Grid(lon0=6.0, lat0=46.0, dlon=0.05, dlat=0.05, ncols=6, nrows=6)
    # a circle in the middle of one cell, smaller than the cell
    cells = grid.cells_in_circle(6.025, 46.025, 500)

    assert cells == [grid.cell_of(6.025, 46.025)]


def test_simplify_drops_the_points_a_road_does_not_need():
    # A straight line with a point every 10 m, and one real corner.
    step = 10 / M_PER_DEG
    straight = np.array([[6.0, 46.0 + i * step] for i in range(20)])
    corner = np.array([[6.0, 46.0], [6.0, 46.001], [6.001, 46.001]])

    kept = simplify_geometry([straight, corner], metres=0.5)

    # the straight run is two points now, the corner keeps its three
    assert len(kept[0]) == 4
    assert len(kept[1]) == 6
    assert kept[0].dtype == np.float32


def test_simplify_never_moves_the_ends_of_an_edge():
    # The ends are the two nodes of the edge, they have to stay put.
    line = np.array([[6.0, 46.0], [6.0005, 46.00002], [6.001, 46.0]])

    kept = simplify_geometry([line], metres=0.5)[0].reshape(-1, 2)

    assert kept[0] == pytest.approx(line[0], abs=1e-6)
    assert kept[-1] == pytest.approx(line[-1], abs=1e-6)


def test_simplify_stays_inside_the_tolerance():
    # A bump of 5 m survives half a metre of tolerance, a bump of 10 cm does not.
    def bump(metres):
        return np.array([[6.0, 46.0], [6.0005, 46.0 + metres / M_PER_DEG], [6.001, 46.0]])

    assert len(simplify_geometry([bump(5)], metres=0.5)[0]) == 6
    assert len(simplify_geometry([bump(0.1)], metres=0.5)[0]) == 4


def test_a_store_keeps_its_numbers_when_the_shapes_are_simplified(store):
    # Only the drawing changes. The lengths come from a column of their own,
    # so they must be exactly what the builder was given.
    cells = sorted(store.cells)
    edges = store.read_edges(cells, with_geometry=True)

    assert len(edges["u"]) > 0
    assert np.all(edges["length"] > 0)
    assert np.all(edges["travel_time"] > 0)
    # every edge still has its two ends
    assert np.all(np.diff(edges["geom_offsets"]) >= 4)
