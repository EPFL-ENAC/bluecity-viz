generate-data:
	@echo "Generating data for SP02 Mobility"
	tippecanoe --force -zg \
		--no-tile-size-limit \
		-o accessibility_20250220.pmtiles accessibility_20250220_wgs84.json
	cp accessibility_20250220.pmtiles ../../frontend/public/geodata/
	@echo "Data generated for SP02 Mobility"