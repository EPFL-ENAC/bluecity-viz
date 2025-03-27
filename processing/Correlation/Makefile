.PHONY: all clean generate-correlations

all: generate-correlations



# Generate PMTiles for correlation datasets
generate-correlations:
	@echo "Generating PMTiles for correlations..."
		
	# Combine waste-pop correlations
	@echo "Combining waste-pop correlations..."
	@python3 combine_geojson.py --pattern "corr_waste_pop_*.geojson" --output "combined_waste_pop.geojson"
		
	# Combine pop-access correlations
	@echo "Combining pop-access correlations..."
	@python3 combine_geojson.py --pattern "corr_pop_access_*.geojson" --output "combined_pop_access.geojson"
		
	# Combine waste-access correlations
	@echo "Combining waste-access correlations..."
	@python3 combine_geojson.py --pattern "corr_waste_access_*.geojson" --output "combined_waste_access.geojson"
		
	# Process waste-pop correlations
	@echo "Processing waste-pop correlations..."
	@tippecanoe --force -zg --read-parallel -o lausanne_corr_waste_pop.pmtiles \
		-l corr_waste_pop \
		--drop-densest-as-needed \
		--extend-zooms-if-still-dropping \
		combined_waste_pop.geojson
	@cp lausanne_corr_waste_pop.pmtiles ../../frontend/public/geodata/
		
	# Process pop-access correlations
	@echo "Processing pop-access correlations..."
	@tippecanoe --force -zg --read-parallel -o lausanne_corr_pop_access.pmtiles \
		-l corr_pop_access \
		--drop-densest-as-needed \
		--extend-zooms-if-still-dropping \
		combined_pop_access.geojson
	@cp lausanne_corr_pop_access.pmtiles ../../frontend/public/geodata/
		
	# Process waste-access correlations
	@echo "Processing waste-access correlations..."
	@tippecanoe --force -zg --read-parallel -o lausanne_corr_waste_access.pmtiles \
		-l corr_waste_access \
		--drop-densest-as-needed \
		--extend-zooms-if-still-dropping \
		combined_waste_access.geojson
	@cp lausanne_corr_waste_access.pmtiles ../../frontend/public/geodata/
		
	@echo "Correlation PMTiles created and copied to frontend/public/geodata/"

# Clean up intermediate files
clean:
	@echo "Cleaning up intermediate files..."
	rm -f lausanne_corr_waste_pop.pmtiles 2>/dev/null || true
	rm -f lausanne_corr_pop_access.pmtiles 2>/dev/null || true
	rm -f lausanne_corr_waste_access.pmtiles 2>/dev/null || true
	rm -f combined_waste_pop.geojson 2>/dev/null || true
	rm -f combined_pop_access.geojson 2>/dev/null || true
	rm -f combined_waste_access.geojson 2>/dev/null || true
	@echo "Cleanup complete"