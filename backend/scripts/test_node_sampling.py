#!/usr/bin/env python
"""Test script for node sampling service integration."""

import logging
import sys

logging.basicConfig(level=logging.INFO)

print("=" * 80)
print("Testing Node Sampling Service Integration")
print("=" * 80)

# Test 1: Import SamplingConfig
print("\n[TEST 1] Importing SamplingConfig...")
try:
    from app.services.node_sampling_service import SamplingConfig

    print("✓ SamplingConfig imported successfully")
    config = SamplingConfig()
    print(f"✓ Default config created: {config.model_dump()}")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 2: Import generate_research_based_pairs
print("\n[TEST 2] Importing generate_research_based_pairs...")
try:
    from app.services.node_sampling_service import generate_research_based_pairs

    print("✓ generate_research_based_pairs imported successfully")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 3: Load graph and test sampling
print("\n[TEST 3] Testing research-based sampling with small sample...")
try:
    from pathlib import Path

    import osmnx as ox

    graph_path = Path("data/lausanne.graphml")
    if not graph_path.exists():
        print(f"⚠ Skipping: Graph file not found at {graph_path}")
    else:
        print(f"Loading graph from {graph_path}...")
        g = ox.load_graphml(str(graph_path))
        print(f"✓ Graph loaded: {len(g.nodes)} nodes, {len(g.edges)} edges")

        # Test with very small sample to keep it fast
        print("Generating 10 OD pairs (n_nodes_preprocess=100)...")
        config = SamplingConfig(n_nodes_preprocess=100)
        pairs = generate_research_based_pairs(g, n_pairs=10, config=config, seed=42)
        print(f"✓ Generated {len(pairs)} OD pairs")
        print(f"  First 3 pairs: {[(p.origin, p.destination) for p in pairs[:3]]}")

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test 4: Verify origin distribution (fix for single-origin bug)
print("\n[TEST 4] Testing origin distribution (critical bug fix)...")
try:
    from pathlib import Path

    import osmnx as ox

    graph_path = Path("data/lausanne.graphml")
    if not graph_path.exists():
        print(f"⚠ Skipping: Graph file not found at {graph_path}")
    else:
        print(f"Loading graph from {graph_path}...")
        g = ox.load_graphml(str(graph_path))

        # Test with 100 pairs to verify distribution
        print("Generating 100 OD pairs to test origin distribution...")
        config = SamplingConfig(
            n_nodes_preprocess=150,  # Must be >5% higher than n_pairs (100)
            n_origins=50,  # 50 origins
            n_destinations_per_origin=10,  # 10 destinations each = 500 candidates
        )
        pairs = generate_research_based_pairs(g, n_pairs=100, config=config, seed=42)

        # Analyze origin distribution
        origins = [p.origin for p in pairs]
        unique_origins = set(origins)

        print(
            f"✓ Generated {len(pairs)} OD pairs from {len(unique_origins)} unique origins"
        )

        # Calculate concentration metrics
        from collections import Counter

        origin_counts = Counter(origins)
        max_count = max(origin_counts.values())
        max_concentration = max_count / len(pairs)

        print("  Origin distribution:")
        print(f"    - Unique origins: {len(unique_origins)}")
        print(
            f"    - Max pairs from single origin: {max_count} ({max_concentration:.1%})"
        )
        print(f"    - Average pairs per origin: {len(pairs) / len(unique_origins):.1f}")

        # Verify we don't have the single-origin bug
        if len(unique_origins) < 5:
            print(
                f"✗ FAILED: Too few origins ({len(unique_origins)}), single-origin bug likely!"
            )
            sys.exit(1)

        if max_concentration > 0.5:
            print(
                f"✗ FAILED: Single origin dominates with {max_concentration:.1%} of pairs!"
            )
            sys.exit(1)

        print("✓ Origin distribution looks healthy (bug fixed!)")

        # Show top origins
        print("  Top 5 origins by frequency:")
        for origin, count in origin_counts.most_common(5):
            print(f"    - Origin {origin}: {count} pairs ({count/len(pairs):.1%})")

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test 5: Check model integration
print("\n[TEST 5] Testing model integration...")
try:
    from app.models.route import RandomPairsRequest
    from app.models.route import SamplingConfig as ModelSamplingConfig

    req = RandomPairsRequest(
        count=10,
        sampling_method="research",
        sampling_config=ModelSamplingConfig(n_nodes_preprocess=100),
    )
    print(f"✓ RandomPairsRequest created: method={req.sampling_method}")

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✓ All tests passed!")
print("=" * 80)
print("\nYou can now start the backend with:")
print("  cd backend && uv run uvicorn app.main:app --reload")
print("\nThe backend will use research-based sampling by default.")
