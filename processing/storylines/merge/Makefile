.PHONY: download-data generate-data clean

download-data:
	@echo "Downloading data..."
	mkdir -p data
	python DataAccess.py
	@echo "Data downloaded."

generate-data:
	@echo "Generating data..."
	python merge.py
	@echo "Data generated."

clean:
	@echo "Cleaning up generated data..."
	rm -f *.gpkg
	@echo "Clean up complete."