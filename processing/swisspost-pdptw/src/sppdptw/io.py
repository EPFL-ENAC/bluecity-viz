"""Loaders for the Swiss Post data files."""

import json

import numpy as np
import pandas as pd

from . import config


def load_instance(path=config.INSTANCE_PATH) -> dict:
    """Load the Swiss Post instance JSON."""
    with open(path) as f:
        return json.load(f)


def load_solution(path=config.SOLUTION_PATH) -> dict:
    """Load the Swiss Post solution JSON (their solver's output)."""
    with open(path) as f:
        return json.load(f)


def load_matrix(path=config.MATRIX_PATH) -> np.ndarray:
    """Load the 82x82 Swiss Post travel-time matrix (seconds, asymmetric)."""
    return np.load(path)["data"].astype(float)


def load_index_mapping() -> pd.DataFrame:
    """Load the uuid -> matrix index mapping.

    Reads the parquet when pyarrow/fastparquet is available; otherwise falls
    back to (or creates) a CSV copy so the notebooks also run in minimal
    environments.
    """
    try:
        df = pd.read_parquet(config.INDEX_MAPPING_PARQUET)
        # Refresh the CSV fallback while we can
        try:
            config.INDEX_MAPPING_CSV.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(config.INDEX_MAPPING_CSV, index=False)
        except OSError:
            pass
        return df
    except ImportError:
        if config.INDEX_MAPPING_CSV.exists():
            return pd.read_csv(config.INDEX_MAPPING_CSV)
        raise ImportError(
            "Reading the index mapping needs pyarrow, or a CSV fallback at "
            f"{config.INDEX_MAPPING_CSV}. Run once in an environment with "
            "pyarrow (uv sync) to create it."
        )


def get_area(instance: dict, area_id: int = config.AREA_ID) -> dict:
    """Return the delivery-area dict for `area_id`."""
    for area in instance["instance"]["delivery_areas"]:
        if area["delivery_area_id"] == area_id:
            return area
    raise KeyError(f"delivery area {area_id} not found")


def load_all():
    """Convenience: (instance, solution, matrix, index_mapping)."""
    return load_instance(), load_solution(), load_matrix(), load_index_mapping()
