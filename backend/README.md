# BlueCity Backend

FastAPI backend for traffic analysis and route optimization with edge removal capabilities and research-based OD pair sampling.

## Features

- 🚗 **Route Calculation**: Calculate shortest paths between origin-destination pairs
- 📊 **Impact Analysis**: Analyze the impact of network modifications on traffic
- 🔬 **Research-Based Sampling**: Generate realistic OD pairs using betweenness centrality and lognormal trip distribution
- ⚡ **Performance Optimized**: Uses igraph for fast graph computations
- 📈 **Congestion Modeling**: Models traffic congestion effects on travel times

## Setup

```bash
# Install dependencies with uv
uv sync

# Run the development server
uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI): `http://localhost:8000/docs`

## OD Pair Sampling

The backend supports two methods for generating origin-destination pairs:

1. **Simple Random Sampling** (legacy): Fast uniform random sampling
2. **Research-Based Sampling** (default): Sophisticated sampling using betweenness centrality and trip distance modeling

See [RESEARCH_SAMPLING.md](./RESEARCH_SAMPLING.md) for detailed documentation on research-based sampling.

### Quick Start

```bash
# Test the research-based sampling
uv run python test_node_sampling.py
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health status
- `GET /api/v1/routes/graph-info` - Get graph statistics
- `POST /api/v1/routes/calculate` - Calculate shortest paths
- `POST /api/v1/routes/recalculate` - Recalculate paths with network modifications
- `POST /api/v1/routes/random-pairs` - Generate random OD pairs (simple or research-based)
- `GET /api/v1/routes/graph` - Get complete graph data
- `GET /api/v1/routes/edge-geometries` - Get edge geometries for visualization

## Usage Examples

### Calculate Routes

```python
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

### Generate Research-Based OD Pairs

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/routes/random-pairs",
    json={
        "count": 100,
        "sampling_method": "research",
        "seed": 42,
        "sampling_config": {
            "n_nodes_preprocess": 1000,
            "daily_km_driven": 1250000
        }
    }
)

pairs = response.json()
```

### Recalculate with Network Modifications

```python
import requests

# Recalculate routes after removing an edge
response = requests.post(
    "http://localhost:8000/api/v1/routes/recalculate",
    json={
        "edge_modifications": [
            {"u": 123, "v": 456, "action": "remove"}
        ],
        "resample_od_pairs": False  # Set to True to resample OD pairs
    }
)

result = response.json()
print(f"Affected routes: {result['impact_statistics']['affected_routes']}")
```

## Development

```bash
# Run tests
uv run pytest

# Test node sampling integration
uv run python test_node_sampling.py

# Format code
make format

# Lint code
make lint

# Type check
uv run mypy app
```
