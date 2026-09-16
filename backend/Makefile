.PHONY: help install dev run test clean lint format format-check

SOURCES = app tests scripts

# Per-checkout override: wtx writes the ports in .env.worktree and every pane
# exports BACKEND_PORT, the main checkout keeps 8000.
BACKEND_PORT ?= 8000

help:
	@echo "BlueCity Backend Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies with uv"
	@echo "  make dev        - Run development server with auto-reload"
	@echo "  make run        - Run production server"
	@echo "  make test       - Run the pytest suite"
	@echo "  make lint       - Lint with ruff"
	@echo "  make format     - Format with ruff"
	@echo "  make format-check - Check formatting without writing"
	@echo "  make clean      - Remove cache and build files"

install:
	uv sync

dev:
	uv run --directory . python -m uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload

run:
	uv run --directory . python -m uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT)

test:
	uv run pytest

lint:
	uv run ruff check --no-fix $(SOURCES)

format:
	uv run ruff format $(SOURCES)

format-check:
	uv run ruff format --check $(SOURCES)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build
