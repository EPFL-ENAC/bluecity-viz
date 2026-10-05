"""The /areas endpoints: create a circle, run the workbench on it, lose it."""

import numpy as np
import pytest

from app.config import settings
from tests.conftest import start_routing

CENTRE = {"lon": 7.106, "lat": 46.108}


def body(radius_m=2000.0, **over):
    return {"circle": {**CENTRE, "radius_m": radius_m, **over}}


@pytest.fixture
def areas_client(client, swiss_store, communes, small_area_limits, monkeypatch):
    """The API client with the lattice store and the communes behind /areas."""
    from app.api.v1 import areas as areas_module
    from app.services.sampling.config import SamplingConfig

    monkeypatch.setattr(areas_module, "graph_store", swiss_store)
    monkeypatch.setattr(areas_module, "municipalities", communes)
    # a small node pool keeps the build fast
    monkeypatch.setattr(
        areas_module, "SamplingConfig", lambda: SamplingConfig(n_nodes_preprocess=100)
    )
    return client


# ── Without a store ───────────────────────────────────────────────────────────


def test_without_a_swiss_graph_the_endpoints_say_so(client, monkeypatch):
    from app.api.v1 import areas as areas_module

    monkeypatch.setattr(areas_module, "graph_store", None)

    response = client.post("/api/v1/areas", json=body())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "no_swiss_graph"


def test_the_limits_are_readable_without_a_store(client, monkeypatch):
    from app.api.v1 import areas as areas_module

    monkeypatch.setattr(areas_module, "graph_store", None)

    limits = client.get("/api/v1/areas/limits").json()

    assert limits["min_junctions"] == settings.area_min_junctions
    assert limits["coverage_bbox"] is None


# ── Creating ──────────────────────────────────────────────────────────────────


def test_creating_an_area_gives_a_ready_graph(areas_client):
    response = areas_client.post("/api/v1/areas", json=body())

    assert response.status_code == 201
    info = response.json()
    assert info["id"] == "c_7.1060_46.1080_2000"
    assert info["circle"] == {"lon": 7.106, "lat": 46.108, "radius_m": 2000}
    assert info["node_count"] > 0
    assert info["od_pairs"] == settings.od_pairs_max


def test_asking_twice_returns_the_same_area_for_free(areas_client, graph_service):
    first = areas_client.post("/api/v1/areas", json=body()).json()
    loaded = len(graph_service.registry.loaded())

    again = areas_client.post("/api/v1/areas", json=body()).json()

    assert again["id"] == first["id"]
    assert len(graph_service.registry.loaded()) == loaded, "nothing was built twice"


def test_a_shape_that_breaks_a_rule_is_refused_with_its_code(areas_client):
    response = areas_client.post("/api/v1/areas", json=body(radius_m=300))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "too_sparse"
    assert detail["message"]
    assert detail["ok"] is False


def test_a_request_must_give_a_circle(areas_client):
    assert areas_client.post("/api/v1/areas", json={}).status_code == 422


# ── Preview ───────────────────────────────────────────────────────────────────


def test_preview_answers_without_building(areas_client, graph_service):
    loaded = [a.meta.id for a in graph_service.registry.loaded()]
    good = areas_client.post("/api/v1/areas/preview", json=body()).json()
    bad = areas_client.post("/api/v1/areas/preview", json=body(radius_m=300)).json()

    assert good["ok"] is True and good["node_count"] > 0
    assert bad["ok"] is False and bad["code"] == "too_sparse"
    assert [a.meta.id for a in graph_service.registry.loaded()] == loaded, "nothing was built"


# ── Reading ───────────────────────────────────────────────────────────────────


def test_an_unknown_area_is_a_404(areas_client):
    response = areas_client.get("/api/v1/routes/graph-info?area_id=c_1.0000_1.0000_1000")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "area_not_loaded"


def test_the_edges_of_an_area_come_back_with_an_etag(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    response = areas_client.get(f"/api/v1/areas/{area_id}/edges")

    assert response.status_code == 200
    edges = response.json()
    assert len(edges) > 0
    first = edges[0]
    assert set(first) >= {"u", "v", "coordinates", "travel_time", "length", "highway"}
    assert len(first["coordinates"][0]) == 2

    etag = response.headers["etag"]
    again = areas_client.get(f"/api/v1/areas/{area_id}/edges", headers={"If-None-Match": etag})
    assert again.status_code == 304


# ── The default area ──────────────────────────────────────────────────────────


@pytest.fixture
def default_from_store(areas_client, graph_service, swiss_store, monkeypatch):
    """The default area built the way startup builds it, on the lattice."""
    monkeypatch.setattr(settings, "default_area_lon", CENTRE["lon"])
    monkeypatch.setattr(settings, "default_area_lat", CENTRE["lat"])
    monkeypatch.setattr(settings, "default_area_radius_m", 2000.0)
    return graph_service.load_default_area(swiss_store)


def test_the_default_area_is_a_circle_from_the_store(default_from_store, graph_service):
    area = default_from_store

    assert graph_service.default_area_id == area.meta.id == "c_7.1060_46.1080_2000"
    assert area.meta.name == "Lausanne"
    assert area.mirror.has_population
    # pinned, and with the bigger caches the default always had
    assert area.meta.id in graph_service.registry.pinned
    assert not area.dynamic


def test_a_request_with_no_area_runs_on_the_default_circle(areas_client, default_from_store):
    info = areas_client.get("/api/v1/routes/graph-info").json()

    assert info["area_id"] == default_from_store.meta.id


def test_population_weighting_works_on_the_default_area(areas_client, default_from_store):
    response = areas_client.post(
        "/api/v1/routes/recalculate",
        json={"edge_modifications": [], "node_weighting": "population", "od_pairs": 100},
    )

    assert response.status_code == 200, response.text


def test_creating_the_default_circle_answers_from_memory(areas_client, default_from_store):
    response = areas_client.post("/api/v1/areas", json=body())

    assert response.json()["id"] == default_from_store.meta.id
    assert response.json()["name"] == "Lausanne"


def test_the_default_area_serves_its_edges_like_any_area(areas_client, default_from_store):
    response = areas_client.get(f"/api/v1/areas/{default_from_store.meta.id}/edges")

    assert response.status_code == 200
    assert len(response.json()) > 0


# ── The waste tool flag ───────────────────────────────────────────────────────


def test_an_area_off_the_cvrp_graph_has_no_waste_tool(areas_client):
    # The lattice and the synthetic CVRP grid share no node id.
    assert areas_client.post("/api/v1/areas", json=body()).json()["cvrp"] is False


def test_an_area_on_the_cvrp_graph_has_the_waste_tool(areas_client, graph_service):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    ids = graph_service.registry.get(area_id).mirror.node_ids
    # Most of the area in the CVRP graph: on. A third of it: off.
    graph_service.cvrp_node_ids = np.sort(ids[: int(len(ids) * 0.6)])
    assert areas_client.post("/api/v1/areas", json=body()).json()["cvrp"] is True

    graph_service.cvrp_node_ids = np.sort(ids[: len(ids) // 3])
    assert areas_client.post("/api/v1/areas", json=body()).json()["cvrp"] is False


def test_no_cvrp_graph_means_no_waste_tool(areas_client, graph_service):
    graph_service.cvrp_node_ids = None
    assert areas_client.post("/api/v1/areas", json=body()).json()["cvrp"] is False


# ── Using an area ─────────────────────────────────────────────────────────────


def test_the_workbench_runs_on_a_created_area(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    info = areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").json()
    assert info["area_id"] == area_id
    assert info["od_pairs"] > 0

    baseline = areas_client.get(f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100").json()
    busiest = max(baseline["edge_usage"], key=lambda r: r["count"])

    result = areas_client.post(
        "/api/v1/routes/recalculate",
        json={
            "area_id": area_id,
            "od_pairs": 100,
            "include_baseline": False,
            "edge_modifications": [{"u": busiest["u"], "v": busiest["v"], "action": "remove"}],
        },
    )

    assert result.status_code == 200
    assert result.json()["new_edge_usage"]


def test_two_areas_never_share_a_baseline_etag(areas_client):
    one = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    two = areas_client.post("/api/v1/areas", json=body(radius_m=2500)).json()["id"]

    first = areas_client.get(f"/api/v1/routes/baseline?area_id={one}&od_pairs=100")
    second = areas_client.get(f"/api/v1/routes/baseline?area_id={two}&od_pairs=100")

    assert first.headers["etag"] != second.headers["etag"]


def test_the_population_weighting_gives_other_numbers(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    url = f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100"

    uniform = areas_client.get(url)
    population = areas_client.get(url + "&node_weighting=population")

    assert uniform.status_code == population.status_code == 200
    assert uniform.headers["etag"] != population.headers["etag"]
    assert uniform.json()["edge_usage"] != population.json()["edge_usage"]

    result = areas_client.post(
        "/api/v1/routes/recalculate",
        json={
            "area_id": area_id,
            "od_pairs": 100,
            "edge_modifications": [],
            "node_weighting": "population",
        },
    )
    assert result.status_code == 200
    assert result.json()["new_edge_usage"]


def test_the_model_state_is_what_every_run_compares_with(areas_client):
    """GET /baseline with the model options is the left side of /recalculate.

    The Model step draws it, and the Results step compares with it, so the
    two must be the same numbers. With nothing modified, and elastic demand
    on, every delta is zero.
    """
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    url = f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100"
    models = {
        "targeted": ({"use_congestion": False}, ""),
        "equilibrium": (
            {"use_congestion": True, "congestion_iterations": 2},
            "&use_congestion=true&congestion_iterations=2",
        ),
    }

    etags = set()
    for options, query in models.values():
        model = areas_client.get(url + query)
        assert model.status_code == 200
        etags.add(model.headers["etag"])

        run = areas_client.post(
            "/api/v1/routes/recalculate",
            json={
                "area_id": area_id,
                "od_pairs": 100,
                "edge_modifications": [],
                "resample_destinations": True,
                **options,
            },
        ).json()
        assert run["original_edge_usage"] == model.json()["edge_usage"]
        assert all(row["delta_count"] == 0 for row in run["new_edge_usage"])

    assert len(etags) == 2, "the two models must not share an ETag"


def test_the_iterations_mean_nothing_without_congestion(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    url = f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100"

    plain = areas_client.get(url)
    with_iterations = areas_client.get(url + "&congestion_iterations=3")

    assert plain.headers["etag"] == with_iterations.headers["etag"]


def test_the_four_weightings_give_four_baselines(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    url = f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100"
    weightings = ["uniform", "population", "weekday_morning", "weekday_evening"]

    answers = [areas_client.get(f"{url}&node_weighting={w}") for w in weightings]

    assert [a.status_code for a in answers] == [200] * 4
    assert len({a.headers["etag"] for a in answers}) == 4

    for weighting in ("weekday_morning", "weekday_evening"):
        result = areas_client.post(
            "/api/v1/routes/recalculate",
            json={
                "area_id": area_id,
                "od_pairs": 100,
                "edge_modifications": [],
                "node_weighting": weighting,
            },
        )
        assert result.status_code == 200
        assert result.json()["new_edge_usage"]


@pytest.mark.parametrize("weighting", ["population", "weekday_morning", "weekday_evening"])
def test_population_on_a_graph_without_it_is_a_422(areas_client, weighting):
    baseline = areas_client.get(f"/api/v1/routes/baseline?od_pairs=10&node_weighting={weighting}")
    result = areas_client.post(
        "/api/v1/routes/recalculate",
        json={"edge_modifications": [], "od_pairs": 10, "node_weighting": weighting},
    )

    for answer in (baseline, result):
        assert answer.status_code == 422
        assert answer.json()["detail"]["code"] == "no_population_data"


def test_an_unknown_weighting_is_refused(areas_client):
    answer = areas_client.get("/api/v1/routes/baseline?od_pairs=10&node_weighting=cats")

    assert answer.status_code == 422


# ── Two phases: the betweenness first, the trips after ───────────────────────


@pytest.fixture
def held(graph_service):
    """Keep the second build phase of every new area until the test runs it."""
    jobs = []
    graph_service.registry.spawn = jobs.append
    return jobs


def recalculate(client, area_id):
    return client.post(
        "/api/v1/routes/recalculate",
        json={"area_id": area_id, "od_pairs": 100, "edge_modifications": []},
    )


def test_an_area_answers_with_its_betweenness_before_its_trips(areas_client, held):
    created = areas_client.post("/api/v1/areas", json=body())

    assert created.status_code == 201
    info = created.json()
    area_id = info["id"]
    assert info["ready"] is False
    assert info["od_pairs"] == 0
    assert areas_client.get(f"/api/v1/areas/{area_id}").json()["ready"] is False

    edges = areas_client.get(f"/api/v1/areas/{area_id}/edges")
    assert edges.status_code == 200 and edges.json()

    bc = areas_client.get(f"/api/v1/areas/{area_id}/betweenness")
    assert bc.status_code == 200
    rows = bc.json()
    assert rows and set(rows[0]) == {"u", "v", "betweenness_centrality"}
    again = areas_client.get(
        f"/api/v1/areas/{area_id}/betweenness", headers={"If-None-Match": bc.headers["etag"]}
    )
    assert again.status_code == 304


def test_routing_on_an_area_that_is_not_ready_is_a_409(areas_client, held):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    too_early = recalculate(areas_client, area_id)
    baseline = areas_client.get(f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100")

    for answer in (too_early, baseline):
        assert answer.status_code == 409
        assert answer.json()["detail"]["code"] == "area_not_ready"
        assert answer.headers["retry-after"] == "1"


def test_a_weekday_sample_waits_for_the_area_too(areas_client, held):
    """A weekday sample routes on the uniform baseline, so it waits for it."""
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    url = f"/api/v1/routes/baseline?area_id={area_id}&od_pairs=100&node_weighting=weekday_morning"

    too_early = areas_client.get(url)
    assert too_early.status_code == 409
    assert too_early.json()["detail"]["code"] == "area_not_ready"

    held.pop()()
    assert areas_client.get(url).status_code == 200


def test_the_area_is_ready_once_its_trips_are_routed(areas_client, held):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    assert len(held) == 1

    held.pop()()

    info = areas_client.get(f"/api/v1/areas/{area_id}").json()
    assert info["ready"] is True
    assert info["od_pairs"] == settings.od_pairs_max
    assert recalculate(areas_client, area_id).status_code == 200
    # the betweenness did not move
    assert areas_client.get(f"/api/v1/areas/{area_id}/betweenness").status_code == 200


def test_asking_again_while_it_builds_does_not_build_twice(areas_client, held):
    first = areas_client.post("/api/v1/areas", json=body()).json()
    second = areas_client.post("/api/v1/areas", json=body()).json()

    assert second["id"] == first["id"]
    assert second["ready"] is False
    assert len(held) == 1


def test_an_area_that_is_not_ready_is_not_evicted(areas_client, graph_service, held, monkeypatch):
    monkeypatch.setattr(graph_service.registry, "max_count", 2)  # the default area + one

    first = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    second = areas_client.post("/api/v1/areas", json=body(radius_m=2500)).json()["id"]

    assert not graph_service.registry.evict(first)
    assert areas_client.get(f"/api/v1/areas/{first}").status_code == 200

    # once both are ready, the older one can go again
    for job in held:
        job()
    loaded = [a.meta.id for a in graph_service.registry.loaded()]
    assert second in loaded
    assert first not in loaded


def test_the_status_of_an_unknown_area_is_a_404(areas_client):
    for path in ("/api/v1/areas/c_nowhere", "/api/v1/areas/c_nowhere/betweenness"):
        answer = areas_client.get(path)
        assert answer.status_code == 404
        assert answer.json()["detail"]["code"] == "area_not_loaded"


def test_the_default_area_has_its_betweenness_too(client, graph_service):
    area_id = start_routing(graph_service, sampling_method="random", count=60, seed=1).meta.id

    info = client.get(f"/api/v1/areas/{area_id}").json()
    rows = client.get(f"/api/v1/areas/{area_id}/betweenness").json()

    assert info["ready"] is True
    assert rows and all(r["betweenness_centrality"] > 0 for r in rows)


# ── Losing an area ────────────────────────────────────────────────────────────


def test_an_evicted_area_is_a_404_and_can_be_created_again(areas_client, graph_service):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    assert graph_service.registry.evict(area_id)
    assert areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").status_code == 404

    again = areas_client.post("/api/v1/areas", json=body())
    assert again.status_code == 201
    assert again.json()["id"] == area_id


def test_the_default_area_is_never_evicted(areas_client, graph_service):
    default_id = graph_service.default_area_id
    assert not graph_service.registry.evict(default_id)
    assert areas_client.get(f"/api/v1/routes/graph-info?area_id={default_id}").status_code == 200


def test_the_budget_drops_the_oldest_area(areas_client, graph_service, monkeypatch):
    monkeypatch.setattr(graph_service.registry, "max_count", 2)  # the default + one

    first = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    second = areas_client.post("/api/v1/areas", json=body(radius_m=2500)).json()["id"]

    loaded = [a.meta.id for a in graph_service.registry.loaded()]
    assert graph_service.default_area_id in loaded
    assert second in loaded
    assert first not in loaded


def test_an_area_over_the_budget_is_still_the_one_we_answer_with(areas_client, graph_service):
    """No budget at all: the new area must survive its own insert, else the
    client is sent to an area that is already gone and loops."""
    graph_service.registry.budget_bytes = 0

    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    assert areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").status_code == 200


# ── Municipalities ────────────────────────────────────────────────────────────


def communes_body(*ids):
    return {"municipalities": list(ids)}


def test_creating_an_area_from_municipalities(areas_client):
    response = areas_client.post("/api/v1/areas", json=communes_body(2, 1))

    assert response.status_code == 201
    info = response.json()
    assert info["id"] == "m_1_2"
    assert info["kind"] == "municipalities"
    assert info["name"] == "A + B"
    assert info["municipalities"] == {"ids": [1, 2], "names": ["A", "B"]}
    assert info["circle"] is None
    assert info["outline"]["type"] == "Polygon"
    assert info["node_count"] == 1600


def test_a_circle_area_says_its_kind(areas_client):
    info = areas_client.post("/api/v1/areas", json=body()).json()

    assert info["kind"] == "circle"
    assert info["municipalities"] is None and info["outline"] is None


def test_the_same_municipalities_in_another_order_are_one_area(areas_client, graph_service):
    first = areas_client.post("/api/v1/areas", json=communes_body(1, 2)).json()
    areas_client.post("/api/v1/areas", json=body())
    loaded = len(graph_service.registry.loaded())

    again = areas_client.post("/api/v1/areas", json=communes_body(2, 1, 2)).json()

    assert again["id"] == first["id"] == "m_1_2"
    assert len(graph_service.registry.loaded()) == loaded, "nothing was built twice"


def test_municipalities_apart_are_refused(areas_client):
    response = areas_client.post("/api/v1/areas", json=communes_body(1, 3))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "not_contiguous"
    assert detail["ok"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"municipalities": []},
        {"circle": {**CENTRE, "radius_m": 2000}, "municipalities": [1]},
        {"municipalities": list(range(1, 102))},
    ],
)
def test_a_request_must_give_exactly_one_shape(areas_client, payload):
    assert areas_client.post("/api/v1/areas", json=payload).status_code == 422


def test_without_municipalities_only_the_circle_works(areas_client, monkeypatch):
    from app.api.v1 import areas as areas_module

    monkeypatch.setattr(areas_module, "municipalities", None)

    response = areas_client.post("/api/v1/areas/preview", json=communes_body(1))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "no_municipalities"
    assert areas_client.get("/api/v1/areas/limits").json()["has_municipalities"] is False
    assert areas_client.post("/api/v1/areas/preview", json=body()).json()["ok"] is True


def test_the_limits_say_municipalities_are_there(areas_client):
    limits = areas_client.get("/api/v1/areas/limits").json()

    assert limits["has_municipalities"] is True
    assert limits["max_municipalities"] == 100


def test_preview_of_municipalities_gives_the_outline(areas_client, graph_service, monkeypatch):
    loaded = [a.meta.id for a in graph_service.registry.loaded()]

    good = areas_client.post("/api/v1/areas/preview", json=communes_body(1, 2)).json()
    assert good["ok"] is True
    assert good["outline"]["type"] == "Polygon"
    assert good["node_count"] == 1600

    monkeypatch.setattr(settings, "area_max_nodes", 1000)
    big = areas_client.post("/api/v1/areas/preview", json=communes_body(1, 2)).json()
    assert big["ok"] is False and big["code"] == "too_large"
    assert big["outline"]["type"] == "Polygon"

    apart = areas_client.post("/api/v1/areas/preview", json=communes_body(1, 3)).json()
    assert apart["code"] == "not_contiguous"
    assert [a.meta.id for a in graph_service.registry.loaded()] == loaded, "nothing was built"


def test_the_workbench_runs_on_municipalities(areas_client):
    area_id = areas_client.post("/api/v1/areas", json=communes_body(1, 2)).json()["id"]

    edges = areas_client.get(f"/api/v1/areas/{area_id}/edges")
    assert edges.status_code == 200 and len(edges.json()) > 0

    info = areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").json()
    assert info["area_id"] == "m_1_2"

    result = areas_client.post(
        "/api/v1/routes/recalculate",
        json={"area_id": area_id, "od_pairs": 100, "edge_modifications": []},
    )
    assert result.status_code == 200
