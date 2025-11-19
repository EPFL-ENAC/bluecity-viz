.PHONY: help tiles clean

# Paths
GRAPH_DIR := data/graph
FRONTEND_GEODATA_DIR := ../../frontend/public/geodata

# Files
DRIVE_GRAPHML := $(GRAPH_DIR)/lausanne_drive.graphml
DRIVE_PMTILES := $(GRAPH_DIR)/lausanne_drive.pmtiles
FRONTEND_PMTILES := $(FRONTEND_GEODATA_DIR)/lausanne_drive.pmtiles

help:
	@echo "Traffic Analysis Processing"
	@echo "============================"
	@echo ""
	@echo "Available targets:"
	@echo "  make tiles       - Generate PMTiles from GraphML files"
	@echo "  make install     - Copy generated PMTiles to frontend geodata folder"
	@echo "  make all         - Generate tiles and install to frontend"
	@echo "  make clean       - Remove generated PMTiles files"
	@echo "  make help        - Show this help message"
	@echo ""
	@echo "Requirements:"
	@echo "  - tippecanoe (brew install tippecanoe)"
	@echo "  - Python packages: osmnx, geopandas, shapely"

# Generate PMTiles from GraphML
tiles: $(DRIVE_PMTILES)

$(DRIVE_PMTILES): $(DRIVE_GRAPHML) generate_graph_tiles.py
	@echo "Generating PMTiles from $(DRIVE_GRAPHML)..."
	python generate_graph_tiles.py $(DRIVE_GRAPHML) $(DRIVE_PMTILES)
	@echo "✓ PMTiles generated: $(DRIVE_PMTILES)"

# Install files to frontend
install: tiles
	@echo "Installing PMTiles to frontend geodata folder..."
	@mkdir -p $(FRONTEND_GEODATA_DIR)
	@if [ -f $(DRIVE_PMTILES) ]; then \
		cp $(DRIVE_PMTILES) $(FRONTEND_PMTILES); \
		echo "✓ Copied PMTiles: $(FRONTEND_PMTILES)"; \
	fi
	@echo "✓ Installation complete!"

# Generate and install in one step
all: tiles install

# Clean generated files
clean:
	@echo "Cleaning generated PMTiles files..."
	@rm -f $(DRIVE_PMTILES)
	@echo "✓ Clean complete"

# Clean backend files as well
clean-all: clean
	@echo "Cleaning frontend files..."
	@rm -f $(FRONTEND_PMTILES)
	@echo "✓ All files cleaned"
