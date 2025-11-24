"""CO2 emissions calculator for vehicle routes."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CO2Calculator:
    """
    Calculate CO2 emissions for vehicle routes based on speed, elevation, and travel time.

    This is a simplified model for proof of concept purposes.
    """

    # Base emission rate in grams of CO2 per second (assuming average car at optimal conditions)
    BASE_EMISSION_RATE = 2.5  # g CO2/s (roughly 9 kg/hour at steady state)

    # Speed adjustment factors
    OPTIMAL_SPEED_KPH = 60  # Optimal fuel efficiency speed
    SPEED_PENALTY_FACTOR = 0.015  # Penalty per km/h deviation from optimal

    # Elevation gain penalty (extra CO2 per meter of elevation gain per second)
    ELEVATION_PENALTY_RATE = 0.08  # g CO2 per meter of elevation gain per second

    @classmethod
    def calculate_edge_co2(
        cls,
        travel_time: float,
        speed_kph: Optional[float] = None,
        elevation_gain: Optional[float] = None,
    ) -> float:
        """
        Calculate CO2 emissions for a single edge.

        Args:
            travel_time: Time to traverse the edge in seconds
            speed_kph: Speed on the edge in km/h (optional)
            elevation_gain: Elevation gain on the edge in meters (optional)

        Returns:
            CO2 emissions in grams
        """
        if travel_time <= 0:
            return 0.0

        # Base emissions from travel time
        co2 = cls.BASE_EMISSION_RATE * travel_time

        # Speed adjustment: driving too slow or too fast increases emissions
        if speed_kph is not None and speed_kph > 0:
            speed_deviation = abs(speed_kph - cls.OPTIMAL_SPEED_KPH)
            speed_multiplier = 1.0 + (speed_deviation * cls.SPEED_PENALTY_FACTOR)
            co2 *= speed_multiplier

        # Elevation penalty: going uphill requires more fuel
        if elevation_gain is not None and elevation_gain > 0:
            elevation_co2 = elevation_gain * cls.ELEVATION_PENALTY_RATE * travel_time
            co2 += elevation_co2

        return co2

    @classmethod
    def calculate_route_co2(
        cls,
        edges_data: list,
    ) -> float:
        """
        Calculate total CO2 emissions for a route from edge data.

        Args:
            edges_data: List of edge dictionaries with travel_time, speed_kph, elevation_gain

        Returns:
            Total CO2 emissions in grams
        """
        total_co2 = 0.0

        for edge in edges_data:
            travel_time = edge.get("travel_time", 0)
            speed_kph = edge.get("speed_kph")
            elevation_gain = edge.get("elevation_gain", 0)

            edge_co2 = cls.calculate_edge_co2(
                travel_time=travel_time,
                speed_kph=speed_kph,
                elevation_gain=elevation_gain,
            )
            total_co2 += edge_co2

        return total_co2
