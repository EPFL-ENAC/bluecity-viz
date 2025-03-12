dev:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

install:
	cd frontend && npm install

# Check if BUCKET_NAME is defined
check-bucket-env:
	@if [ -z "$(BUCKET_NAME)" ]; then \
		echo "Error: BUCKET_NAME environment variable is not set"; \
		echo "Usage: BUCKET_NAME=your-bucket-name make upload-frontend-geodata"; \
		exit 1; \
	fi

# Verify geodata directory exists
check-geodata:
	@if [ ! -d "frontend/public/geodata" ]; then \
		echo "Error: frontend/public/geodata directory does not exist"; \
		exit 1; \
	fi
	@if [ -z "$$(find frontend/public/geodata -type f 2>/dev/null)" ]; then \
		echo "Warning: No files found in frontend/public/geodata"; \
	fi

# Upload geodata with improved features
upload-frontend-geodata: check-bucket-env check-geodata
	@echo "Starting upload of geodata files to s3://${BUCKET_NAME}/bluecity/..."
	@s3cmd put --recursive --acl-public --guess-mime-type \
		--preserve --no-encrypt --check-md5 --progress \
		--add-header="Cache-Control:max-age=86400" \
		frontend/public/geodata/ s3://${BUCKET_NAME}/bluecity/
	@echo "Upload complete!"
	@echo "Files are available at: https://${BUCKET_NAME}/bluecity/"

# List all files uploaded to S3
list-geodata: check-bucket-env
	@echo "Listing files in s3://${BUCKET_NAME}/bluecity/..."
	@s3cmd ls s3://${BUCKET_NAME}/bluecity/

# Clean up the geodata folder (optional)
clean-geodata:
	@echo "Cleaning temporary files from frontend/public/geodata/..."
	@find frontend/public/geodata -name "*.tmp" -delete
	@find frontend/public/geodata -name "*.bak" -delete

.PHONY: dev build install upload-frontend-geodata list-geodata check-bucket-env check-geodata clean-geodata