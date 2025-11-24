"""Test CO2 emissions calculation."""

from app.services.co2_calculator import CO2Calculator


def test_co2_calculator():
    """Test basic CO2 calculation."""
    print("Testing CO2 Calculator...")

    # Test 1: Basic edge with only travel time
    co2_basic = CO2Calculator.calculate_edge_co2(
        travel_time=60, speed_kph=None, elevation_gain=None  # 1 minute
    )
    print(f"\n1. Basic edge (60s): {co2_basic:.2f} grams")

    # Test 2: Edge with optimal speed (60 km/h)
    co2_optimal = CO2Calculator.calculate_edge_co2(
        travel_time=60, speed_kph=60, elevation_gain=None
    )
    print(f"2. Optimal speed (60s @ 60km/h): {co2_optimal:.2f} grams")

    # Test 3: Edge with slow speed (30 km/h)
    co2_slow = CO2Calculator.calculate_edge_co2(travel_time=60, speed_kph=30, elevation_gain=None)
    print(f"3. Slow speed (60s @ 30km/h): {co2_slow:.2f} grams")

    # Test 4: Edge with fast speed (100 km/h)
    co2_fast = CO2Calculator.calculate_edge_co2(travel_time=60, speed_kph=100, elevation_gain=None)
    print(f"4. Fast speed (60s @ 100km/h): {co2_fast:.2f} grams")

    # Test 5: Edge with elevation gain
    co2_uphill = CO2Calculator.calculate_edge_co2(
        travel_time=60, speed_kph=60, elevation_gain=10  # 10 meters uphill
    )
    print(f"5. With elevation (60s @ 60km/h + 10m uphill): {co2_uphill:.2f} grams")

    # Test 6: Route with multiple edges
    edges_data = [
        {"travel_time": 30, "speed_kph": 50, "elevation_gain": 0},
        {"travel_time": 45, "speed_kph": 60, "elevation_gain": 5},
        {"travel_time": 60, "speed_kph": 40, "elevation_gain": 0},
    ]
    co2_route = CO2Calculator.calculate_route_co2(edges_data)
    print(f"\n6. Complete route (3 edges, 135s total): {co2_route:.2f} grams")
    print(f"   Average per edge: {co2_route/3:.2f} grams")
    print(f"   Equivalent to {co2_route/1000:.3f} kg")

    print("\n✓ All tests completed successfully!")


if __name__ == "__main__":
    test_co2_calculator()
