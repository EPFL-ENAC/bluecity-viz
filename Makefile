# BlueCity Viz - Root Makefile

# Local settings, gitignored: one KEY=value per line, no quotes (make reads
# this as a makefile, so quotes would end up in the value). `-` means it is
# fine when the file is not there. Copy .env.example to start one. A value
# given on the command line still wins.
-include .env

# Per-checkout overrides. Git worktrees export these from .env.worktree (see
# docs/worktree-env/), the main checkout keeps the defaults. `?=` matters: the
# value only applies when the environment does not already set one.
BACKEND_PORT ?= 8000

.PHONY: help dev build install clean upload-frontend-geodata list-geodata check-bucket-env check-geodata clean-geodata
.PHONY: dev-all tmux-dev-all new go wt-land wt-done wt-open

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

# --- dev sessions and git worktrees (docs/worktree-env/)

# Both servers in this terminal (same as `make dev`, the name matches resslab-hub).
# In a worktree, export its ports first: set -a; . .env.worktree; set +a
dev-all: dev ## Same as `make dev` (both servers in this terminal)

tmux-dev-all: ## tmux session "<repo>/<branch>" with claude, backend, frontend and shell panes
	scripts/tmux-dev.sh

new: ## make new BRANCH=feat/x [BASE=origin/dev] [PROMPT=brief.md] : worktree + deps + session, attached
	scripts/wt-new.sh $(BRANCH) $(BASE) $(if $(PROMPT),--prompt '$(PROMPT)')

go: new ## make go BRANCH=feat/x : jump to the branch's session, creating branch/worktree/session as needed (tab completion: wtgo)

wt-land: ## make wt-land BRANCH=feat/x [MODE=--local] : rebase, PR + squash-merge into dev, clean up
	scripts/wt-land.sh $(BRANCH) $(MODE)

wt-done: ## make wt-done BRANCH=feat/x : kill the session + remove the worktree, keep the branch
	scripts/wt-done.sh $(BRANCH)

wt-open: ## make wt-open [TARGET=frontend|backend] [BRANCH=feat/x] : print and open the URL
	scripts/wt-open.sh $(or $(TARGET),frontend) $(BRANCH)


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