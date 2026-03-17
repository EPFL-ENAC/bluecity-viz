"""Betweenness centrality computation and edge weight assignment for road networks."""

import logging
from typing import Dict, List, Optional, Tuple

import igraph as ig
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

logger = logging.getLogger(__name__)


def load_edge_attributes(g: nx.MultiDiGraph) -> pd.DataFrame:
    """Extract length, lanes, and speed_kph edge attributes from a NetworkX graph.

    Returns:
        DataFrame with columns: length (m), lanes (int), speed_kph (km/h)
    """
    length = pd.Series(nx.get_edge_attributes(g, "length"), name="length")

    lanes = nx.get_edge_attributes(g, "lanes")
    lanes = pd.Series(
        {idx: lanes.get(idx, 2) for idx in length.index}, name="lanes"
    ).fillna(2)
    lanes = lanes.apply(lambda v: v[0] if isinstance(v, list) else v).astype(int)

    speed_kph = pd.Series(nx.get_edge_attributes(g, "speed_kph"), name="speed_kph")
    df = pd.concat([length, lanes, speed_kph], axis=1)

    if pd.isnull(df).sum().sum() > 0:
        raise ValueError("Edge attributes contain NaNs.")
    return df


def assign_edge_weight(
    g: nx.MultiDiGraph,
    weight_name: str,
    edge_attr: pd.DataFrame,
    betweenness: Optional[pd.Series],
    betweenness_to_slowdown: Optional[float],
) -> nx.MultiDiGraph:
    """Assign travel-time edge weights, optionally applying BPR congestion.

    BPR speed-reduction formula (when betweenness is provided):
        speed_cong = speed_free / (1 + BC / (lanes × betweenness_to_slowdown))

    A BC value equal to betweenness_to_slowdown causes a 50% speed reduction.
    """
    if betweenness is not None and betweenness_to_slowdown:
        speed_kph_new = edge_attr["speed_kph"] / (
            1 + betweenness / edge_attr["lanes"] / betweenness_to_slowdown
        )
        speed_reduction = (
            (edge_attr["speed_kph"] - speed_kph_new) / edge_attr["speed_kph"] * 100
        )
        logger.info(
            f"Speed reduction — Avg: {speed_reduction.mean():.1f}%  "
            f"Max: {speed_reduction.max():.1f}%"
        )
        weight = edge_attr["length"] / (speed_kph_new / 3.6)
    else:
        weight = edge_attr["length"] / (edge_attr["speed_kph"] / 3.6)

    nx.set_edge_attributes(g, weight.to_dict(), weight_name)
    return g


def get_considered_nodes(
    g: nx.MultiDiGraph,
    rng: np.random.RandomState,
    max_nodes: int,
    node_weight_col: str,
) -> pd.Series:
    """Sample nodes suitable for the travel-time matrix and OD sampling.

    Filters to nodes with street_count ≥ 3 (excludes dead-ends and cul-de-sacs),
    then samples up to max_nodes by node weight.
    """
    n = ox.graph_to_gdfs(g, nodes=True, edges=False)

    if node_weight_col == "dummy":
        n[node_weight_col] = 1

    n = n.loc[(n["street_count"] >= 3) & (n[node_weight_col] > 0), node_weight_col]
    logger.info(f"{len(n):,} nodes available for sampling.")

    if len(n) > max_nodes:
        n = n.sample(max_nodes, random_state=rng, replace=False, weights=n)
        logger.info(f"Sampled {max_nodes:,} nodes for processing.")

    return n


def edge_betweenness_igraph(
    h: ig.Graph,
    expected_km_driven: float,
    directed: bool = True,
    cutoff: Optional[float] = None,
    weights: Optional[str] = None,
    sources: Optional[List[int]] = None,
    targets: Optional[List[int]] = None,
) -> Dict[Tuple[int, int], float]:
    """Calculate normalized edge betweenness centrality using igraph.

    Normalization converts raw path-count BC into vehicle-flow units (veh/day):
        factor = daily_km_driven × 1000 / Σ(BC_raw × length_m)
        BC_normalized = BC_raw × factor

    This makes BC directly comparable to measured traffic counts and ensures
    the BPR formula produces physically meaningful speed reductions.

    Args:
        h: igraph Graph
        expected_km_driven: Daily vehicle-km baseline for normalization
        sources/targets: Sampled node indices (subset for tractable runtime)
    """
    bc_result = h.edge_betweenness(directed, cutoff, weights, sources, targets)

    total_sum = sum(bc * length for bc, length in zip(bc_result, h.es["length"]))
    factor = expected_km_driven * 1_000 / total_sum
    bc_dict = {idx: bc * factor for idx, bc in zip(h.get_edgelist(), bc_result)}

    return bc_dict
