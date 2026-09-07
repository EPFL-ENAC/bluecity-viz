# Stage 1: Build dependencies
FROM python:3.12-slim-bookworm AS builder

# Copy uv binary from the official image (pinned, not latest)
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy project files needed for dependency installation (separate layer for caching)
COPY pyproject.toml uv.lock .python-version README.md ./

# Runtime dependencies only: --no-dev drops ruff, pytest and httpx
RUN uv sync --frozen --no-cache --no-dev --no-install-project

# Stage 2: Final image (no uv binary, no build tooling)
FROM python:3.12-slim-bookworm AS final

# Run as a normal user, not root
RUN useradd --system --create-home --uid 1001 app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

# Application code and data (see .dockerignore for what stays out)
COPY --chown=app:app app ./app
COPY --chown=app:app data ./data

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

# python-slim has no curl, so probe with the stdlib
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--log-level", "info"]
