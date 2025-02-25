generate-data:
	@echo "Generating data"
	python process.py
	tippecanoe --force -zg --read-parallel -U 2 -o lausanne_migration_2011_2023.pmtiles lausanne_migration_2011_2023.geojson 
	@echo "Data generated" 