"""Test CO2 emissions calculation."""

from app.services.co2_calculator import CO2Calculator


def test_co2_calculator():
    """Test distance-based CO2 calculation."""
    print("Testing CO2 Calculator (distance-based model)...")
    print(f"  IDLE={CO2Calculator.IDLE_COEFF}, ROLLING={CO2Calculator.ROLLING_COEFF}, "
          f"AERO={CO2Calculator.AERO_COEFF}, ELEV={CO2Calculator.ELEVATION_CO2_PER_M}")

    # Speed curve sanity check (g/km values)
    print("\nSpeed → g CO₂/km:")
    for v in [10, 30, 50, 70, 90, 110, 130]:
        print(f"  {v:3d} km/h → {CO2Calculator.co2_per_km_at_speed(v):.1f} g/km")

    # Test 1: 500 m edge at default speed (no speed info)
    co2_basic = CO2Calculator.calculate_edge_co2(length=500)
    print(f"\n1. 500 m, no speed info (default {CO2Calculator.DEFAULT_SPEED_KPH} km/h): "
          f"{co2_basic:.2f} g")

    # Test 2: 500 m at 70 km/h (optimal)
    co2_optimal = CO2Calculator.calculate_edge_co2(length=500, speed_kph=70)
    print(f"2. 500 m @ 70 km/h (optimal):  {co2_optimal:.2f} g  "
          f"({co2_optimal / 0.5:.1f} g/km)")

    # Test 3: 500 m at 30 km/h (slow urban)
    co2_slow = CO2Calculator.calculate_edge_co2(length=500, speed_kph=30)
    print(f"3. 500 m @ 30 km/h (slow):     {co2_slow:.2f} g  "
          f"({co2_slow / 0.5:.1f} g/km)")

    # Test 4: 500 m at 120 km/h (fast)
    co2_fast = CO2Calculator.calculate_edge_co2(length=500, speed_kph=120)
    print(f"4. 500 m @ 120 km/h (fast):    {co2_fast:.2f} g  "
          f"({co2_fast / 0.5:.1f} g/km)")

    # Test 5: elevation gain
    co2_flat  = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50)
    co2_uphill = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50, elevation_gain=20)
    print(f"5. 500 m @ 50 km/h, flat:      {co2_flat:.2f} g")
    print(f"   500 m @ 50 km/h, +20 m:     {co2_uphill:.2f} g  "
          f"(+{co2_uphill - co2_flat:.1f} g for 20 m climb)")

    # Test 6: speed derived from length + travel_time
    co2_from_tt = CO2Calculator.calculate_edge_co2(length=500, travel_time=36)  # 50 km/h
    print(f"6. 500 m, travel_time=36s (→50 km/h): {co2_from_tt:.2f} g")

    # Test 7: very short edge (used to blow up with old time-based model)
    co2_short = CO2Calculator.calculate_edge_co2(length=2, speed_kph=50)
    print(f"\n7. 2 m edge @ 50 km/h (outlier check): {co2_short:.4f} g  "
          f"({co2_short / 0.002:.1f} g/km — should be ~178)")

    # Test 8: route with multiple edges (length-based)
    edges_data = [
        {"length": 300, "speed_kph": 50, "elevation_gain": 0},
        {"length": 500, "speed_kph": 70, "elevation_gain": 15},
        {"length": 200, "speed_kph": 30, "elevation_gain": 0},
    ]
    co2_route = CO2Calculator.calculate_route_co2(edges_data)
    print(f"\n8. Route (300+500+200 m, mixed speeds): {co2_route:.2f} g total")

    print("\n✓ All tests completed successfully!")


if __name__ == "__main__":
    test_co2_calculator()
