# Research-Based OD Sampling Integration

This document describes the research-based origin-destination (OD) pair sampling feature integrated into the BlueCity Viz backend.

## Overview

The backend now supports two methods for generating OD pairs:

1. **Simple Random Sampling** (legacy): Fast uniform random sampling within a geographic radius
2. **Research-Based Sampling** (new, default): Sophisticated sampling using betweenness centrality and lognormal trip distribution

The research-based method produces more realistic traffic patterns by modeling:
- Congestion effects through betweenness centrality
- Real-world trip distance preferences using lognormal distribution
- Node connectivity and importance

## Key Features

### 1. Betweenness Centrality with Congestion Modeling

The algorithm calculates edge betweenness centrality and uses it to model congestion:
- Edges with high betweenness experience speed reductions
- Speed reduction is proportional to traffic load per lane
- Iterative adjustment creates realistic travel time matrices

### 2. Lognormal Trip Distribution

Trip destinations are sampled using a lognormal distribution based on travel time:
- Calibrated using Swiss travel survey data (car trips in Lausanne area)
- Peak probability at ~8 minutes travel time
- Realistic falloff for very short and very long trips

### 3. Performance Optimization

- Uses **igraph** for fast betweenness calculation (orders of magnitude faster than NetworkX)
- Uses **igraph one-to-many routing** for ultra-fast route calculation (~9,000 routes/sec)
- Groups OD pairs by origin: 382 Dijkstra searches instead of 19,100 individual routes
- Leverages **scipy** for statistical distributions
- Configurable node sampling to balance accuracy vs. speed

## Configuration Parameters

The `SamplingConfig` model controls the sampling behavior:

The number of pairs is a setting (`backend/app/config.py`), not a field of
`SamplingConfig`. The number of origin draws follows from it:

    origin draws = ceil(pairs / n_destinations_per_origin)

Two settings, because the count is also a per-request choice:

- `OD_PAIRS_MAX` (76,400) is sampled and routed once, at startup.
- `OD_PAIRS` (20,000) is what a request gets when it does not say.
  `POST /routes/recalculate` takes `od_pairs`, `GET /routes/baseline` takes
  `?od_pairs=`, both capped at `OD_PAIRS_MAX`.

**The sets are nested.** N pairs are the *first* N pairs of the set sampled
at startup, so 20,000 is a subset of 76,400: more pairs means the same trips
plus extra ones, never a different sample. Two results are comparable as long
as they used the same N, and going from 20,000 to 76,400 only adds trips.
This works because the origin draws are in random order, so a prefix is still
a random sample of origins. The baseline for N is a slice of the route set,
not a new routing.

```python
class SamplingConfig(BaseModel):
    n_origins: int = 500
    # Not used when a pair count is given. Kept for the API schema.

    n_destinations_per_origin: int = 200
    # Number of destinations per origin draw.
    # An origin drawn twice gets twice as many destinations.

    n_nodes_preprocess: int = 1000
    # Maximum nodes for travel time matrix (higher = more accurate, slower)

    daily_km_driven: float = 1_250_000
    # Expected vehicle-km driven per day for betweenness normalization
    # Based on: population × car ownership × km/car/day
    # Example: 250,000 people × 0.5 cars/person × 10 km/car/day

    betweenness_to_slowdown: float = 50_000
    # Betweenness value (veh/day/lane) causing 50% speed reduction
    # Higher values = less congestion effect

    node_weight_col: str = "dummy"
    # Node attribute for static weights
    # "dummy" = uniform weights, or use population/employment data

    lognorm_mu: float = 6.85
    # Lognormal distribution mu parameter
    # Calibrated from Swiss Mobility and Transport Microcensus

    lognorm_sigma: float = 0.83
    # Lognormal distribution sigma parameter
    # Controls spread of trip distances
```

### The set sampled at startup (76,400 OD pairs)

With `OD_PAIRS_MAX=76400` and `n_destinations_per_origin=200`:
1. 382 origin draws, weighted by node weight (uniform by default)
2. Each draw samples 200 destinations with the lognormal travel-time weights
3. About 76,200 pairs come out, from roughly 307 distinct origins
   (382 draws with replacement, and an origin with no reachable
   destination is dropped)

Before this was a setting, the count came out of
`n_origins × n_destinations_per_origin` while the code checked a `n_pairs`
argument it then ignored. Asking for 500 pairs gave 76,400 of them.

#### How many pairs do we need?

Every frequency, betweenness and CO2 value on the map comes from this set,
so the count is a product decision. Per-edge usage frequency compared to the
76,400 set, free-flow routing on the Lausanne graph:

| set | correlation | top 100 edges in common | edges used |
|---|---|---|---|
| old sampler, 76,400 | 0.990 | 95 | 6,406 |
| 20,000 | 0.958 | 85 | 5,644 |
| 10,000 | 0.919 | 73 | 5,353 |
| 5,000 | 0.857 | 59 | 4,975 |

The first row is the set the old code produced. Fixing the sampler barely
moves the map (0.99 correlation).

The default is 20,000: 0.96 correlation and 85 of the top 100 edges, for a
congestion run about 4 times faster. The full set stays one request away.

### Tuning for Different Cities

**For smaller cities** (< 100k population):
- Reduce `daily_km_driven` proportionally to population
- Consider lower `betweenness_to_slowdown` for less congestion
- May reduce `n_origins` to 200-300 for faster processing

**For larger cities** (> 500k population):
- Increase `daily_km_driven` proportionally
- Increase `n_nodes_preprocess` for better coverage (up to 2000-3000)
- May increase `n_origins` to 1000+ for better geographic coverage
- May need to adjust `lognorm_mu` based on local travel patterns

**For cities with different trip patterns**:
- Adjust `lognorm_mu` to shift peak trip distance (higher = longer average trips)
- Adjust `lognorm_sigma` to change trip distance variability

**For performance tuning**:
- **More origins, fewer destinations** (e.g., 1000 origins × 5 destinations) = better geographic spread, slightly slower
- **Fewer origins, more destinations** (e.g., 100 origins × 50 destinations) = concentration on high-betweenness nodes, faster
- Default **500 × 10** balances geographic diversity with computation time

## API Usage

### 1. Generate OD Pairs

**Simple random sampling:**
```bash
curl -X POST "http://localhost:8000/api/v1/routes/random-pairs" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 100,
    "sampling_method": "simple",
    "radius_km": 3.0,
    "seed": 42
  }'
```

**Research-based sampling (default config):**
```bash
curl -X POST "http://localhost:8000/api/v1/routes/random-pairs" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 100,
    "sampling_method": "research",
    "seed": 42
  }'
```

**Research-based sampling (custom config):**
```bash
curl -X POST "http://localhost:8000/api/v1/routes/random-pairs" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 100,
    "sampling_method": "research",
    "seed": 42,
    "sampling_config": {
      "n_origins": 200,
      "n_destinations_per_origin": 20,
      "n_nodes_preprocess": 500,
      "daily_km_driven": 800000,
      "betweenness_to_slowdown": 40000
    }
  }'
```

### 2. Recalculate Routes

**Standard recalculation (reroute existing pairs):**
```bash
curl -X POST "http://localhost:8000/api/v1/routes/recalculate" \
  -H "Content-Type: application/json" \
  -d '{
    "edge_modifications": [
      {"u": 123, "v": 456, "action": "remove"}
    ],
    "resample_od_pairs": false
  }'
```

**Recalculation with OD resampling:**
```bash
curl -X POST "http://localhost:8000/api/v1/routes/recalculate" \
  -H "Content-Type: application/json" \
  -d '{
    "edge_modifications": [
      {"u": 123, "v": 456, "action": "remove"}
    ],
    "resample_od_pairs": true,
    "sampling_config": {
      "n_origins": 300,
      "n_destinations_per_origin": 15,
      "n_nodes_preprocess": 500
    }
  }'
```

**Note**: When `resample_od_pairs=true`, the modified graph is used to generate completely new OD pairs (new origins and destinations based on the modified network's betweenness centrality). When `false`, the same OD pairs are re-routed through the modified graph.

## Performance Characteristics

### Startup Time (Lausanne Network)

With default config (19,100 routes, 1000 preprocessing nodes):
- **Graph loading**: ~5-10 seconds
- **Research-based sampling**: ~30-40 seconds
  - Betweenness centrality calculation: ~20s
  - Travel time matrix computation: ~10s
  - OD pair sampling: <1s
- **Route calculation (igraph)**: ~2.5 seconds
  - Graph conversion: ~0.27s
  - 382 origins × 50 destinations routing: ~2.1s
  - Throughput: **~9,000 routes/sec**
- **Total startup time**: ~40-50 seconds

The startup time investment delivers high-quality, realistic OD pairs with extremely fast routing.

### Memory Usage

- Simple sampling: ~100-200 MB
- Research-based sampling: ~300-500 MB (depends on `n_nodes_preprocess`)
- igraph routing: No additional memory overhead (reuses existing graph)

### Routing Performance

The implementation uses **igraph one-to-many shortest paths** for optimal performance:

**Key optimization**: OD pairs are grouped by origin, then all destinations for each origin are calculated in a single Dijkstra search.

Example with default config:
- **19,100 OD pairs** from **382 unique origins** (avg 50 destinations/origin)
- **382 Dijkstra searches** instead of 19,100 individual searches
- **~50× speedup** compared to individual routing
- **Throughput**: ~9,000 routes/sec on typical hardware

This makes it feasible to compute 10,000+ routes in just 2-3 seconds.

### Scalability

**Betweenness Calculation (igraph)**:

| n_nodes_preprocess | Typical Time | Use Case |
|-------------------|--------------|----------|
| 100 | ~2-5 sec | Quick testing |
| 500 | ~10-15 sec | Small cities (<100k) |
| 1000 | ~20-25 sec | Medium cities (100-300k) ⭐ Default |
| 2000 | ~60-90 sec | Large cities (>300k) |
| 5000 | ~5-10 min | Very large metros |

**Route Calculation (igraph one-to-many)**:

| Number of Routes | Unique Origins | Time | Throughput |
|-----------------|---------------|------|------------|
| 1,000 | ~20 | ~0.2s | ~5,000 routes/sec |
| 5,000 | ~100 | ~0.8s | ~6,000 routes/sec |
| 19,100 | ~382 | ~2.1s | ~9,000 routes/sec |
| 50,000 | ~1,000 | ~6-8s | ~7,000 routes/sec |

Performance scales linearly with number of **unique origins**, not total routes.

## Implementation Details

### File Structure

```
backend/app/
├── services/
│   ├── graph_service.py           # Updated with sampling_method parameter
│   └── node_sampling_service.py   # NEW: Research-based sampling logic
├── models/
│   └── route.py                   # Updated with SamplingConfig
├── api/v1/
│   └── routes.py                  # Updated endpoints
└── main.py                        # Updated startup to use research sampling
```

### Key Functions

**`generate_research_based_pairs(g, n_pairs, config, seed)`**
- Main entry point for research-based sampling
- Returns list of `NodePair` objects
- Orchestrates the entire sampling pipeline

**`edge_betweenness_igraph(h, expected_km_driven, ...)`**
- Calculates normalized edge betweenness using igraph
- Much faster than NetworkX (O(V²E) with optimization)

**`sample_od_pairs(nodes, rng, n_samples, lognorm_mu, lognorm_sigma, t_matrix_dict)`**
- Samples destinations using lognormal weighting based on travel time
- `n_samples` parameter: number of origins to sample (each gets n_samples destinations)
- Accounts for travel time and node importance
- Returns dict mapping origin → list of destinations

**`calculate_routes(pairs, weight)`**
- Calculates shortest paths using **igraph one-to-many routing**
- Groups OD pairs by origin for optimal performance
- Returns list of `Route` objects with metrics (travel time, distance, elevation, CO2)
- Throughput: ~9,000 routes/sec on typical hardware

## Backwards Compatibility

✅ All existing API calls work unchanged
✅ Simple random sampling still available via `sampling_method='simple'`
✅ Default behavior changes to research-based (opt-out, not opt-in)

## Testing

Run the integration test:
```bash
cd backend
uv run python scripts/test_node_sampling.py
```

This tests:
1. ✓ Import and instantiation of SamplingConfig
2. ✓ Graph loading and sampling with small dataset
3. ✓ Origin distribution (verifies fix for single-origin bug)
4. ✓ Model integration (RandomPairsRequest, RecalculateRequest)

**Expected output** for origin distribution test:
- 10 unique origins from 100 OD pairs
- Max concentration: 10% per origin (perfectly distributed)
- No single-origin bug

## Future Enhancements

Potential improvements:

1. **Caching**: Cache betweenness centrality between runs
2. **Async initialization**: Load graph and calculate routes asynchronously
3. **Progressive sampling**: Start with fewer nodes, refine over time
4. **Custom node weights**: Support population/employment data from GIS
5. **Time-of-day modeling**: Different parameters for peak/off-peak hours
6. **Multi-modal**: Extend to bike/transit OD pairs
7. **~~One-to-many routing~~**: ✅ **IMPLEMENTED** - Using igraph one-to-many for ~50× speedup
8. **Persistent igraph storage**: Store graph as igraph permanently instead of converting repeatedly
   - Currently: Convert NetworkX → igraph on each startup (~0.27s)
   - Future: Store graph as igraph, convert only when needed for NetworkX-specific operations
   - Expected speedup: Eliminate conversion overhead, ~10% faster startup

## References

- Original research code: `/node_sampling.py` (provided by researcher)
- Swiss Mobility and Transport Microcensus: Source for lognormal parameters
- igraph documentation: https://igraph.org/python/
- OSMnx documentation: https://osmnx.readthedocs.io/

## Troubleshooting

**Issue**: Backend startup takes too long
- **Solution**: Reduce `n_nodes_preprocess` in startup config (e.g., 500 instead of 1000)

**Issue**: Memory errors during sampling
- **Solution**: Reduce `n_nodes_preprocess` to lower memory usage

**Issue**: OD pairs seem unrealistic (too short/long)
- **Solution**: Adjust `lognorm_mu` (higher = longer trips) and `lognorm_sigma` (higher = more variation)

**Issue**: Too much/little congestion effect
- **Solution**: Adjust `betweenness_to_slowdown` (higher = less congestion) and `daily_km_driven`

## Credits

Research-based sampling methodology provided by [Researcher Name].
Integration implemented by the BlueCity Viz team.
