.PHONY: generate-data generate-tiles clean

# Main target that processes data and generates tiles
generate-data:
	@echo "Generating data for SP06 Materials"
	# python process.py
	$(MAKE) convert-coordinates
	$(MAKE) generate-tiles
	@echo "Data generated for SP06 Materials"

# Target to convert from Swiss coordinates (EPSG:2056) to WGS84 (EPSG:4326)
convert-coordinates:
	@echo "Converting buildings from EPSG:2056 to EPSG:4326"
	@if [ -f buildings.geojson ]; then \
		echo "Running coordinate conversion..."; \
		ogr2ogr -f GeoJSON -t_srs EPSG:4326 buildings.geojson '1 - (RegBL Building attributes) vd/buildings.geojson' \
		echo "Conversion complete: buildings.geojson"; \
	else \
		echo "Error: buildings.geojson not found"; \
		exit 1; \
	fi

# Separate target for tile generation only
generate-tiles:
	@echo "Generating tiles for SP06 Materials"
	# Process the waste routes GeoJSON into PMTiles
	@if [ -f buildings.geojson ]; then \
		echo "Creating PMTiles for waste collection routes"; \
		tippecanoe --force -zg \
			--read-parallel \
			--no-simplification-of-shared-nodes \
			--drop-smallest-as-needed \
			--no-clipping --no-duplication \
			-o buildings.pmtiles \
			buildings.geojson; \
		cp buildings.pmtiles ../../frontend/public/geodata/; \
		echo "PMTiles file created and copied to frontend/public/geodata/"; \
	else \
		echo "Error: buildings.geojson not found"; \
		exit 1; \
	fi
	@echo "Tiles generated for SP06 Materials"

