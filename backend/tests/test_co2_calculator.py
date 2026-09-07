"""CO2 model checks. Read-only, the file belongs to another change."""

import pytest

from app.services.co2_calculator import CO2Calculator


def test_zero_length_emits_nothing():
    assert CO2Calculator.calculate_edge_co2(length=0) == 0.0


def test_the_curve_bottoms_out_around_70_kph():
    rates = {v: CO2Calculator.co2_per_km_at_speed(v) for v in (10, 30, 50, 70, 90, 130)}
    assert min(rates, key=rates.get) == 70
    assert rates[10] > rates[30] > rates[50] > rates[70]
    assert rates[130] > rates[70]


def test_uphill_costs_more_than_flat():
    flat = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50)
    uphill = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50, elevation_gain=25)
    # 25 m over 500 m is a 5 % grade, so +25 %.
    assert uphill == pytest.approx(flat * 1.25)


def test_downhill_is_not_cheaper_than_flat():
    flat = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50)
    downhill = CO2Calculator.calculate_edge_co2(length=500, speed_kph=50, elevation_gain=-25)
    assert downhill == pytest.approx(flat)


def test_speed_comes_from_travel_time_when_missing():
    # 1000 m in 72 s is 50 km/h.
    derived = CO2Calculator.calculate_edge_co2(length=1000, travel_time=72)
    explicit = CO2Calculator.calculate_edge_co2(length=1000, speed_kph=50)
    assert derived == pytest.approx(explicit)


def test_default_speed_is_used_without_any_speed_information():
    value = CO2Calculator.calculate_edge_co2(length=1000)
    expected = CO2Calculator.co2_per_km_at_speed(CO2Calculator.DEFAULT_SPEED_KPH)
    assert value == pytest.approx(expected)
