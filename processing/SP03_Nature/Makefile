.PHONY: generate-data

generate-data:
	@echo "Generating data for SP03 Nature"
	python process.py
		
	# Process AQI data
	@if [ -f lausanne_aqi_yearly.geojson ]; then \
		echo "Creating PMTiles for AQI yearly data"; \
		tippecanoe --force -zg --read-parallel -U 2 -o lausanne_aqi_yearly.pmtiles lausanne_aqi_yearly.geojson; \
		cp lausanne_aqi_yearly.pmtiles ../../frontend/public/geodata/; \
	fi
		
	@if [ -f lausanne_aqi_monthly.geojson ]; then \
		echo "Creating PMTiles for AQI monthly data"; \
		tippecanoe --force -zg --read-parallel -U 2 -o lausanne_aqi_monthly.pmtiles lausanne_aqi_monthly.geojson; \
		cp lausanne_aqi_monthly.pmtiles ../../frontend/public/geodata/; \
	fi
		
	# Process temperature data
	@if [ -f lausanne_temperature_yearly.geojson ]; then \
		echo "Creating PMTiles for temperature yearly data"; \
		tippecanoe --force -zg --read-parallel -U 2 -o lausanne_temperature_yearly.pmtiles lausanne_temperature_yearly.geojson; \
		cp lausanne_temperature_yearly.pmtiles ../../frontend/public/geodata/; \
	fi
		
	@if [ -f lausanne_temperature_monthly.geojson ]; then \
		echo "Creating PMTiles for temperature monthly data"; \
		tippecanoe --force -zg --read-parallel -U 2 -o lausanne_temperature_monthly.pmtiles lausanne_temperature_monthly.geojson; \
		cp lausanne_temperature_monthly.pmtiles ../../frontend/public/geodata/; \
	fi
		
	# Process species observation data
	@if [ -f lausanne_species.geojson ]; then \
		echo "Creating PMTiles for species observation data"; \
		tippecanoe --force -zg --read-parallel \
			--no-simplification-of-shared-nodes \
			--extend-zooms-if-still-dropping \
			--drop-densest-as-needed \
			-l species_observations \
			-o lausanne_species.pmtiles lausanne_species.geojson; \
		cp lausanne_species.pmtiles ../../frontend/public/geodata/; \
		echo "Species observation PMTiles file created and copied to frontend/public/geodata/"; \
	else \
		echo "Warning: lausanne_species.geojson not found"; \
	fi
		
	@echo "Data generated for SP03 Nature"

clean:
	@echo "Cleaning up intermediate files..."
	rm -f lausanne_aqi_*.geojson 2>/dev/null || true
	rm -f lausanne_temperature_*.geojson 2>/dev/null || true
	rm -f lausanne_species.geojson 2>/dev/null || true
	rm -f *.pmtiles 2>/dev/null || true
	@echo "Cleanup complete"