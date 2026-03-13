.PHONY: download-data generate-data clean


download-data:
	@echo "Downloading data"
	python DataAccess.py
	@echo "Data downloaded"

generate-data:
	@echo "Generating data"
	python biodiversity.py
	@echo "Data generated"

clean:
	@echo "Cleaning data"
	rm -f *.gpkg
	@echo "Data cleaned"