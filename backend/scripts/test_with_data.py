"""Manual check of the routing API against a running server.

Not a unit test: it needs a backend with the real graph loaded.
Run it with the port of the checkout you want to hit:

    BACKEND_PORT=8000 uv run python scripts/test_with_data.py
"""

import json
import os

import requests

# Git worktrees export their own BACKEND_PORT (see docs/worktree-env/), so the
# tests hit the server of the checkout they run in.
BASE_URL = f"http://localhost:{os.environ.get('BACKEND_PORT', '8000')}"


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
            print(f"\nRoute {i + 1}:")
            print(f"  Origin: {route['origin']}")
            print(f"  Destination: {route['destination']}")
            print(f"  Path length: {len(route['path'])} nodes")
            print(f"  Travel time: {route.get('travel_time', 'N/A')} seconds")
            print(f"  Distance: {route.get('distance', 'N/A')} meters")
    else:
        print("Error:", response.json())


def test_recalculate_routes():
    """Recalculate with one edge removed, on the caller's own OD pairs."""
    pairs = get_sample_nodes()

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/calculate",
        json={"pairs": [{"origin": pairs[0][0], "destination": pairs[0][1]}]},
    )

    if response.status_code != 200:
        print("Failed to calculate initial route")
        return

    path = response.json()["routes"][0]["path"]
    if len(path) < 3:
        print("Path too short to remove an edge")
        return

    mid_idx = len(path) // 2
    u, v = path[mid_idx], path[mid_idx + 1]
    print(f"\nRemoving edge: {u} -> {v}")

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/recalculate",
        json={
            "pairs": [{"origin": pairs[0][0], "destination": pairs[0][1]}],
            "edge_modifications": [{"u": u, "v": v, "action": "remove"}],
        },
    )

    print(f"Recalculate status: {response.status_code}")
    if response.status_code != 200:
        print("Error:", response.json())
        return

    data = response.json()
    stats = data["impact_statistics"]
    print(f"  OD pairs used:   {data['od_pairs']}")
    print(f"  applied:         {len(data['applied_modifications'])} modification(s)")
    print(
        f"  routes:          {stats['total_routes']} total, "
        f"{stats['affected_routes']} affected, {stats['failed_routes']} failed"
    )
    print(f"  extra time:      {stats['total_time_increase_minutes']:.2f} min")
    print(f"  extra distance:  {stats['total_distance_increase_km']:.3f} km")
    print(
        f"  edge usage rows: {len(data['original_edge_usage'])} before, "
        f"{len(data['new_edge_usage'])} after"
    )

    still_used = [r for r in data["new_edge_usage"] if r["u"] == u and r["v"] == v]
    print(f"  removed edge is gone from the new usage: {not still_used}")

    timing = data["timing"]
    print(f"  server time:     {timing['total_ms']} ms")


def test_baseline_and_od_pairs():
    """The baseline endpoint, its ETag, and the per-request OD pair count."""
    info = requests.get(f"{BASE_URL}/api/v1/routes/graph-info").json()
    print(
        f"OD pairs: {info['od_pairs']} sampled, {info['od_pairs_default']} by default, "
        f"{info['od_pairs_max']} max"
    )

    response = requests.get(f"{BASE_URL}/api/v1/routes/baseline")
    etag = response.headers.get("ETag")
    print(
        f"  GET /baseline:   {response.status_code}, {len(response.content) / 1e6:.2f} MB, "
        f"{len(response.json()['edge_usage'])} rows"
    )

    again = requests.get(f"{BASE_URL}/api/v1/routes/baseline", headers={"If-None-Match": etag})
    print(f"  same ETag again: {again.status_code} (304 means the client keeps its copy)")

    small = requests.get(f"{BASE_URL}/api/v1/routes/baseline?od_pairs=5000").json()
    full = requests.get(f"{BASE_URL}/api/v1/routes/baseline?od_pairs={info['od_pairs_max']}").json()
    print(f"  5,000 pairs:     {small['total_routes']} routes, {len(small['edge_usage'])} edges")
    print(f"  full set:        {full['total_routes']} routes, {len(full['edge_usage'])} edges")

    response = requests.post(
        f"{BASE_URL}/api/v1/routes/recalculate",
        json={"edge_modifications": [], "od_pairs": 5000, "include_baseline": False},
    )
    data = response.json()
    print(
        f"  recalculate at 5,000 pairs: od_pairs={data['od_pairs']}, "
        f"{len(response.content) / 1e6:.2f} MB without the baseline"
    )

    too_many = requests.post(
        f"{BASE_URL}/api/v1/routes/recalculate",
        json={"edge_modifications": [], "od_pairs": info["od_pairs_max"] + 1},
    )
    print(f"  asking for more than the max: {too_many.status_code} (422 expected)")


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

    print("\n\n3. Testing the baseline and the OD pair count...")
    print("-" * 60)
    test_baseline_and_od_pairs()

    print("\n" + "=" * 60)
    print("Tests complete!")
