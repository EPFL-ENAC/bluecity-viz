# Sparrow CO2 Emissions Processing

This directory contains scripts for processing CO2 emissions data from the Sparrow API.

## Overview

The processing pipeline:
1. Downloads CO2 emissions data from Sparrow API (or uses cached data)
2. Aggregates point data into H3 hexagonal bins (resolution 10)
3. Removes outliers using IQR method
4. Creates a smoothed heatmap using Gaussian filtering
5. Samples the smoothed values at H3 hexagons (resolution 11) within Lausanne quartiers
6. Outputs GeoJSON with `hex_id` and `co2_smooth` properties

## Files

- `sparrow.ipynb` - Original Jupyter notebook (read-only reference)
- `process_sparrow.py` - Production processing script
- `Makefile` - Build automation
- `.env` - API key (create from `.env.example`)
- `sparrow_co2_2024.csv` - Cached API data (generated)
- `data/` - Downloaded source data (Quartiers statistiques shapefile)
- `outputs/` - Generated files

## Usage

### First Time Setup

1. Create `.env` file with your Sparrow API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your APIKEY
   ```

2. Process data (downloads quartiers automatically, uses cached CSV):
   ```bash
   make generate-data
   ```

### Regular Usage

Process using cached CO2 data:
```bash
make generate-data
```

Fetch fresh data from API (use sparingly):
```bash
make fetch-data
```

Download quartiers shapefile only:
```bash
make download-quartiers
```

Generate PMTiles from existing GeoJSON:
```bash
make generate-tiles
```

### From Root Directory

```bash
cd processing
make run-sparrow         # Uses cached data
make run-sparrow-fresh   # Fetches fresh API data
```

### Cleanup

Remove generated files (keeps cached CSV and source data):
```bash
make clean
```

Remove all generated files including cached data:
```bash
make clean-all
```

## Output

**Final output**: `outputs/lausanne_co2_emissions.geojson`
- 8850 H3 hexagons (resolution 11) covering Lausanne quartiers
- Properties: `hex_id`, `co2_smooth`
- CRS: EPSG:4326

**Intermediate outputs**:
- `outputs/h3_aggregated.geojson` - Aggregated H3 bins before smoothing
- `outputs/heatmap_smooth.npz` - Smoothed heatmap array (for debugging)

**PMTiles**: `outputs/lausanne_co2_emissions.pmtiles` (copied to frontend)

## Configuration

Edit constants in `process_sparrow.py`:
- `BBOX` - Bounding box for API queries (default: Lausanne area)
- `H3_RESOLUTION_AGGREGATE` - Resolution for initial binning (default: 10)
- `H3_RESOLUTION_SAMPLE` - Resolution for final hexagons (default: 11)
- `GAUSSIAN_SIGMA` - Smoothing parameter (default: 2)
- `HISTOGRAM_BINS` - Number of bins for heatmap (default: 300)
- `YEAR` - Year for data fetching (default: 2024)

## Data Source

- **Sparrow API**: https://api.sparrow.city/
- **Quartiers statistiques**: https://viageo.ch/donnee/telecharger/300517
