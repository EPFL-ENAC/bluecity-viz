# BlueCity Viz - Root Makefile

# Local settings, gitignored: one KEY=value per line, no quotes (make reads
# this as a makefile, so quotes would end up in the value). `-` means it is
# fine when the file is not there. Copy .env.example to start one. A value
# given on the command line still wins.
-include .env

# Per-checkout override. wtx writes the ports in .env.worktree and every pane
# exports them, the main checkout keeps the default. `?=` matters: the value
# only applies when the environment does not already set one.
BACKEND_PORT ?= 8000

.PHONY: help dev build install clean upload-frontend-geodata list-geodata check-bucket-env check-geodata clean-geodata

help: ## Show this help message
	@echo "BlueCity Viz - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start frontend and backend development servers
	@echo "Starting backend and frontend development servers..."
	@trap 'kill 0' INT; \
	cd backend && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload & \
	cd frontend && pnpm run dev & \
	wait

dev-frontend: ## Start only frontend development server
	cd frontend && pnpm run dev

dev-backend: ## Start only backend development server
	cd backend && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload

build: ## Build frontend for production
	cd frontend && pnpm run build

install: ## Install all dependencies
	cd frontend && pnpm install
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

# Push the geodata to S3.
#
# sync, not put: it compares each file by size and md5, so only what is new or
# what changed goes up, and running it twice costs nothing. -F matters, several
# files in geodata are symlinks to the shared data directory and s3cmd skips a
# symlink without it. Never add --delete-removed, it would drop everything on
# S3 that is not in the local folder.
upload-frontend-geodata: check-bucket-env check-geodata ## Push new or changed geodata to S3 (DRY=1 to preview)
	@echo "Syncing frontend/public/geodata/ to s3://$(BUCKET_NAME)/bluecity/"
	@s3cmd sync $(if $(DRY),--dry-run) --acl-public --guess-mime-type \
		--follow-symlinks --check-md5 --no-encrypt --progress \
		--add-header="Cache-Control:max-age=86400" \
		frontend/public/geodata/ s3://$(BUCKET_NAME)/bluecity/
	@echo "$(if $(DRY),Preview only - nothing was sent.,Done: https://$(BUCKET_NAME)/bluecity/)"

# List all files uploaded to S3
list-geodata: check-bucket-env ## List geodata files in S3 bucket
	@echo "Listing files in s3://${BUCKET_NAME}/bluecity/..."
	@s3cmd ls s3://${BUCKET_NAME}/bluecity/

# Clean up the geodata folder (optional)
clean-geodata: ## Clean temporary files from geodata directory
	@echo "Cleaning temporary files from frontend/public/geodata/..."
	@find frontend/public/geodata -name "*.tmp" -delete 2>/dev/null || true
	@find frontend/public/geodata -name "*.bak" -delete 2>/dev/null || true