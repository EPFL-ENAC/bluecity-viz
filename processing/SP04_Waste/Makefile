.PHONY: generate-data generate-tiles clean

# Main target that processes data and generates tiles
generate-data:
	@echo "Generating data for SP04 Waste"
	python process.py
	$(MAKE) generate-tiles
	@echo "Data generated for SP04 Waste"

# Separate target for tile generation only
generate-tiles:
	@echo "Generating tiles for SP04 Waste"
	# Process the waste routes GeoJSON into PMTiles
	@if [ -f lausanne_waste_routes.geojson ]; then \
		echo "Creating PMTiles for waste collection routes"; \
		tippecanoe --force -zg \
			--read-parallel \
			--no-simplification-of-shared-nodes \
			--drop-smallest-as-needed \
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

clean:
	@echo "Cleaning up intermediate files..."
	rm -f lausanne_waste_routes_combined_raw.geojson 2>/dev/null || true
	@echo "Cleanup complete"