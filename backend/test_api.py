"""Quick test script for the API."""

import requests

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    response = requests.get(f"{BASE_URL}/")
    print("Health check:", response.json())
    assert response.status_code == 200


def test_calculate_routes():
    """Test route calculation endpoint."""
    # Note: This will fail without a loaded graph
    # This is just to show the API structure
    response = requests.post(
        f"{BASE_URL}/api/v1/routes/calculate",
        json={
            "pairs": [
                {"origin": 123456, "destination": 789012},
            ],
            "weight": "travel_time",
            "include_geometry": True,
        },
    )
    print("Calculate routes status:", response.status_code)
    if response.status_code != 200:
        print("Error:", response.json())


def test_recalculate_routes():
    """Test route recalculation endpoint."""
    response = requests.post(
        f"{BASE_URL}/api/v1/routes/recalculate",
        json={
            "pairs": [
                {"origin": 123456, "destination": 789012},
            ],
            "edges_to_remove": [
                {"u": 111111, "v": 222222},
            ],
            "weight": "travel_time",
            "include_geometry": True,
        },
    )
    print("Recalculate routes status:", response.status_code)
    if response.status_code != 200:
        print("Error:", response.json())


if __name__ == "__main__":
    print("Testing BlueCity API...\n")
    test_health()
    print()
    test_calculate_routes()
    print()
    test_recalculate_routes()
