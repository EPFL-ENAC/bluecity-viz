.PHONY: help tiles clean

# Paths
GRAPH_DIR := data/graph
ELEVATION_DIR := data/elevation
FRONTEND_GEODATA_DIR := ../../frontend/public/geodata
BACKEND_DATA_DIR := ../../backend/data

# Files
DRIVE_GRAPHML := $(GRAPH_DIR)/lausanne_drive.graphml
DRIVE_GEOJSON := $(GRAPH_DIR)/lausanne_drive.geojson
DRIVE_PMTILES := $(GRAPH_DIR)/lausanne_drive.pmtiles
FRONTEND_PMTILES := $(FRONTEND_GEODATA_DIR)/lausanne_drive.pmtiles
BACKEND_GEOJSON := $(BACKEND_DATA_DIR)/lausanne.geojson

help:
	@echo "Traffic Analysis Processing"
	@echo "============================"
	@echo ""
	@echo "Available targets:"
	@echo "  make elevation   - Download elevation raster data from swisstopo"
	@echo "  make geojson     - Generate GeoJSON from GraphML files"
	@echo "  make tiles       - Generate PMTiles from GraphML files"
	@echo "  make install     - Copy generated files to frontend and backend"
	@echo "  make all         - Generate tiles and install to frontend"
	@echo "  make clean       - Remove generated PMTiles files"
	@echo "  make help        - Show this help message"
	@echo ""
	@echo "Requirements:"
	@echo "  - tippecanoe (brew install tippecanoe)"
	@echo "  - Python packages: osmnx, geopandas, shapely"

# Download elevation raster data
elevation:
	@echo "Downloading Swiss elevation data (swissALTI3D)..."
	@mkdir -p $(ELEVATION_DIR)
	uv run python download_elevation_data.py
	@echo "✓ Elevation data downloaded to $(ELEVATION_DIR)"

# Generate GeoJSON from GraphML
geojson: $(DRIVE_GEOJSON)

$(DRIVE_GEOJSON): $(DRIVE_GRAPHML)
	@echo "Generating GeoJSON from $(DRIVE_GRAPHML)..."
	@uv run python -c "from generate_graph_tiles import graphml_to_geojson; graphml_to_geojson('$(DRIVE_GRAPHML)', '$(DRIVE_GEOJSON)')"
	@echo "✓ GeoJSON generated: $(DRIVE_GEOJSON)"

# Generate PMTiles from GraphML
tiles: $(DRIVE_PMTILES)

$(DRIVE_PMTILES): $(DRIVE_GRAPHML) generate_graph_tiles.py
	@echo "Generating PMTiles from $(DRIVE_GRAPHML)..."
	uv run python generate_graph_tiles.py $(DRIVE_GRAPHML) $(DRIVE_PMTILES)
	@echo "✓ PMTiles generated: $(DRIVE_PMTILES)"

# Install files to frontend
install: tiles geojson
	@echo "Installing files to frontend and backend..."
	@mkdir -p $(FRONTEND_GEODATA_DIR)
	@mkdir -p $(BACKEND_DATA_DIR)
	@if [ -f $(DRIVE_PMTILES) ]; then \
		cp $(DRIVE_PMTILES) $(FRONTEND_PMTILES); \
		echo "✓ Copied PMTiles: $(FRONTEND_PMTILES)"; \
	fi
	@if [ -f $(DRIVE_GEOJSON) ]; then \
		cp $(DRIVE_GEOJSON) $(BACKEND_GEOJSON); \
		echo "✓ Copied GeoJSON: $(BACKEND_GEOJSON)"; \
	fi
	@echo "✓ Installation complete!"

# Generate and install in one step
all: tiles install

# Clean generated files
clean:
	@echo "Cleaning generated PMTiles and GeoJSON files..."
	@rm -f $(DRIVE_PMTILES) $(DRIVE_GEOJSON)
	@echo "✓ Clean complete"

# Clean backend files as well
clean-all: clean
	@echo "Cleaning frontend files..."
	@rm -f $(FRONTEND_PMTILES)
	@echo "✓ All files cleaned"
