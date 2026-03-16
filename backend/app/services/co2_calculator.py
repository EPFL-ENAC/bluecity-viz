"""CO2 emissions calculator for vehicle routes.

Distance-based COPERT-style model for a typical European passenger car (petrol, ~1500 kg).

Speed-emission curve (U-shaped, minimum around 70 km/h):
    co2_per_km(v) = IDLE_COEFF/v  +  ROLLING_COEFF  +  AERO_COEFF * v²
                    ──────────────   ───────────────    ─────────────────
                    idle/stop-start  rolling resistance  aerodynamic drag

Calibrated to roughly match EU fleet average:
    30 km/h → ~204 g/km   (city slow)
    50 km/h → ~178 g/km   (urban)
    70 km/h → ~168 g/km   (suburban, ~optimal)
   100 km/h → ~182 g/km   (rural)
   130 km/h → ~218 g/km   (motorway)

Grade penalty (relative, calibrated to ICCT road-grade measurements for ICE cars):
    co2_per_km_uphill = co2_per_km_flat × (1 + grade × GRADE_CO2_SENSITIVITY)
    grade = elevation_gain / length  (fraction, e.g. 0.10 for 10 %)
     5 % grade → +25 %   10 % → +50 %   15 % → +75 %   20 % → +100 %

Typical range for a hilly city (flat → 15 % steep): ~170–310 g/km.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CO2Calculator:
    # Speed-emission coefficients (g CO₂ / km)
    IDLE_COEFF: float = 2400.0   # penalty for low-speed / stop-start operation
    ROLLING_COEFF: float = 120.0  # constant rolling-resistance term
    AERO_COEFF: float = 0.004    # aerodynamic drag (increases with v²)

    # Fallback speed when neither speed_kph nor travel_time is available
    DEFAULT_SPEED_KPH: float = 40.0

    # Grade-relative CO₂ sensitivity.
    # Each unit of grade (fraction, not percent) multiplies base CO₂/km by (1 + grade × factor).
    # Calibrated from ICCT road-grade measurements for ICE passenger cars:
    #   5 % grade  → +25 %   (0.05 × 5.0 = 0.25)
    #  10 % grade  → +50 %   (0.10 × 5.0 = 0.50)
    #  15 % grade  → +75 %   (0.15 × 5.0 = 0.75)
    #  20 % grade  → +100 %  (0.20 × 5.0 = 1.00)
    GRADE_CO2_SENSITIVITY: float = 5.0

    @classmethod
    def co2_per_km_at_speed(cls, speed_kph: float) -> float:
        """Return CO₂ emission rate in g/km for a given constant speed."""
        if speed_kph <= 0:
            return cls.IDLE_COEFF + cls.ROLLING_COEFF  # pathological edge
        return (
            cls.IDLE_COEFF / speed_kph
            + cls.ROLLING_COEFF
            + cls.AERO_COEFF * speed_kph ** 2
        )

    @classmethod
    def calculate_edge_co2(
        cls,
        length: float,
        speed_kph: Optional[float] = None,
        elevation_gain: Optional[float] = None,
        travel_time: Optional[float] = None,
    ) -> float:
        """Calculate CO₂ emissions (grams) for a single edge.

        Args:
            length:        Edge length in **metres**.
            speed_kph:     Average speed in km/h (preferred).
            elevation_gain: Elevation gain in metres (positive = uphill).
            travel_time:   Travel time in seconds — used only to derive speed
                           when speed_kph is missing.
        """
        if length <= 0:
            return 0.0

        # Resolve speed
        speed = speed_kph if (speed_kph is not None and speed_kph > 0) else None
        if speed is None and travel_time and travel_time > 0:
            speed = (length / 1000.0) / (travel_time / 3600.0)
        if speed is None or speed <= 0:
            speed = cls.DEFAULT_SPEED_KPH

        length_km = length / 1000.0

        # Grade multiplier: each 1 % of slope adds GRADE_CO2_SENSITIVITY % to base CO₂/km.
        # grade = rise / run (fraction), clamped so we never go below 1.0.
        grade_factor = 1.0
        if elevation_gain and elevation_gain > 0:
            grade = elevation_gain / length  # fraction, e.g. 0.10 for 10 %
            grade_factor = 1.0 + grade * cls.GRADE_CO2_SENSITIVITY

        return cls.co2_per_km_at_speed(speed) * length_km * grade_factor

    @classmethod
    def calculate_route_co2(cls, edges_data: list) -> float:
        """Calculate total CO₂ emissions for a route from a list of edge dicts.

        Each dict should contain 'length', and optionally 'speed_kph',
        'travel_time', and 'elevation_gain'.
        """
        return sum(
            cls.calculate_edge_co2(
                length=e.get("length", 0),
                speed_kph=e.get("speed_kph"),
                elevation_gain=e.get("elevation_gain", 0),
                travel_time=e.get("travel_time"),
            )
            for e in edges_data
        )
