.PHONY: generate-data fetch-data generate-tiles clean clean-all help

# Default parameters (can be overridden)
YEARS ?=
FILTERS ?=

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Process using cached data (default: all years 2023-2026, all filters)
generate-data: ## Process Sparrow emissions data (uses cached CSV)
	@echo "Processing Sparrow emissions data from cache..."
	@echo "Years: $(if $(YEARS),$(YEARS),2023-2026 (default))"
	@echo "Filters: $(if $(FILTERS),$(FILTERS),all (default))"
	@mkdir -p outputs data
	uv run python process_sparrow.py $(if $(YEARS),--years $(YEARS)) $(if $(FILTERS),--filters $(FILTERS))
	$(MAKE) generate-tiles
	@echo "Data processing complete"

# Fetch fresh data from API
fetch-data: ## Fetch fresh data from Sparrow API and process
	@echo "Fetching fresh data from Sparrow API..."
	@echo "Years: $(if $(YEARS),$(YEARS),2023-2026 (default))"
	@echo "Filters: $(if $(FILTERS),$(FILTERS),all (default))"
	@mkdir -p outputs data
	uv run python process_sparrow.py --fetch-data $(if $(YEARS),--years $(YEARS)) $(if $(FILTERS),--filters $(FILTERS))
	$(MAKE) generate-tiles
	@echo "Data fetching and processing complete"

# Generate PMTiles from processed GeoJSON
generate-tiles: ## Generate PMTiles from processed GeoJSON
	@echo "Generating tiles for Sparrow emissions..."
	@if [ -f outputs/lausanne_emissions_multilevel.geojson ]; then \
		echo "Creating PMTiles for multi-level emissions data"; \
		tippecanoe --force -zg \
			--read-parallel \
			--drop-densest-as-needed \
			--extend-zooms-if-still-dropping \
			-l emissions_multilevel \
			-o outputs/lausanne_emissions_multilevel.pmtiles \
			outputs/lausanne_emissions_multilevel.geojson; \
		cp outputs/lausanne_emissions_multilevel.pmtiles ../../frontend/public/geodata/; \
		echo "PMTiles created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: outputs/lausanne_emissions_multilevel.geojson not found"; \
		echo "Run 'make generate-data' or 'make fetch-data' first"; \
		exit 1; \
	fi
	@echo "Tiles generation complete"

clean: ## Clean generated files (keeps cached CSV and source data)
	@echo "Cleaning generated files..."
	rm -rf outputs/
	@echo "Cleanup complete (kept: data/*.csv, data/)"

clean-all: clean ## Clean all generated files including cached data
	@echo "Cleaning all generated and cached files..."
	rm -f data/sparrow_*.csv
	@echo "Complete cleanup done (kept: data/ directory for shapefiles)"

# Development helpers
validate-years: ## Test year validation
	@echo "Testing invalid year (too early)..."
	@uv run python process_sparrow.py --years 2022 || true
	@echo ""
	@echo "Testing invalid year (future)..."
	@uv run python process_sparrow.py --years 2027 || true

validate-filters: ## Test filter validation
	@echo "Testing invalid filter..."
	@uv run python process_sparrow.py --filters pollution || true

show-config: ## Show current configuration
	@echo "Sparrow Emissions Processing Configuration"
	@echo "=========================================="
	@echo "Default years: 2023-$(shell date +%Y)"
	@echo "Allowed filters: co2, no2, pm25, o3, temperature"
	@echo "H3 aggregate resolution: 10"
	@echo "H3 sample resolution: 11"
	@echo "Gaussian sigma: 2"
	@echo "Histogram bins: 300"
	@echo ""
	@echo "Usage examples:"
	@echo "  make fetch-data                    # All years, all filters"
	@echo "  make fetch-data YEARS=2024         # Single year, all filters"
	@echo "  make fetch-data FILTERS=co2,no2    # All years, specific filters"
	@echo "  make fetch-data YEARS=2024 FILTERS=co2  # Single year and filter"
