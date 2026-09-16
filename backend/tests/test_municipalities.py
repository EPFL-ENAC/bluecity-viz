"""The municipalities file: neighbours, round trip, contiguity and names."""

import pyarrow.parquet as pq
import pytest
from shapely.geometry import box

from app.services.municipalities import Municipalities, label, normalise_ids, outline_geojson
from app.services.municipalities_writer import neighbours_of, write_municipalities


def test_neighbours_share_a_border_not_a_corner():
    left = box(0, 0, 1, 1)
    right = box(1, 0, 2, 1)  # shares the line x = 1
    corner = box(2, 1, 3, 2)  # touches right at one point only
    far = box(10, 10, 11, 11)

    assert neighbours_of([left, right, corner, far], [10, 20, 30, 40]) == [[20], [10], [], []]


def test_the_file_reads_back_sorted(communes_path, communes):
    assert pq.read_table(communes_path).column("bfs").to_pylist() == [1, 2, 3]
    assert len(communes) == 3
    a = communes.get(1)
    assert a.name == "A"
    assert a.canton == 22
    assert a.neighbours == (2,)
    assert a.bbox == pytest.approx((7.04, 46.04, 7.089, 46.14))
    assert communes.get(3).neighbours == ()
    assert communes.get(99) is None
    assert communes.names([2, 1, 99]) == ["B", "A"]
    assert communes.source == "test"


def test_an_old_file_is_refused(tmp_path, communes_path):
    table = pq.read_table(communes_path)
    old = table.replace_schema_metadata({"format_version": "0"})
    pq.write_table(old, tmp_path / "old.parquet")

    with pytest.raises(ValueError, match="version"):
        Municipalities.open(tmp_path / "old.parquet")


@pytest.mark.parametrize(
    "ids, expected",
    [([1], True), ([1, 2], True), ([2, 1], True), ([1, 3], False), ([], False), ([1, 99], False)],
)
def test_contiguous(communes, ids, expected):
    assert communes.contiguous(ids) is expected


def test_the_union_of_two_neighbours_is_one_polygon(communes):
    outline = outline_geojson(communes.union([1, 2]))

    assert outline["type"] == "Polygon"
    assert len(outline["coordinates"]) == 1, "no hole where the border was"


def test_ids_are_sorted_as_numbers():
    assert normalise_ids([10, 5, 5, 2]) == (2, 5, 10)


def test_labels():
    assert label(["Lausanne"]) == "Lausanne"
    assert label(["Lausanne", "Pully"]) == "Lausanne + Pully"
    assert label(["Lausanne", "Pully", "Lutry", "Paudex", "Epalinges"]) == (
        "Lausanne, Pully + 3 more"
    )
    assert len(label(["x" * 50, "y" * 50])) == 60
    assert label([]) == ""


def test_writer_keeps_the_rows_together(tmp_path):
    path = write_municipalities(
        tmp_path / "m.parquet",
        bfs=[5, 3],
        name=["five", "three"],
        canton=[1, 2],
        neighbours=[[3], [5]],
        geometry=[box(1, 0, 2, 1), box(0, 0, 1, 1)],
    )
    table = Municipalities.open(path)

    assert table.get(3).name == "three" and table.get(3).canton == 2
    assert table.get(5).bbox == (1.0, 0.0, 2.0, 1.0)
