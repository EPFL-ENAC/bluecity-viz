.PHONY: generate-data fetch-data download-quartiers generate-tiles clean clean-all help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Download Quartiers statistiques shapefile from viageo.ch
download-quartiers: ## Download Quartiers statistiques shapefile
	@echo "Downloading Quartiers statistiques from viageo.ch..."
	@mkdir -p data
	@if [ ! -f "data/Quartiers statistiques.shp" ]; then \
		curl -L -o data/quartiers.zip \
		  "https://viageo.ch/donnee/telecharger/300517"; \
		cd data && unzip -o quartiers.zip && rm quartiers.zip; \
		echo "Quartiers statistiques downloaded successfully"; \
	else \
		echo "Quartiers statistiques already exists"; \
	fi

# Process using cached data (default)
generate-data: download-quartiers ## Process Sparrow CO2 data (uses cached CSV)
	@echo "Processing Sparrow CO2 data from cache..."
	@mkdir -p outputs
	uv run python process_sparrow.py
	$(MAKE) generate-tiles
	@echo "Data processing complete"

# Fetch fresh data from API
fetch-data: download-quartiers ## Fetch fresh data from Sparrow API and process
	@echo "Fetching fresh data from Sparrow API..."
	@mkdir -p outputs
	uv run python process_sparrow.py --fetch-data
	$(MAKE) generate-tiles
	@echo "Data fetching and processing complete"

# Generate PMTiles from processed GeoJSON
generate-tiles: ## Generate PMTiles from processed GeoJSON
	@echo "Generating tiles for Sparrow CO2 emissions..."
	@if [ -f outputs/lausanne_co2_emissions.geojson ]; then \
		echo "Creating PMTiles for CO2 emissions"; \
		tippecanoe --force -zg \
			--read-parallel \
			--drop-densest-as-needed \
			--extend-zooms-if-still-dropping \
			-l co2_emissions \
			-o outputs/lausanne_co2_emissions.pmtiles \
			outputs/lausanne_co2_emissions.geojson; \
		cp outputs/lausanne_co2_emissions.pmtiles ../../frontend/public/geodata/; \
		echo "PMTiles created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: outputs/lausanne_co2_emissions.geojson not found"; \
		exit 1; \
	fi
	@echo "Tiles generation complete"

clean: ## Clean generated files (keeps cached CSV and source data)
	@echo "Cleaning generated files..."
	rm -rf outputs/
	@echo "Cleanup complete (kept: sparrow_co2_2024.csv, data/)"

clean-all: clean ## Clean all generated files including cached data
	@echo "Cleaning all generated and cached files..."
	rm -f sparrow_co2_2024.csv
	rm -rf data/
	@echo "Complete cleanup done"
