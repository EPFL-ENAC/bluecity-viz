"""The /areas endpoints: create a circle, run the workbench on it, lose it."""

import pytest

from app.config import settings
from app.services.area_graph import DEFAULT_AREA_ID

CENTRE = {"lon": 7.106, "lat": 46.108}


def body(radius_m=2000.0, **over):
    return {"circle": {**CENTRE, "radius_m": radius_m, **over}}


@pytest.fixture
def areas_client(client, swiss_store, small_area_limits, monkeypatch):
    """The API client with the lattice store behind /areas."""
    from app.api.v1 import areas as areas_module
    from app.services.sampling.config import SamplingConfig

    monkeypatch.setattr(areas_module, "graph_store", swiss_store)
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


def test_the_default_area_still_serves_its_own_geometry(areas_client, graph_service):
    response = areas_client.get(f"/api/v1/areas/{DEFAULT_AREA_ID}/edges")

    assert response.status_code == 200
    assert len(response.json()) == len(graph_service.graph.edges)


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


# ── Losing an area ────────────────────────────────────────────────────────────


def test_an_evicted_area_is_a_404_and_can_be_created_again(areas_client, graph_service):
    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    assert graph_service.registry.evict(area_id)
    assert areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").status_code == 404

    again = areas_client.post("/api/v1/areas", json=body())
    assert again.status_code == 201
    assert again.json()["id"] == area_id


def test_the_default_area_is_never_evicted(areas_client, graph_service):
    assert not graph_service.registry.evict(DEFAULT_AREA_ID)
    assert (
        areas_client.get(f"/api/v1/routes/graph-info?area_id={DEFAULT_AREA_ID}").status_code == 200
    )


def test_the_budget_drops_the_oldest_area(areas_client, graph_service, monkeypatch):
    monkeypatch.setattr(graph_service.registry, "max_count", 2)  # lausanne + one

    first = areas_client.post("/api/v1/areas", json=body()).json()["id"]
    second = areas_client.post("/api/v1/areas", json=body(radius_m=2500)).json()["id"]

    loaded = [a.meta.id for a in graph_service.registry.loaded()]
    assert DEFAULT_AREA_ID in loaded
    assert second in loaded
    assert first not in loaded


def test_an_area_over_the_budget_is_still_the_one_we_answer_with(areas_client, graph_service):
    """No budget at all: the new area must survive its own insert, else the
    client is sent to an area that is already gone and loops."""
    graph_service.registry.budget_bytes = 0

    area_id = areas_client.post("/api/v1/areas", json=body()).json()["id"]

    assert areas_client.get(f"/api/v1/routes/graph-info?area_id={area_id}").status_code == 200
