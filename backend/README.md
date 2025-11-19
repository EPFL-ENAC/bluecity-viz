# BlueCity Backend

FastAPI backend for traffic analysis and route optimization with edge removal capabilities.

## Setup

```bash
# Install dependencies with uv
uv sync

# Run the development server
uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI): `http://localhost:8000/docs`

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health status
- `POST /api/v1/routes/calculate` - Calculate shortest paths
- `POST /api/v1/routes/recalculate` - Recalculate paths with removed edges

## Usage Example

First, you need to load a graph. The GraphService expects a path to a saved OSMnx graph file.

```python
# Example request to calculate routes
import requests

response = requests.post(
    "http://localhost:8000/api/v1/routes/calculate",
    json={
        "pairs": [
            {"origin": 123456, "destination": 789012},
            {"origin": 345678, "destination": 901234}
        ],
        "weight": "travel_time",
        "include_geometry": True
    }
)

print(response.json())
```

## Development

```bash
# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint code
uv run ruff check .
```
