.PHONY: help elevation network geojson tiles copy all clean clean-all

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GRAPH_DIR          := data/graph
ELEVATION_DIR      := data/elevation
FRONTEND_GEODATA   := ../../frontend/public/geodata
BACKEND_DATA       := ../../backend/data

# ---------------------------------------------------------------------------
# Derived file names
# ---------------------------------------------------------------------------

DRIVE_GRAPHML      := $(GRAPH_DIR)/lausanne_drive.graphml
DRIVE_GEOJSON      := $(GRAPH_DIR)/lausanne_drive.geojson
DRIVE_PMTILES      := $(GRAPH_DIR)/lausanne_drive.pmtiles

BACKEND_GRAPHML    := $(BACKEND_DATA)/lausanne.graphml
BACKEND_GEOJSON    := $(BACKEND_DATA)/lausanne.geojson
FRONTEND_PMTILES   := $(FRONTEND_GEODATA)/lausanne_drive.pmtiles

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:
	@echo "Traffic Analysis — data pipeline"
	@echo "================================="
	@echo ""
	@echo "Full pipeline (run once to bootstrap everything):"
	@echo "  make all"
	@echo ""
	@echo "Individual steps:"
	@echo "  make elevation   Download Swiss ALTI3D elevation rasters (optional)"
	@echo "  make network     Download OSM graph + enrich with speeds & elevation"
	@echo "  make geojson     Convert GraphML → GeoJSON  (backend edge geometry)"
	@echo "  make tiles       Convert GraphML → PMTiles  (frontend vector tiles)"
	@echo "  make copy        Copy outputs to backend/ and frontend/"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       Remove generated GeoJSON and PMTiles"
	@echo "  make clean-all   Also remove copies in backend/ and frontend/"
	@echo "  make help        Show this message"
	@echo ""
	@echo "Requirements: uv  +  tippecanoe"
	@echo "  macOS:  brew install tippecanoe"
	@echo "  Linux:  https://github.com/felt/tippecanoe#installation"

# ---------------------------------------------------------------------------
# Step 0 (optional) — Download Swiss ALTI3D elevation rasters
# ---------------------------------------------------------------------------

elevation:
	@echo "Downloading Swiss ALTI3D elevation rasters..."
	@mkdir -p $(ELEVATION_DIR)
	uv run python download_elevation_data.py
	@echo "✓ Elevation data saved to $(ELEVATION_DIR)/"

# ---------------------------------------------------------------------------
# Step 1 — Download OSM graph and enrich (speeds, travel times, elevation)
# ---------------------------------------------------------------------------
#
# Re-runs only when the output file is absent.  To force a fresh download,
# delete $(DRIVE_GRAPHML) first: rm data/graph/lausanne_drive.graphml
# ---------------------------------------------------------------------------

network: $(DRIVE_GRAPHML)

$(DRIVE_GRAPHML): lausanne_network.py
	@echo "Building Lausanne road network..."
	@mkdir -p $(GRAPH_DIR)
	uv run python lausanne_network.py --output $(DRIVE_GRAPHML)
	@echo "✓ Network saved to $(DRIVE_GRAPHML)"

# ---------------------------------------------------------------------------
# Step 2a — GraphML → GeoJSON  (backend edge geometry)
# ---------------------------------------------------------------------------

geojson: $(DRIVE_GEOJSON)

$(DRIVE_GEOJSON): $(DRIVE_GRAPHML) generate_graph_tiles.py
	@echo "Generating GeoJSON from $(DRIVE_GRAPHML)..."
	uv run python generate_graph_tiles.py $(DRIVE_GRAPHML) --geojson $(DRIVE_GEOJSON)
	@echo "✓ GeoJSON saved to $(DRIVE_GEOJSON)"

# ---------------------------------------------------------------------------
# Step 2b — GraphML → PMTiles  (frontend vector tiles)
# ---------------------------------------------------------------------------

tiles: $(DRIVE_PMTILES)

$(DRIVE_PMTILES): $(DRIVE_GRAPHML) generate_graph_tiles.py
	@echo "Generating PMTiles from $(DRIVE_GRAPHML)..."
	uv run python generate_graph_tiles.py $(DRIVE_GRAPHML) $(DRIVE_PMTILES)
	@echo "✓ PMTiles saved to $(DRIVE_PMTILES)"

# ---------------------------------------------------------------------------
# Step 3 — Copy outputs to backend/ and frontend/
# ---------------------------------------------------------------------------

copy: tiles geojson
	@echo "Copying files to backend/ and frontend/..."
	@mkdir -p $(FRONTEND_GEODATA) $(BACKEND_DATA)
	@cp $(DRIVE_PMTILES)  $(FRONTEND_PMTILES)
	@echo "  ✓ $(FRONTEND_PMTILES)"
	@cp $(DRIVE_GEOJSON)  $(BACKEND_GEOJSON)
	@echo "  ✓ $(BACKEND_GEOJSON)"
	@cp $(DRIVE_GRAPHML)  $(BACKEND_GRAPHML)
	@echo "  ✓ $(BACKEND_GRAPHML)"
	@echo "✓ Copy complete"

# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
#
# Elevation is intentionally not included here because it requires a large
# download (~2 GB) that is optional.  Run 'make elevation' separately before
# 'make all' if you want grade data in the graph.
# ---------------------------------------------------------------------------

all: network tiles copy

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

clean:
	@echo "Removing generated files in $(GRAPH_DIR)/..."
	@rm -f $(DRIVE_PMTILES) $(DRIVE_GEOJSON)
	@echo "✓ Clean complete"

clean-all: clean
	@echo "Removing copied files from backend/ and frontend/..."
	@rm -f $(FRONTEND_PMTILES) $(BACKEND_GEOJSON) $(BACKEND_GRAPHML)
	@echo "✓ All clean"
