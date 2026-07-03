"""Fixed-sequence route re-evaluation.

Re-cost an existing tour (a fixed sequence of stops) under modified
assumptions — a different travel-time matrix, different service times —
WITHOUT re-optimizing. This isolates the "matrix gap" and "service-time gap"
from the "optimization gap": if a tour gets slower under matrix B while its
stop order is held fixed, that difference is purely the matrix's doing.
"""

import numpy as np
import pandas as pd


def evaluate_sequence(
    stops: list[int],
    matrix: np.ndarray,
    visit_times_s: dict[int, float] | float = 0.0,
) -> dict:
    """Cost a fixed stop sequence under a given matrix and service times.

    ``visit_times_s`` is either a per-location dict (matrix index -> seconds)
    or a scalar applied to every intermediate stop (depot endpoints excluded).
    """
    stops = [s for s in stops if s is not None]
    drive_s = float(sum(matrix[i, j] for i, j in zip(stops[:-1], stops[1:])))
    inner = stops[1:-1]
    if isinstance(visit_times_s, dict):
        service_s = float(sum(visit_times_s.get(s, 0.0) for s in inner))
    else:
        service_s = float(visit_times_s) * len(inner)
    return {
        "drive_min": drive_s / 60,
        "service_min": service_s / 60,
        "total_min": (drive_s + service_s) / 60,
        "n_stops": len(inner),
    }


def evaluate_tours(
    tours: pd.DataFrame,
    matrix: np.ndarray,
    visit_times_s: dict[int, float] | float = 0.0,
    label: str = "",
) -> pd.DataFrame:
    """Apply :func:`evaluate_sequence` to every tour of a tours dataframe
    (as produced by :func:`sppdptw.solution.extract_tours`)."""
    rows = []
    for _, tour in tours.iterrows():
        res = evaluate_sequence(tour["stops"], matrix, visit_times_s)
        res["date"] = tour["date"]
        res["area_id"] = tour["area_id"]
        if label:
            res["scenario"] = label
        rows.append(res)
    return pd.DataFrame(rows)
