.PHONY: help install dev test clean lint format

help:
	@echo "BlueCity Backend Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies with uv"
	@echo "  make dev        - Run development server with auto-reload"
	@echo "  make run        - Run production server"
	@echo "  make test       - Run test script"
	@echo "  make lint       - Run flake8 linter"
	@echo "  make format     - Format code with black"
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
	@if uv --version >/dev/null 2>&1; then \
		uv run flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics; \
		uv run flake8 app --count --exit-zero --max-complexity=15 --max-line-length=100 --statistics; \
	else \
		.venv/bin/flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics; \
		.venv/bin/flake8 app --count --exit-zero --max-complexity=15 --max-line-length=100 --statistics; \
	fi

format:
	@if uv --version >/dev/null 2>&1; then \
		uv run black app; \
	else \
		.venv/bin/black app; \
	fi

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build
