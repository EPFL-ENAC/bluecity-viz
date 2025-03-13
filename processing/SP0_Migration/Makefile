.PHONY: generate-data clean

generate-data:
	@echo "Generating data"
	python process.py
		
	$(MAKE) generate-period-tiles
		
	@echo "Data generated"

# Generate PMTiles for each period GeoJSON file
generate-period-tiles:
	@echo "Generating PMTiles for period data"
	@mkdir -p period_data
	@for file in $$(find period_data -name "*.geojson"); do \
		basename=$$(basename $$file .geojson); \
		echo "Processing $$basename"; \
		tippecanoe --force -zg \
			--read-parallel \
			--drop-densest-as-needed \
			--extend-zooms-if-still-dropping \
			-l lausanne_migration \
			-o period_data/$$basename.pmtiles \
			$$file; \
		echo "Created period_data/$$basename.pmtiles"; \
		cp period_data/$$basename.pmtiles ../../frontend/public/geodata/; \
	done
		
	@echo "All period PMTiles generated and copied to frontend"


clean:
	rm -f *.pmtiles