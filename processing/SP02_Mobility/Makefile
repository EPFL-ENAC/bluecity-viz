generate-data:
	@echo "Generating data for SP02 Mobility"
	tippecanoe --force -zg --read-parallel -U 2 -o accessibility_20250220_wgs84.pmtiles accessibility_20250220_wgs84.json
	cp accessibility_20250220_wgs84.pmtiles ../../frontend/public/geodata/
	@echo "Data generated for SPO2 Mobility" 