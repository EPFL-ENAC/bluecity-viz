generate-data:
	@echo "Generating data"
	python process.py
	tippecanoe --force -zg --read-parallel  --coalesce-densest-as-needed --extend-zooms-if-still-dropping --accumulate-attribute=B22BTOT:mean -U 2 -o statpop_grid.pmtiles statpop_grid_wgs84.geojson 
	cp statpop_grid.pmtiles ../../frontend/public/geodata/
	@echo "Data generated"