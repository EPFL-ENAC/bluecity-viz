.PHONY: generate-data clean

generate-data:
	@echo "Generating data"
	python process.py
		
	$(MAKE) generate-period-tiles
		
	@echo "Data generated"

# Generate PMTiles for each period GeoJSON file
generate-period-tiles:
	@echo "Generating PMTiles for lausanne_migration_2011_2023"
	tippecanoe --force -zg \
		--read-parallel \
		--extend-zooms-if-still-dropping \
		--no-tile-size-limit \
		-l lausanne_migration \
		-o lausanne_migration_2011_2023_2.pmtiles \
		lausanne_migration_2011_2023.geojson
	echo "Created lausanne_migration_2011_2023_2.pmtiles"; \
	cp lausanne_migration_2011_2023_2.pmtiles ../../frontend/public/geodata/; \
		
	@echo "All period PMTiles generated and copied to frontend"


clean:
	rm -f *.pmtiles