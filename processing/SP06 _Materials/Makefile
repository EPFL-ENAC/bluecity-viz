.PHONY: generate-data generate-tiles clean

# Main target that processes data and generates tiles
generate-data:
	@echo "Generating data for SP06 Materials"
	# python process.py
	$(MAKE) convert-coordinates
	$(MAKE) generate-tiles
	@echo "Data generated for SP06 Materials"

convert-to-geojson-final-buildings:
	@echo "Exporting Final_buildings_Lausanne layer to GeoJSON"
	@mkdir -p geojson
	ogr2ogr -f GeoJSON -t_srs EPSG:4326 geojson/Final_buildings_Lausanne.geojson BlueCity_Demo2/BlueCity_Demo2.gdb Final_buildings_Lausanne
	@echo "Successfully exported Final_buildings_Lausanne to geojson/Final_buildings_Lausanne.geojson"


generate-buildings-pmtiles:
	@echo "Creating PMTiles for Final_buildings_Lausanne"
	@mkdir -p pmtiles
	tippecanoe --force -zg \
		--read-parallel \
		--no-simplification-of-shared-nodes \
		--drop-smallest-as-needed \
		--extend-zooms-if-still-dropping \
		-l buildings \
		-o pmtiles/buildings.pmtiles \
		geojson/Final_buildings_Lausanne.geojson
	cp pmtiles/buildings.pmtiles ../../frontend/public/geodata/
	@echo "PMTiles file created and copied to frontend/public/geodata/"

