"""How much CO2 a car emits driving one edge.

A distance-based COPERT-style model for a typical European petrol car of
about 1,500 kg. It has no engine, no gearbox and no driver: it says what a
fleet average emits at a steady speed on a given slope, which is the right
grain for comparing two versions of a street network.

Speed. The curve is U-shaped, because a car wastes fuel both crawling and
racing:

    co2_per_km(v) = IDLE_COEFF/v  +  ROLLING_COEFF  +  AERO_COEFF · v²
                    ──────────────   ───────────────    ─────────────────
                    idle, stop-start  rolling resistance  aerodynamic drag

    30 km/h → 203.6 g/km   (city, slow)
    50 km/h → 178.0 g/km   (urban)
    67 km/h → 173.8 g/km   (the minimum of the curve)
   100 km/h → 184.0 g/km   (rural)
   130 km/h → 206.1 g/km   (motorway)

Slope. Climbing costs extra, proportionally to the gradient:

    co2_per_km_uphill = co2_per_km_flat · (1 + grade · GRADE_CO2_SENSITIVITY)
    grade = elevation_gain / length   (a fraction: 0.10 is a 10 % climb)
     5 % → +25 %   10 % → +50 %   15 % → +75 %   20 % → +100 %

Going down costs the same as flat, never less: an engine braking downhill
still burns fuel, and giving a discount would let a route through the hills
look cheaper than it is. On a hilly city this puts an edge between about 170
and 310 g/km.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class CO2Calculator:
    # Speed-emission coefficients (g CO₂ / km)
    IDLE_COEFF: float = 2400.0  # penalty for low-speed / stop-start operation
    ROLLING_COEFF: float = 120.0  # constant rolling-resistance term
    AERO_COEFF: float = 0.004  # aerodynamic drag (increases with v²)

    # Speed assumed when the caller has neither a speed nor a travel time.
    # The graph mirror resolves this before it gets here, so it only bites a
    # direct caller (the CVRP solver on an edge with no data).
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
        return cls.IDLE_COEFF / speed_kph + cls.ROLLING_COEFF + cls.AERO_COEFF * speed_kph**2

    @classmethod
    def calculate_edge_co2(
        cls,
        length: float,
        speed_kph: Optional[float] = None,
        elevation_gain: Optional[float] = None,
        travel_time: Optional[float] = None,
    ) -> float:
        """Grams of CO2 for one vehicle over one edge.

        The routing model uses `edge_co2_array` on whole arrays; this is the
        single-edge form, for the CVRP solver and for tests.

        Args:
            length:         edge length in **metres**
            speed_kph:      average speed in km/h (preferred)
            elevation_gain: metres of climb, 0 or None when flat or downhill
            travel_time:    seconds, only used to derive the speed when
                            speed_kph is missing
        """
        if length <= 0:
            return 0.0

        speed = speed_kph if (speed_kph is not None and speed_kph > 0) else None
        if speed is None and travel_time and travel_time > 0:
            speed = (length / 1000.0) / (travel_time / 3600.0)
        if speed is None or speed <= 0:
            speed = cls.DEFAULT_SPEED_KPH

        return float(
            cls.edge_co2_array(
                np.array([length]), np.array([speed]), np.array([elevation_gain or 0.0])
            )[0]
        )

    @classmethod
    def co2_per_km_at_speed_array(cls, speed_kph: np.ndarray) -> np.ndarray:
        """Vectorised co2_per_km_at_speed, for one value per graph edge."""
        speed = np.asarray(speed_kph, dtype=np.float64)
        safe = np.where(speed > 0, speed, 1.0)
        return np.where(
            speed > 0,
            cls.IDLE_COEFF / safe + cls.ROLLING_COEFF + cls.AERO_COEFF * safe**2,
            cls.IDLE_COEFF + cls.ROLLING_COEFF,
        )

    @classmethod
    def edge_co2_array(
        cls,
        length: np.ndarray,
        speed_kph: np.ndarray,
        elevation_gain: np.ndarray,
    ) -> np.ndarray:
        """Grams of CO2 for one vehicle over each edge. The model, in one array."""
        length = np.asarray(length, dtype=np.float64)
        speed = np.asarray(speed_kph, dtype=np.float64)
        elev = np.asarray(elevation_gain, dtype=np.float64)

        speed = np.where(speed > 0, speed, cls.DEFAULT_SPEED_KPH)
        per_km = cls.co2_per_km_at_speed_array(speed)

        safe_length = np.where(length > 0, length, 1.0)
        grade = np.where((elev > 0) & (length > 0), elev / safe_length, 0.0)
        grade_factor = 1.0 + grade * cls.GRADE_CO2_SENSITIVITY

        return np.where(length > 0, per_km * (length / 1000.0) * grade_factor, 0.0)
