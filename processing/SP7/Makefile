.PHONY: generate-data generate-tiles clean

# Main target that processes data and generates tiles
generate-data:
	@echo "Generating data for SP7 Vehicle Tracking"
	python process.py
	$(MAKE) generate-tiles
	@echo "Data generated for SP7 Vehicle Tracking"

# Separate target for tile generation only
generate-tiles:
	@echo "Generating tiles for SP7 Vehicle Tracking"
	# Process the vehicle tracks GeoJSON into PMTiles
	@if [ -f vehicle_tracks.geojson ]; then \
		echo "Creating PMTiles for vehicle tracking"; \
		tippecanoe --force -zg\
			--read-parallel \
			--drop-smallest-as-needed \
			--no-line-simplification \
			--no-tiny-polygon-reduction --no-line-simplification --no-feature-limit --no-tile-size-limit --extend-zooms-if-still-dropping \
			-l vehicle_tracks \
			-o vehicle_tracks.pmtiles \
			vehicle_tracks.geojson; \
		cp vehicle_tracks.pmtiles ../../frontend/public/geodata/; \
		echo "PMTiles file created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: vehicle_tracks.geojson not found"; \
		exit 1; \
	fi
	@echo "Tiles generated for SP7 Vehicle Tracking"

clean:
	@echo "Cleaning up intermediate files..."
	rm -f vehicle_tracks_*.geojson 2>/dev/null || true
	@echo "Cleanup complete"