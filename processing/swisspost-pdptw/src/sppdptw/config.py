"""Paths to the Swiss Post data files, resolved relative to this subproject."""

from pathlib import Path

# processing/swisspost-pdptw/
PROJECT_DIR = Path(__file__).resolve().parents[2]
# repo root
REPO_ROOT = PROJECT_DIR.parents[1]

DATA_DIR = REPO_ROOT / "SWISS POST DATA" / "DATA"
INSTANCE_PATH = DATA_DIR / "Sectors" / "Mock-n30-d70_instance.json"
SOLUTION_PATH = DATA_DIR / "Sectors" / "Mock-n30-d70_solution.json"
MATRIX_PATH = DATA_DIR / "newSwissPost" / "02-9a1f57088926808757a37448b43db56f6b5caf17.npz"
INDEX_MAPPING_PARQUET = DATA_DIR / "newSwissPost" / "03-index_mapping.parquet"

# Files produced by the notebooks
LOCAL_DATA_DIR = PROJECT_DIR / "data"
CACHE_DIR = LOCAL_DATA_DIR / "cache"
INDEX_MAPPING_CSV = LOCAL_DATA_DIR / "index_mapping.csv"
OUTPUTS_DIR = PROJECT_DIR / "outputs"

# The delivery area studied in the pdptw project (see EPFL-ENAC/pdptw)
AREA_ID = 340070
