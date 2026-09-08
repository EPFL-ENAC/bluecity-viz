"""Cutting an area out of the store, and the rules that refuse a bad one."""

import numpy as np
import pytest

from app.config import settings
from app.services import area_builder
from app.services.area_builder import AreaRejected, AreaSpec, giant_component, select
from app.services.graph_store import distance_m
from app.services.sampling.config import SamplingConfig

CENTRE_LON, CENTRE_LAT = 7.106, 46.108  # middle of the lattice


def circle(radius_m=2000.0, lon=CENTRE_LON, lat=CENTRE_LAT):
    return AreaSpec.from_circle(lon, lat, radius_m)


# ── The id and the shape ──────────────────────────────────────────────────────


def test_the_id_comes_from_the_geometry():
    one = AreaSpec.from_circle(7.44, 46.95, 3000)
    same = AreaSpec.from_circle(7.44000004, 46.95000004, 3000.4)
    other = AreaSpec.from_circle(7.44, 46.95, 3500)

    assert one.id == "c_7.4400_46.9500_3000"
    assert same.id == one.id, "a pixel of drag must not make a new area"
    assert other.id != one.id


def test_a_polygon_gets_a_stable_id():
    ring = [[7.0, 46.0], [7.1, 46.0], [7.1, 46.1]]
    assert AreaSpec.from_polygon(ring).id == AreaSpec.from_polygon(ring).id
    assert AreaSpec.from_polygon(ring).id.startswith("p_")


def test_a_polygon_keeps_the_points_inside_it():
    square = AreaSpec.from_polygon([[7.0, 46.0], [7.2, 46.0], [7.2, 46.2], [7.0, 46.2]])
    x = np.array([7.1, 6.9, 7.3])
    y = np.array([46.1, 46.1, 46.1])

    assert list(square.contains(x, y)) == [True, False, False]


# ── Selecting ─────────────────────────────────────────────────────────────────


def test_only_the_nodes_inside_the_circle_are_kept(swiss_store):
    spec = circle(1500)
    selection = select(swiss_store, spec)

    assert selection.n_nodes > 0
    assert np.all(distance_m(selection.x, selection.y, spec.lon, spec.lat) <= spec.radius_m + 1e-6)


def test_an_edge_needs_both_ends_inside(swiss_store):
    selection = select(swiss_store, circle(1200))
    inside = set(int(n) for n in selection.node_id)

    assert set(int(u) for u in selection.edges["u"]) <= inside
    assert set(int(v) for v in selection.edges["v"]) <= inside


def test_a_bigger_circle_keeps_more(swiss_store):
    small = select(swiss_store, circle(800))
    big = select(swiss_store, circle(2000))

    assert big.n_nodes > small.n_nodes
    assert set(int(n) for n in small.node_id) <= set(int(n) for n in big.node_id)


# ── The rules ─────────────────────────────────────────────────────────────────


def test_a_good_circle_passes(swiss_store, small_area_limits):
    counts = area_builder.check(swiss_store, circle(2000))

    assert counts["junction_count"] >= settings.area_min_nodes
    assert counts["scc_fraction"] == 1.0


def test_too_small_a_circle_is_too_sparse(swiss_store, small_area_limits):
    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, circle(400))

    assert raised.value.code == "too_sparse"
    assert raised.value.counts["node_count"] < settings.area_min_nodes


def test_too_big_a_circle_is_refused(swiss_store, small_area_limits, monkeypatch):
    monkeypatch.setattr(settings, "area_max_nodes", 200)

    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, circle(3000))

    assert raised.value.code == "too_large"


def test_a_circle_away_from_the_data_is_outside_coverage(swiss_store, small_area_limits):
    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, circle(2000, lon=9.5, lat=47.5))

    assert raised.value.code == "outside_coverage"


def test_a_radius_out_of_range_is_refused(swiss_store, small_area_limits, monkeypatch):
    monkeypatch.setattr(settings, "area_max_radius_m", 2_500.0)

    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, circle(9000))

    assert raised.value.code == "outside_coverage"
    assert "radius" in raised.value.message


def test_a_network_in_two_pieces_is_refused(make_store, small_area_limits):
    store = make_store(cut_column=15)

    with pytest.raises(AreaRejected) as raised:
        area_builder.check(store, circle(4000))

    assert raised.value.code == "disconnected"
    assert raised.value.counts["scc_fraction"] < 0.9


def test_the_giant_component_is_found(make_store, small_area_limits):
    store = make_store(cut_column=15)
    selection = select(store, circle(4000))

    mask, fraction = giant_component(selection)

    assert 0.3 < fraction < 0.8, "the lattice is cut in two halves"
    assert mask.sum() == int(round(fraction * selection.n_nodes))


# ── Preview ───────────────────────────────────────────────────────────────────


def test_preview_says_yes_with_the_counts(swiss_store, small_area_limits):
    answer = area_builder.preview(swiss_store, circle(2000))

    assert answer["ok"] is True
    assert answer["code"] is None
    assert answer["node_count"] > 0
    assert answer["bbox"]


def test_preview_says_no_with_a_code(swiss_store, small_area_limits):
    answer = area_builder.preview(swiss_store, circle(400))

    assert answer["ok"] is False
    assert answer["code"] == "too_sparse"
    assert answer["message"]


# ── Building ──────────────────────────────────────────────────────────────────


def test_building_gives_a_routing_graph_with_a_baseline(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(2000), SamplingConfig(n_nodes_preprocess=100))

    assert area.mirror.n_nodes > 0
    assert area.baseline is not None
    assert len(area.pairs) == settings.area_od_pairs_max
    assert area.baseline.routes.n_found > 0
    assert area.dynamic is True
    assert area.meta.bbox and area.meta.scc_fraction == 1.0
    assert area.meta.build_ms > 0


def test_a_built_area_can_be_recalculated(swiss_store, small_area_limits):
    from app.models.route import EdgeModification

    area = area_builder.build(swiss_store, circle(2000), SamplingConfig(n_nodes_preprocess=100))
    busiest = max(area.baseline.usage_rows, key=lambda r: r["count"])

    result = area.recalculate_with_modifications(
        edge_modifications=[EdgeModification(u=busiest["u"], v=busiest["v"], action="remove")]
    )

    assert result["od_pairs"] > 0
    assert result["new_edge_usage"]
    assert result["impact_statistics"]["total_routes"] > 0


def test_the_edge_payload_is_ready_right_after_the_build(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(1500), SamplingConfig(n_nodes_preprocess=100))

    data, etag = area.payloads.get_or_build("edges", lambda: [])
    assert etag
    assert b'"coordinates"' in data
    assert b'"bus_route_count"' in data


def test_a_disconnected_area_keeps_only_the_main_network(
    make_store, small_area_limits, monkeypatch
):
    store = make_store(cut_column=15)
    monkeypatch.setattr(settings, "area_min_scc_fraction", 0.3)

    area = area_builder.build(store, circle(4000), SamplingConfig(n_nodes_preprocess=100))

    everything = select(store, circle(4000))
    assert area.mirror.n_nodes < everything.n_nodes
