# Sparrow Emissions Processing

This directory contains scripts for processing multi-pollutant emissions data from the Sparrow API with multi-level temporal aggregation.

## Overview

The processing pipeline:
1. Downloads emissions data from Sparrow API for multiple years and pollutants (or uses cached data)
2. Aggregates point data into H3 hexagonal bins (resolution 10)
3. Creates three levels of temporal aggregation:
   - **Level 1**: Overall average per hexagon per filter
   - **Level 2**: Monthly averages per hexagon per filter
   - **Level 3**: Time-of-day averages per hexagon per filter
4. Removes outliers using IQR method for each aggregation level
5. Creates smoothed heatmaps using Gaussian filtering (85 heatmaps total)
6. Samples the smoothed values at H3 hexagons (resolution 11) within Lausanne boundary
7. Outputs nested GeoJSON with multi-level temporal data

## Files

- `sparrow.ipynb` - Original Jupyter notebook (read-only reference)
- `process_sparrow.py` - Production processing script with multi-level aggregation
- `Makefile` - Build automation
- `.env` - API key (create from `.env.example`)
- `data/sparrow_{years}_{filters}.csv` - Cached API data (auto-generated)
- `data/` - Downloaded source data
- `outputs/` - Generated files

## Usage

### First Time Setup

1. Create `.env` file with your Sparrow API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your APIKEY
   ```

2. Process data with default parameters (all years 2023-2026, all filters):
   ```bash
   make generate-data
   ```

### Command-Line Arguments

The script supports flexible parameter selection:

```bash
# Default: all years (2023-2026), all filters (co2, no2, pm25, o3, temperature)
uv run python process_sparrow.py --fetch-data

# Single year and filter
uv run python process_sparrow.py --years 2024 --filters co2

# Multiple years and filters
uv run python process_sparrow.py --years 2023,2024 --filters co2,no2,pm25

# Use cached data (faster, no API calls)
uv run python process_sparrow.py --years 2024 --filters co2
```

**Arguments:**
- `--years YEARS` - Comma-separated years (e.g., `2023,2024,2025`)
  - Default: `2023-2026` (current year)
  - Validated: Must be >= 2023 and <= current year
- `--filters FILTERS` - Comma-separated filters (e.g., `co2,no2`)
  - Allowed: `co2`, `no2`, `pm25`, `o3`, `temperature`
  - Default: All filters
- `--fetch-data` - Fetch fresh data from API (otherwise uses cache)

### Regular Usage

#### Using Makefile Targets

**Basic commands:**
```bash
make generate-data       # Process using cached data (default: all years/filters)
make fetch-data          # Fetch fresh data from API (use sparingly)
make generate-tiles      # Generate PMTiles from existing GeoJSON
```

**With custom parameters:**
```bash
make generate-data YEARS=2024 FILTERS=co2,no2
make fetch-data YEARS=2023,2024 FILTERS=temperature
```

**Utility targets:**
```bash
make show-config         # Show current configuration and examples
make validate-years      # Test year validation
make validate-filters    # Test filter validation
make help                # Show all available targets
```

### From Root Directory

```bash
cd processing
make run-sparrow         # Uses cached data (default: all years/filters)
make run-sparrow-fresh   # Fetches fresh API data (default: all years/filters)
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

## Output Structure

### Final Output
**File**: `outputs/lausanne_emissions_multilevel.geojson`

Each hexagon contains nested properties with three levels of aggregation:

```json
{
  "hex_id": "8b1234567890abc",
  "geometry": {...},
  "co2": {
    "overall": 123.45,
    "monthly": {
      "1": 120.1,
      "2": 118.3,
      ...
      "12": 125.7
    },
    "time_of_day": {
      "night": 110.2,
      "morning_commute": 135.8,
      "work_hours": 140.1,
      "late_afternoon_commute": 145.3
    }
  },
  "no2": {...},
  "pm25": {...},
  "o3": {...},
  "temperature": {...}
}
```

**Properties:**
- ~8850 H3 hexagons (resolution 11) covering Lausanne area
- Five pollutant filters with nested temporal data
- CRS: EPSG:4326

### Time Period Definitions

**Level 3** aggregates data into four time periods:
- **Night**: 20:00-05:59 (hours 20-23, 0-5)
- **Morning commute**: 07:00-08:59 (hours 7-8)
- **Work hours**: 10:00-15:59 (hours 10-15)
- **Late afternoon commute**: 17:00-18:59 (hours 17-18)

### Intermediate Outputs

- `outputs/level1_aggregated.geojson` - Overall aggregation
- `outputs/level2_aggregated.geojson` - Monthly aggregation
- `outputs/level3_aggregated.geojson` - Time-of-day aggregation

### PMTiles
`outputs/lausanne_emissions_multilevel.pmtiles` (copied to frontend)

## Configuration

Constants in `process_sparrow.py`:

**Spatial Parameters:**
- `BBOX` - Bounding box for API queries: `(46.4, 6.5, 46.6, 6.8)` (Lausanne area)
- `H3_RESOLUTION_AGGREGATE` - Resolution for initial binning: `10`
- `H3_RESOLUTION_SAMPLE` - Resolution for final hexagons: `11`
- `LAUSANNE_HULL_WKT` - Lausanne boundary polygon (WKT format)

**Processing Parameters:**
- `GAUSSIAN_SIGMA` - Smoothing parameter: `2`
- `HISTOGRAM_BINS` - Number of bins for heatmap: `300`

**Data Parameters:**
- `ALLOWED_FILTERS` - Valid filter names: `['co2', 'no2', 'pm25', 'o3', 'temperature']`
- `DEFAULT_YEARS` - Default year range: `2023` to current year
- `TIME_PERIODS` - Hour definitions for Level 3 aggregation

## Performance

For default configuration (4 years × 5 filters × 12 months):
- **API requests**: 240 total (with progress logging)
- **Heatmaps created**: 85 (5 filters × [1 overall + 12 monthly + 4 time-of-day])
- **Estimated runtime**:
  - Fresh data fetch: 20-30 minutes
  - Heatmap generation: 5-10 minutes
  - **Total**: ~30-40 minutes

**Caching Strategy:**
Cache filenames reflect the data they contain:
- Format: `sparrow_{year_range}_{filters}.csv`
- Example: `sparrow_2023-2026_co2-no2-o3-pm25-temperature.csv`

## Data Sources

- **Sparrow API**: https://api.sparrow.city/
  - Available filters: CO2, NO2, PM2.5, O3, temperature
  - Data availability: 2023 onwards
  - Coverage: Lausanne metropolitan area

## Technical Details

**Aggregation Workflow:**
1. Raw API data → Point GeoDataFrame with timestamps
2. Add temporal columns (hour, month, time_period)
3. Create H3 bins at resolution 10
4. Generate three aggregation levels with separate geometries
5. Remove outliers using IQR method (per level)
6. Create smoothed heatmaps using Gaussian filtering (per level)
7. Sample at resolution 11 hexagons within Lausanne hull
8. Build nested GeoJSON structure

**Smoothing:**
- Uses Gaussian filter with sigma=2
- Applied in EPSG:3857 projection for accurate distance-based smoothing
- Separate heatmap for each filter/temporal combination

**Boundary:**
- Uses `LAUSANNE_HULL_WKT` polygon instead of quartiers shapefile
- More consistent and reproducible boundary definition
- No external shapefile dependency
