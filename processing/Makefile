# BlueCity Viz Processing - Makefile

.PHONY: help install sync update clean format lint test run-tests dev-install

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	uv sync

sync: install ## Alias for install

update: ## Update all dependencies
	uv sync --upgrade

dev-install: ## Install with development dependencies
	uv sync --dev

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ htmlcov/ .coverage

format: ## Format code with black and isort
	uv run black .
	uv run isort .

lint: ## Run linting checks
	uv run flake8 .
	uv run mypy .

test: ## Run tests
	uv run pytest

run-tests: test ## Alias for test

check: format lint test ## Run all checks (format, lint, test)

# Individual script running examples
run-correlation: ## Run correlation analysis
	uv run python Correlation/combine_geojson.py

run-sp7: ## Run SP7 processing
	uv run python SP7/process.py

run-waste: ## Run waste processing
	uv run python SP04_Waste/process.py

# Jupyter notebook
notebook: ## Start Jupyter notebook
	uv run jupyter notebook

# Environment info
env-info: ## Show Python environment information
	uv run python --version
	uv run python -c "import sys; print('Python executable:', sys.executable)"
	uv run pip list
