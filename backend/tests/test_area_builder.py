"""Cutting an area out of the store, and the rules that refuse a bad one."""

import numpy as np
import pytest

from app.config import settings
from app.services import area_builder
from app.services.area_builder import (
    AreaRejected,
    CircleSpec,
    MunicipalitySpec,
    giant_component,
    select,
)
from app.services.area_graph import NoPopulationData
from app.services.graph_store import distance_m
from app.services.sampling.config import SamplingConfig

CENTRE_LON, CENTRE_LAT = 7.106, 46.108  # middle of the lattice


def circle(radius_m=2000.0, lon=CENTRE_LON, lat=CENTRE_LAT):
    return CircleSpec.from_circle(lon, lat, radius_m)


# ── The id and the shape ──────────────────────────────────────────────────────


def test_the_id_comes_from_the_geometry():
    one = CircleSpec.from_circle(7.44, 46.95, 3000)
    same = CircleSpec.from_circle(7.44000004, 46.95000004, 3000.4)
    other = CircleSpec.from_circle(7.44, 46.95, 3500)

    assert one.id == "c_7.4400_46.9500_3000"
    assert same.id == one.id, "a pixel of drag must not make a new area"
    assert other.id != one.id


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
    counts, mask = area_builder.check(swiss_store, circle(2000))

    assert counts["junction_count"] >= settings.area_min_junctions
    assert counts["scc_fraction"] == 1.0
    assert mask.all(), "one network, so every node is in it"


def test_too_small_a_circle_is_too_sparse(swiss_store, small_area_limits):
    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, circle(400))

    assert raised.value.code == "too_sparse"
    assert raised.value.counts["junction_count"] < settings.area_min_junctions


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
    assert len(area.pairs) == settings.od_pairs_max
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


def dense_share(area, pairs):
    """Share of the pair ends that fall in the dense block of the lattice."""
    from tests.conftest import DENSE_COLS, DENSE_ROWS, STORE_COLS

    ends = np.concatenate([pairs.origins, pairs.destinations]) - 2000
    rows, cols = np.divmod(ends, STORE_COLS)
    dense = np.isin(rows, list(DENSE_ROWS)) & np.isin(cols, list(DENSE_COLS))
    return dense.mean()


def test_a_population_sample_leans_to_where_people_live(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(2000), SamplingConfig(n_nodes_preprocess=100))

    population = area.od_set("population")

    assert len(population.pairs) == len(area.pairs)
    assert not np.array_equal(population.pairs.origins, area.pairs.origins)
    assert dense_share(area, population.pairs) > dense_share(area, area.pairs) + 0.1
    # the betweenness does not depend on the pairs, it is shared
    assert population.baseline.bc is area.baseline.bc
    assert population.baseline.routes.n_found > 0
    # asking again gives the same set, no second sampling
    assert area.od_set("population") is population


def test_a_population_recalculate_uses_its_own_pairs(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(2000), SamplingConfig(n_nodes_preprocess=100))

    uniform = area.recalculate_with_modifications(edge_modifications=[], od_pairs=100)
    population = area.recalculate_with_modifications(
        edge_modifications=[], od_pairs=100, node_weighting="population"
    )

    def counts(result):
        return {(r["u"], r["v"]): r["count"] for r in result["new_edge_usage"]}

    assert counts(uniform) != counts(population)


def test_an_area_without_population_says_so(make_store, small_area_limits):
    store = make_store(population=False)
    area = area_builder.build(store, circle(2000), SamplingConfig(n_nodes_preprocess=100))

    with pytest.raises(NoPopulationData):
        area.od_set("population")
    # the uniform workbench still runs
    assert area.od_set("uniform").baseline is not None


def test_the_edge_payload_is_ready_right_after_the_build(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(1500), SamplingConfig(n_nodes_preprocess=100))

    data, etag = area.payloads.get_or_build("edges", lambda: [])
    assert etag
    assert b'"coordinates"' in data
    assert b'"speed_kph"' in data


def test_a_disconnected_area_keeps_only_the_main_network(
    make_store, small_area_limits, monkeypatch
):
    store = make_store(cut_column=15)
    monkeypatch.setattr(settings, "area_min_scc_fraction", 0.3)

    area = area_builder.build(store, circle(4000), SamplingConfig(n_nodes_preprocess=100))

    everything = select(store, circle(4000))
    assert area.mirror.n_nodes < everything.n_nodes


# ── Municipalities ────────────────────────────────────────────────────────────


def communes_spec(ids, table):
    return MunicipalitySpec.from_ids(ids, table)


def test_the_municipality_id_is_the_sorted_set(communes):
    assert communes_spec([2, 1, 1], communes).id == "m_1_2"
    assert communes_spec([1, 2], communes) == communes_spec([2, 1], communes)


def test_ids_sort_as_numbers_not_as_text(communes):
    assert communes_spec([10, 5], communes).id == "m_5_10"


def test_one_municipality_keeps_only_its_nodes(swiss_store, communes):
    spec = communes_spec([1], communes)
    selection = select(swiss_store, spec)

    # A ends at 7.089: the columns at 7.050 .. 7.088, 20 of 40, all 40 rows
    assert selection.n_nodes == 20 * 40
    assert selection.x.max() < 7.089


def test_two_neighbours_keep_the_streets_across_the_border(swiss_store, communes):
    selection = select(swiss_store, communes_spec([1, 2], communes))

    assert selection.n_nodes == 40 * 40
    xs = dict(zip(selection.node_id.tolist(), selection.x.tolist()))
    crossing = [
        (u, v)
        for u, v in zip(selection.edges["u"].tolist(), selection.edges["v"].tolist())
        if (xs[u] < 7.089) != (xs[v] < 7.089)
    ]
    assert crossing, "the streets between A and B are part of the area"


def test_an_unknown_municipality_is_outside_coverage(swiss_store, communes, small_area_limits):
    spec = communes_spec([1, 9999], communes)

    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, spec)

    assert raised.value.code == "outside_coverage"
    assert "9999" in raised.value.message


def test_two_towns_apart_are_refused_before_reading_cells(
    swiss_store, communes, small_area_limits, monkeypatch
):
    def no_read(*args, **kwargs):
        raise AssertionError("the cells must not be read")

    monkeypatch.setattr(swiss_store, "read_nodes", no_read)
    monkeypatch.setattr(swiss_store, "read_edges", no_read)
    spec = communes_spec([1, 3], communes)

    for run in (
        lambda: area_builder.check(swiss_store, spec),
        lambda: area_builder.build(swiss_store, spec, SamplingConfig(n_nodes_preprocess=100)),
    ):
        with pytest.raises(AreaRejected) as raised:
            run()
        assert raised.value.code == "not_contiguous"

    answer = area_builder.preview(swiss_store, spec)
    assert answer["ok"] is False and answer["code"] == "not_contiguous"


def test_two_neighbours_pass_the_rules(swiss_store, communes, small_area_limits):
    counts, mask = area_builder.check(swiss_store, communes_spec([1, 2], communes))

    assert counts["node_count"] == 1600
    assert mask.all()


def test_a_big_set_of_municipalities_is_too_large(
    swiss_store, communes, small_area_limits, monkeypatch
):
    monkeypatch.setattr(settings, "area_max_nodes", 1000)
    spec = communes_spec([1, 2], communes)

    with pytest.raises(AreaRejected) as raised:
        area_builder.check(swiss_store, spec)
    assert raised.value.code == "too_large"
    assert raised.value.counts["node_count"] == 1600

    answer = area_builder.preview(swiss_store, spec)
    assert answer["code"] == "too_large"
    assert answer["outline"]["type"] == "Polygon", "the picker still draws the shape"


def test_building_municipalities_describes_them(swiss_store, communes, small_area_limits):
    area = area_builder.build(
        swiss_store, communes_spec([2, 1], communes), SamplingConfig(n_nodes_preprocess=100)
    )

    meta = area.meta
    assert meta.id == "m_1_2"
    assert meta.kind == "municipalities"
    assert meta.name == "A + B"
    assert meta.municipalities == {"ids": [1, 2], "names": ["A", "B"]}
    assert meta.circle is None
    assert meta.outline["type"] == "Polygon"
    assert meta.bbox == pytest.approx([7.04, 46.04, 7.14, 46.14])
    assert area.mirror.n_nodes == 1600


def test_a_circle_area_keeps_its_description(swiss_store, small_area_limits):
    area = area_builder.build(swiss_store, circle(1500), SamplingConfig(n_nodes_preprocess=100))

    assert area.meta.kind == "circle"
    assert area.meta.circle == {"lon": CENTRE_LON, "lat": CENTRE_LAT, "radius_m": 1500.0}
    assert area.meta.municipalities is None and area.meta.outline is None
