import pandas as pd
import networkx as nx
from pathlib import Path


def enrich_habitat(graph: nx.MultiDiGraph, habitat_csv: Path) -> nx.MultiDiGraph:
    """Add habitat_area_m2 attribute to graph edges from a pre-computed CSV."""
    if not habitat_csv.exists():
        print(f"  Habitat CSV not found at {habitat_csv} — skipping.")
        return graph

    df = pd.read_csv(habitat_csv)
    # Build lookup: (u, v) → habitat_area_m2
    habitat_map = {
        (int(row.u), int(row.v)): float(row.habitat_area_m2)
        for row in df.itertuples()
    }
    enriched = 0
    for u, v, k in graph.edges(keys=True):
        area = habitat_map.get((u, v), 0.0)
        graph[u][v][k]['habitat_area_m2'] = area
        if area > 0:
            enriched += 1
    print(f"  Habitat areas assigned: {enriched}/{len(graph.edges())} edges have data.")
    return graph
