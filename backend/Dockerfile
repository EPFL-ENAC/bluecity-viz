# Stage 1: Build dependencies
FROM python:3.12-slim-bookworm AS builder

# Copy uv binary from official UV image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables for uv
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Create the app directory
WORKDIR /app

# Copy project files needed for dependency installation (separate layer for caching)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv sync (cached unless pyproject.toml/uv.lock change)
RUN uv sync --frozen --no-cache

# Stage 2: Build the final image


FROM python:3.12-slim-bookworm AS final


# Copy the installed dependencies from the builder stage
# Copy the uv binary from builder stage to final image
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy the installed dependencies from the builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/uv.lock /app/uv.lock

# Create the app directory
WORKDIR /app

# Copy the application code (excluding files in .dockerignore)
COPY . .

# Set the path to include the virtual environment's binaries
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Run the application using uv run
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--log-level", "info"]
