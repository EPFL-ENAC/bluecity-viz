"""The generic 500 body and the optional API key."""

from app.config import settings


def test_unhandled_errors_do_not_leak_internals(client):
    response = client.get("/_test/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_api_is_open_when_no_key_is_set(client):
    assert settings.api_key == ""
    assert client.get("/api/v1/routes/graph-info").status_code == 200


def test_api_key_is_required_once_it_is_set(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "s3cret")

    assert client.get("/api/v1/routes/graph-info").status_code == 401
    assert client.get("/api/v1/cvrp/centroids?waste_type=DI").status_code == 401
    assert client.get("/api/v1/routes/graph-info", headers={"X-API-Key": "nope"}).status_code == 401

    ok = client.get("/api/v1/routes/graph-info", headers={"X-API-Key": "s3cret"})
    assert ok.status_code == 200


def test_health_stays_open_with_a_key_set(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "s3cret")
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
