# Traffic Analysis Data Processing

This directory contains tools for processing road network data for the traffic analysis feature.

## Overview

The traffic analysis feature requires:

1. **GraphML file**: Road network graph (lausanne_drive.graphml)
2. **PMTiles file**: Optimized vector tiles for web visualization (lausanne_drive.pmtiles)

The PMTiles file is placed in the frontend's `public/geodata/` folder and served as a static asset, just like the other map layers.

## Quick Start

```bash
# Install dependencies
pip install osmnx geopandas shapely
brew install tippecanoe  # macOS
# or apt-get install tippecanoe  # Linux

# Generate PMTiles and copy to backend
make all

# Or step by step:
make tiles    # Generate PMTiles from GraphML
make install  # Copy files to backend
```

## Files

- `generate_graph_tiles.py` - Python script to convert GraphML → PMTiles
- `Makefile` - Build automation for tile generation
- `data/graph/lausanne_drive.graphml` - Source road network (OSM data)
- `data/graph/lausanne_drive.pmtiles` - Generated vector tiles (output)

## Makefile Targets

```bash
make help      # Show all available commands
make tiles     # Generate PMTiles from GraphML
make install   # Copy PMTiles to frontend/public/geodata/
make all       # Generate tiles and install (default)
make clean     # Remove generated PMTiles
make clean-all # Remove generated and frontend files
```

## Manual Usage

If you need more control, you can run the script directly:

```bash
python generate_graph_tiles.py <input.graphml> [output.pmtiles]

# Examples:
python generate_graph_tiles.py data/graph/lausanne_drive.graphml
python generate_graph_tiles.py data/graph/lausanne_bike.graphml data/graph/lausanne_bike.pmtiles
```

## How It Works

1. **Load GraphML**: Reads the OSMnx graph file
2. **Add Attributes**: Ensures speed and travel time attributes exist
3. **Convert to GeoJSON**: Creates a temporary GeoJSON with all edges
4. **Generate PMTiles**: Uses tippecanoe to create optimized vector tiles
   - Zoom levels: 6-20
   - Layer name: `graph_edges`
   - Automatic simplification at lower zoom levels

## Output Structure

The PMTiles file contains a vector tile layer called `graph_edges` with properties:

- `u`, `v` - Node IDs (for edge identification)
- `name` - Street name
- `highway` - Highway type (motorway, primary, residential, etc.)
- `speed_kph` - Speed limit in km/h
- `length` - Edge length in meters
- `travel_time` - Travel time in seconds

## Performance Benefits

| Format  | Size   | Load Time | Memory |
| ------- | ------ | --------- | ------ |
| GraphML | ~15 MB | N/A       | N/A    |
| GeoJSON | ~50 MB | 2-5s      | 100 MB |
| PMTiles | ~8 MB  | <500ms    | 10 MB  |

PMTiles provides:

- ✅ 85% size reduction vs GeoJSON
- ✅ Viewport-based loading (only visible tiles)
- ✅ Automatic browser caching
- ✅ Progressive zoom levels

## Dependencies

### Required

- **Python**: osmnx, geopandas, shapely
- **tippecanoe**: Vector tile generator ([installation guide](https://github.com/felt/tippecanoe#installation))

### Installation

```bash
# Python packages
pip install osmnx geopandas shapely

# Tippecanoe (macOS)
brew install tippecanoe

# Tippecanoe (Ubuntu/Debian)
sudo apt-get install -y tippecanoe

# Tippecanoe (from source)
git clone https://github.com/felt/tippecanoe.git
cd tippecanoe
make -j
sudo make install
```

## Troubleshooting

### "tippecanoe: command not found"

Install tippecanoe (see Dependencies above)

### "Graph file not found"

Make sure you're in the `processing/traffic-analysis/` directory and the GraphML file exists in `data/graph/`

### "Permission denied" when running make install

The backend directory needs write permissions. Check that `../../backend/data/` is writable.

## Development

To modify the tile generation process, edit `generate_graph_tiles.py`. Key parameters in the tippecanoe command:

- `-Z`, `-z`: Min/max zoom levels
- `-l`: Layer name
- `-r1`: Simplification rate
- `--drop-densest-as-needed`: Automatic feature reduction at lower zooms

## Next Steps

After running `make install`, the PMTiles file will be available at:

```
/geodata/lausanne_drive.pmtiles
```

The frontend loads this directly as a static asset from the public folder, just like the other geodata layers.
