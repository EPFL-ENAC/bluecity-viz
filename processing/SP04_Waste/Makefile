.PHONY: generate-data generate-tiles generate-cluster-data generate-cluster-tiles clean

# Main target that processes data and generates tiles
generate-data:
	@echo "Generating data for SP04 Waste"
	python process.py
	$(MAKE) generate-tiles
	@echo "Data generated for SP04 Waste"

# Process cluster data and generate tiles
generate-cluster-data:
	@echo "Generating cluster data for SP04 Waste"
	python process_centroids.py
	$(MAKE) generate-cluster-tiles
	@echo "Cluster data generated for SP04 Waste"

# Separate target for route tile generation only
generate-tiles:
	@echo "Generating tiles for SP04 Waste"
	# Process the waste routes GeoJSON into PMTiles
	@if [ -f lausanne_waste_routes.geojson ]; then \
		echo "Creating PMTiles for waste collection routes"; \
		tippecanoe --force -zg \
			--read-parallel \
			--no-simplification-of-shared-nodes \
			--drop-densest-as-needed \
			--extend-zooms-if-still-dropping \
			--no-clipping --no-duplication \
			-l waste_routes \
			-o lausanne_waste_routes.pmtiles \
			lausanne_waste_routes.geojson; \
		cp lausanne_waste_routes.pmtiles ../../frontend/public/geodata/; \
		echo "PMTiles file created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: lausanne_waste_routes.geojson not found"; \
		exit 1; \
	fi
	@echo "Tiles generated for SP04 Waste"

# Generate tiles for cluster data
generate-cluster-tiles:
	@echo "Generating tiles for SP04 Waste Clusters"
	# Process the waste centroids GeoJSON into PMTiles
	@if [ -f lausanne_waste_centroids.geojson ]; then \
		echo "Creating PMTiles for waste collection centroids"; \
		tippecanoe --force -zg \
			--read-parallel \
			--no-simplification-of-shared-nodes \
			--no-clipping --no-duplication \
			-l waste_centroids \
			-o lausanne_waste_centroids.pmtiles \
			lausanne_waste_centroids.geojson; \
		cp lausanne_waste_centroids.pmtiles ../../frontend/public/geodata/; \
		echo "Centroids PMTiles file created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: lausanne_waste_centroids.geojson not found"; \
		exit 1; \
	fi
	@echo "Cluster tiles generated for SP04 Waste"

# All-in-one target to generate both data types
generate-all: generate-data generate-cluster-data

clean:
	@echo "Cleaning up intermediate files..."
	rm -f lausanne_waste_routes_combined_raw.geojson 2>/dev/null || true
	rm -f lausanne_waste_centroids.geojson 2>/dev/null || true
	rm -f lausanne_waste_routes.pmtiles 2>/dev/null || true
	rm -f lausanne_waste_centroids.pmtiles 2>/dev/null || true
	@echo "Cleanup complete"