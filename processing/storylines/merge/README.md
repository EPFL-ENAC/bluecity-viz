# Population and Employment Merge to Road Nodes
This directory contains the code to merge Swiss population (`STATPOP`) and employment (`STATENT`) data, attach them to the nearest Lausanne road-network nodes, and compute a composite node-level indicator.

## Overview

This module builds a node-level socioeconomic dataset for Lausanne by combining hectometric statistical grids with the road graph nodes used in the traffic analysis workflow.

The pipeline performs:
- **Tabular merge** of `STATPOP` and `STATENT` using shared grid identifiers (`RELI`, `E_KOORD`, `N_KOORD`)
- **Spatial filtering** to keep only observations inside Lausanne
- **Nearest-node assignment** from each 100m grid cell to the closest road graph node
- **Temporal filtering** to keep only the most recent `STATENT` year (`ERHJAHR`)
- **Node aggregation** by `osmid`
- **Indicator computation** using percentile ranks of population and workers

## Files

- `merge.ipynb`: Jupyter notebook with the full exploratory workflow and map visualization
- `merge.py`: Script version of the processing pipeline
- `DataAccess.ipynb`: Notebook to download federal statistical datasets
- `DataAccess.py`: Script to download and extract datasets
- `Makefile`: Convenience commands for download, generation, and cleanup
- `data/`: Input data folder (downloaded and manually added files)
- `.gitignore`: Local ignore rules

## Input Data

The processing expects the following files under `data/`:

- `ag-b-00.03-vz2022statpop/STATPOP2022.csv`
- `ag-b-00.03-22-STATENT2022/STATENT_2022.csv`
- `lausanne_drive_nodes.gpkg`

### How to get them

- Run `DataAccess.py` (or `DataAccess.ipynb`) to download and extract:
  - `STATPOP 2022`
  - `STATENT 2022`
- `lausanne_drive_nodes.gpkg` is **not** downloaded by `DataAccess.py`; it must be generated upstream in `processing/traffic-analysis` and copied into `data/`.

## Method

The script follows these main steps:

1. Load `STATPOP` and `STATENT` selected columns.
2. Merge both datasets on grid keys (`RELI`, `E_KOORD`, `N_KOORD`).
3. Convert each grid point into a 100m x 100m square polygon.
4. Keep only polygons within a Lausanne hull polygon.
5. Spatially join each polygon to its nearest road node (`sjoin_nearest`).
6. Keep only the latest available `ERHJAHR`.
7. Dissolve by `osmid` using sum aggregations.
8. Reattach node point geometry.
9. Compute:
   - `population_percentile` from `B22BTOT`
   - `workers_percentile` from `B08EMPT`
   - `node_coef` as the mean of both percentiles
10. Export to GeoPackage.

## Usage

### Using Make (recommended)
```bash
make download-data
make generate-data