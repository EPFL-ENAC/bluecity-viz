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
		
	@echo "Data generated for SP03 Nature"