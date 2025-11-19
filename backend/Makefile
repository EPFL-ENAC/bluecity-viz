.PHONY: help install dev test clean lint format

help:
	@echo "BlueCity Backend Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies with uv"
	@echo "  make dev        - Run development server with auto-reload"
	@echo "  make run        - Run production server"
	@echo "  make test       - Run test script"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Format code with ruff"
	@echo "  make clean      - Remove cache and build files"

install:
	uv sync

dev:
	uv run --directory . python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run:
	uv run --directory . python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	uv run --directory . python test_with_data.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build
