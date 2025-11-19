"""Test with actual graph data."""

import requests
import json

BASE_URL = "http://localhost:8000"


def get_sample_nodes():
    """Get actual sample node IDs from the loaded graph."""
    response = requests.get(f"{BASE_URL}/api/v1/routes/graph-info")

    if response.status_code != 200:
        print("Failed to get graph info")
        return []

    data = response.json()
    sample_nodes = data["sample_nodes"]

    print(f"Graph has {data['node_count']} nodes and {data['edge_count']} edges")
    print(f"Using sample nodes: {sample_nodes[:10]}")

    # Create pairs from the sample nodes
    if len(sample_nodes) >= 4:
        return [
            (sample_nodes[0], sample_nodes[5]),
            (sample_nodes[1], sample_nodes[8]),
        ]
    return []


def test_calculate_routes():
    """Test route calculation with real node IDs."""
    pairs = get_sample_nodes()

    request_data = {
        "pairs": [{"origin": pair[0], "destination": pair[1]} for pair in pairs],
        "weight": "travel_time",
        "include_geometry": True,
    }

    print("Request:", json.dumps(request_data, indent=2))

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/calculate",
        json=request_data,
    )

    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Number of routes calculated: {len(data['routes'])}")
        for i, route in enumerate(data["routes"]):
            print(f"\nRoute {i+1}:")
            print(f"  Origin: {route['origin']}")
            print(f"  Destination: {route['destination']}")
            print(f"  Path length: {len(route['path'])} nodes")
            print(f"  Travel time: {route.get('travel_time', 'N/A')} seconds")
            print(f"  Distance: {route.get('distance', 'N/A')} meters")
    else:
        print("Error:", response.json())


def test_recalculate_routes():
    """Test route recalculation with edge removal."""
    # First calculate original routes
    pairs = get_sample_nodes()

    # Get a route first to find an edge to remove
    request_data = {
        "pairs": [{"origin": pairs[0][0], "destination": pairs[0][1]}],
        "weight": "travel_time",
        "include_geometry": True,
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/calculate",
        json=request_data,
    )

    if response.status_code != 200:
        print("Failed to calculate initial route")
        return

    route = response.json()["routes"][0]
    path = route["path"]

    if len(path) < 3:
        print("Path too short to remove an edge")
        return

    # Remove an edge from the middle
    mid_idx = len(path) // 2
    edge_to_remove = {"u": path[mid_idx], "v": path[mid_idx + 1]}

    print(f"\nRemoving edge: {edge_to_remove['u']} -> {edge_to_remove['v']}")

    recalc_request = {
        "pairs": [{"origin": pairs[0][0], "destination": pairs[0][1]}],
        "edges_to_remove": [edge_to_remove],
        "weight": "travel_time",
        "include_geometry": True,
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/recalculate",
        json=recalc_request,
    )

    print(f"\nRecalculate status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        comparison = data["comparisons"][0]

        print(f"\nOriginal route:")
        print(f"  Path length: {len(comparison['original_route']['path'])} nodes")
        print(
            f"  Travel time: {comparison['original_route'].get('travel_time', 'N/A')} seconds"
        )

        print(f"\nNew route (with edge removed):")
        print(f"  Path length: {len(comparison['new_route']['path'])} nodes")
        print(
            f"  Travel time: {comparison['new_route'].get('travel_time', 'N/A')} seconds"
        )

        if comparison["removed_edge_on_path"]:
            print(f"\n✓ Removed edge was on the original path")
    else:
        print("Error:", response.json())


if __name__ == "__main__":
    print("=" * 60)
    print("Testing BlueCity API with Real Data")
    print("=" * 60)

    print("\n1. Testing route calculation...")
    print("-" * 60)
    test_calculate_routes()

    print("\n\n2. Testing route recalculation with edge removal...")
    print("-" * 60)
    test_recalculate_routes()

    print("\n" + "=" * 60)
    print("Tests complete!")
