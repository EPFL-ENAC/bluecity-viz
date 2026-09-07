# Data contract

The notebooks read the Swiss Post files directly from `../../SWISS POST DATA/DATA/` at the repo root:

| File | Content |
|------|---------|
| `Sectors/Mock-n30-d70_instance.json` | Full instance: 10 delivery areas, locations (with per-realization `visit_time` in **seconds**), vehicle/driver templates, 636 hub-based + 128 transport shipments over 70 planning days. Area **340070** is the one studied (46 locations). |
| `Sectors/Mock-n30-d70_solution.json` | Swiss Post's solver output: per-tour itineraries with timestamped `TourStart / Arrival / Departure / DrivingStart / DrivingEnd / TourEnd` events. |
| `newSwissPost/02-9a1f57088926808757a37448b43db56f6b5caf17.npz` | 82×82 travel-time matrix, `uint16`, **seconds**, asymmetric, zero diagonal. Key `data`. |
| `newSwissPost/03-index_mapping.parquet` | `uuid` → `index` mapping into the matrix. |

## Files produced by the notebooks (all gitignored)

- `cache/` — downloaded Bern-area OSM graph (`bern.graphml`), computed OSM matrices (`osm_matrix_*.npy`)
- `index_mapping.csv` — CSV copy of the parquet (fallback for environments without pyarrow)
- `../outputs/` — figures and `summary_*.json` files passed between notebooks

## Plugging in your own OSM matrix (notebook 04)

Set `OSM_MATRIX_PATH` in the config cell of notebook 04. Accepted formats:

- `.npy` — 82×82 array ordered like `03-index_mapping.parquet` (row i = from location index i), seconds
- wide `.csv` — 82×82 with the location index as header/index
- long `.csv` — columns `from_index, to_index, value` (seconds)
