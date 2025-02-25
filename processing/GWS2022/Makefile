generate-data:
	@echo "Generating data"
	python process.py
	tippecanoe --force -zg --read-parallel --coalesce-densest-as-needed --extend-zooms-if-still-dropping --accumulate-attribute=GTOT:mean -U 2 -o gws_grid.pmtiles gws_grid_wgs84.geojson 
	cp gws_grid.pmtiles ../../frontend/public/geodata/
	@echo "Data generated"