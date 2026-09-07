"""Health endpoints and the test injection itself."""


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_graph_info_uses_the_injected_service(client):
    """Proves the monkeypatch on routes.graph_service works, without touching routes.py."""
    response = client.get("/api/v1/routes/graph-info")
    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] == 20
    assert body["edge_count"] == 60
