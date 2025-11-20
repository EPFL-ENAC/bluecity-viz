# BlueCity Viz - Root Makefile

.PHONY: help dev build install clean upload-frontend-geodata list-geodata check-bucket-env check-geodata clean-geodata

help: ## Show this help message
	@echo "BlueCity Viz - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start frontend and backend development servers
	@echo "Starting backend and frontend development servers..."
	@trap 'kill 0' INT; \
	cd backend && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload & \
	cd frontend && npm run dev & \
	wait

dev-frontend: ## Start only frontend development server
	cd frontend && npm run dev

dev-backend: ## Start only backend development server
	cd backend && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build: ## Build frontend for production
	cd frontend && npm run build

install: ## Install all dependencies
	cd frontend && npm install
	cd backend && uv sync
	cd processing && uv sync





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
upload-frontend-geodata: check-bucket-env check-geodata ## Upload geodata files to S3 bucket
	@echo "Starting upload of geodata files to s3://${BUCKET_NAME}/bluecity/..."
	@s3cmd put --recursive --acl-public --guess-mime-type \
		--preserve --no-encrypt --check-md5 --progress \
		--add-header="Cache-Control:max-age=86400" \
		frontend/public/geodata/ s3://${BUCKET_NAME}/bluecity/
	@echo "Upload complete!"
	@echo "Files are available at: https://${BUCKET_NAME}/bluecity/"

# List all files uploaded to S3
list-geodata: check-bucket-env ## List geodata files in S3 bucket
	@echo "Listing files in s3://${BUCKET_NAME}/bluecity/..."
	@s3cmd ls s3://${BUCKET_NAME}/bluecity/

# Clean up the geodata folder (optional)
clean-geodata: ## Clean temporary files from geodata directory
	@echo "Cleaning temporary files from frontend/public/geodata/..."
	@find frontend/public/geodata -name "*.tmp" -delete 2>/dev/null || true
	@find frontend/public/geodata -name "*.bak" -delete 2>/dev/null || true