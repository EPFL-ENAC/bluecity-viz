"""Every routing endpoint can name an area, and says so when it is gone.

An area is not permanent: the registry drops the least recently used ones. A
client that comes back with a saved area id must get a clear 404 and create
it again, not a 500.
"""

from app.services.area_graph import DEFAULT_AREA_ID


def test_graph_info_answers_for_the_default_area(client):
    body = client.get("/api/v1/routes/graph-info").json()

    assert body["area_id"] == DEFAULT_AREA_ID
    assert body["node_count"] == 20
    assert body["edge_count"] == 60
    assert body["scc_fraction"] == 1.0


def test_naming_the_default_area_is_the_same_as_naming_nothing(client):
    default = client.get("/api/v1/routes/graph-info").json()
    named = client.get(f"/api/v1/routes/graph-info?area_id={DEFAULT_AREA_ID}").json()

    assert named == default


def test_unknown_area_is_a_404_with_a_code(client):
    response = client.get("/api/v1/routes/graph-info?area_id=c_9.0000_47.0000_3000")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "area_not_loaded"


def test_unknown_area_on_baseline_is_a_404(client):
    response = client.get("/api/v1/routes/baseline?area_id=gone")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "area_not_loaded"


def test_unknown_area_on_recalculate_is_a_404(client):
    response = client.post(
        "/api/v1/routes/recalculate",
        json={"area_id": "gone", "edge_modifications": []},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "area_not_loaded"


def test_unknown_area_on_clear_cache_is_a_404(client):
    assert client.post("/api/v1/routes/clear-cache?area_id=gone").status_code == 404
    assert client.post("/api/v1/routes/clear-cache").status_code == 200


def test_calculate_runs_on_the_named_area(client, graph_service):
    nodes = client.get("/api/v1/routes/graph-info").json()["sample_nodes"]
    body = {
        "pairs": [{"origin": nodes[0], "destination": nodes[-1]}],
        "area_id": DEFAULT_AREA_ID,
    }

    response = client.post("/api/v1/routes/calculate", json=body)

    assert response.status_code == 200
    assert len(response.json()["routes"]) == 1
