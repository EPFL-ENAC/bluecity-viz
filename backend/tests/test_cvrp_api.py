"""CVRP endpoints, from validation up to a real solve on the synthetic graph."""

import pytest


def test_centroids_rejects_an_unknown_waste_type(client):
    assert client.get("/api/v1/cvrp/centroids?waste_type=XX").status_code == 422


def test_centroids_404_when_the_type_is_not_loaded(client):
    response = client.get("/api/v1/cvrp/centroids?waste_type=DV")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_centroids_returns_a_feature_collection(client):
    response = client.get("/api/v1/cvrp/centroids?waste_type=DI")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 20
    first = body["features"][0]
    assert first["geometry"]["type"] == "Point"
    assert set(first["properties"]) == {"node", "centroid_waste"}


@pytest.mark.parametrize(
    "payload",
    [
        {"load_unit": "tonnes"},
        {"waste_type": "XX"},
        {"n_vehicles": 0},
        {"max_runtime": 0},
        {"vehicle_capacity": 1},
    ],
)
def test_solve_rejects_bad_input(client, payload):
    assert client.post("/api/v1/cvrp/solve", json=payload).status_code == 422


def test_solve_returns_routes_that_match_the_reported_distance(client):
    """total_distance_m must be within 1 % of the routed segments."""
    response = client.post(
        "/api/v1/cvrp/solve",
        json={"waste_type": "DI", "n_vehicles": 3, "vehicle_capacity": 100, "max_runtime": 1},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["n_routes"] >= 1
    assert body["centroids_used"] == 20
    assert body["solve_time_ms"] > 0
    assert body["route_segments"]
    assert body["edge_loads"]

    routed = sum(_segment_length_m(seg["path_coordinates"]) for seg in body["route_segments"])
    gap = abs(body["total_distance_m"] - routed) / routed
    assert gap < 0.01, f"solver says {body['total_distance_m']:.0f} m, routes give {routed:.0f} m"


def test_solve_with_a_removed_edge_still_works(client):
    response = client.post(
        "/api/v1/cvrp/solve",
        json={
            "waste_type": "DI",
            "n_vehicles": 3,
            "vehicle_capacity": 100,
            "max_runtime": 1,
            "edge_modifications": [{"u": 1000, "v": 1001, "action": "remove"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["n_routes"] >= 1


def test_solve_503_when_the_graph_is_missing(client, cvrp_service):
    cvrp_service._graph_service.graph = None
    response = client.post("/api/v1/cvrp/solve", json={"waste_type": "DI"})
    assert response.status_code == 503


def test_solve_422_for_a_waste_type_without_centroids(client, cvrp_service):
    cvrp_service._node_dfs.pop("DI")
    response = client.post("/api/v1/cvrp/solve", json={"waste_type": "DI", "max_runtime": 1})
    assert response.status_code == 422


def _segment_length_m(coords: list) -> float:
    import osmnx as ox

    return sum(
        float(ox.distance.great_circle(lat1, lon1, lat2, lon2))
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:])
    )
