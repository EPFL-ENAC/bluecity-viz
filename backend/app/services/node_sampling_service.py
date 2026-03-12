"""Node sampling service for research-based OD pair generation.

This module implements sophisticated origin-destination pair sampling based on:
- Betweenness centrality with congestion modeling
- Travel time matrix computation using igraph for performance
- Lognormal distribution-based sampling reflecting real trip patterns
- Iterative edge weight adjustment based on predicted traffic

Adapted from researcher's node_sampling.py script.
"""

import logging
from typing import Dict, List, Optional, Tuple

import igraph as ig
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import lognorm

logger = logging.getLogger(__name__)


class SamplingConfig(BaseModel):
    """Configuration for research-based OD sampling."""

    n_origins: int = Field(
        default=500,
        ge=10,
        le=2000,
        description="Number of origin nodes to sample",
    )
    n_destinations_per_origin: int = Field(
        default=200,
        ge=5,
        le=500,
        description="Number of destinations to sample per origin",
    )
    n_nodes_preprocess: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="Maximum nodes for travel time matrix calculation",
    )
    daily_km_driven: float = Field(
        default=1_250_000,
        gt=0,
        description="Expected vehicle-km driven per day for betweenness normalization",
    )
    betweenness_to_slowdown: float = Field(
        default=50_000,
        gt=0,
        description="Betweenness value causing 50% speed reduction (veh/day/lane)",
    )
    node_weight_col: str = Field(
        default="dummy",
        description="Node attribute for static weights ('dummy' for uniform)",
    )
    lognorm_mu: float = Field(
        default=6.85,
        description="Lognormal distribution mu parameter (from travel survey data)",
    )
    lognorm_sigma: float = Field(
        default=0.83, gt=0, description="Lognormal distribution sigma parameter"
    )


def show_weight_info(lognorm_mu: float, lognorm_sigma: float):
    """Log information about time-based weights for node pair sampling."""
    max_time = np.exp(lognorm_mu - lognorm_sigma**2)
    logger.info(f"Maximum weight assigned to nodes {max_time:.0f} s ({max_time/60:.1f} min) apart")
    times = [1, 2, 5, 10, 30, 60]
    weights = lognorm.pdf(
        [max_time] + [t * 60 for t in times], s=lognorm_sigma, scale=np.exp(lognorm_mu)
    )
    weights = weights / weights[0]
    logger.info(
        f"Relative weights: {', '.join([f'{t} min: {w:.2f}' for t, w in zip(times, weights[1:])])}"
    )


def load_edge_attributes(g: nx.MultiDiGraph) -> pd.DataFrame:
    """Extract length, lanes, and speed edge attributes from networkx graph.

    Args:
        g: NetworkX MultiDiGraph with edge attributes

    Returns:
        DataFrame with columns: length, lanes, speed_kph
    """
    length = pd.Series(nx.get_edge_attributes(g, "length"), name="length")

    # Get number of lanes and ensure integer value
    lanes = nx.get_edge_attributes(g, "lanes")
    lanes = pd.Series({idx: lanes.get(idx, 2) for idx in length.index}, name="lanes").fillna(2)
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
    """Assign edge weight representing travel time on each edge.

    If betweenness and betweenness_to_slowdown are provided, congestion is modeled.
    A betweenness value equal to betweenness_to_slowdown leads to 50% speed decrease.

    Args:
        g: NetworkX graph
        weight_name: Name for the weight attribute
        edge_attr: DataFrame with length, lanes, speed_kph columns
        betweenness: Optional betweenness centrality values per edge
        betweenness_to_slowdown: Betweenness threshold for 50% slowdown

    Returns:
        Graph with updated edge weights
    """
    if betweenness is not None and betweenness_to_slowdown:
        speed_kph_new = edge_attr["speed_kph"] / (
            1 + betweenness / edge_attr["lanes"] / betweenness_to_slowdown
        )
        speed_reduction = (edge_attr["speed_kph"] - speed_kph_new) / edge_attr["speed_kph"] * 100
        logger.info(
            f"Speed reduction - Avg: {speed_reduction.mean():.1f}% / Max: {speed_reduction.max():.1f}%"
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
    """Get nodes for travel time matrix estimation with static weights.

    Filters nodes with street_count >= 3 (avoid dead-ends) and positive weight.

    Args:
        g: NetworkX graph
        rng: Random state for reproducibility
        max_nodes: Maximum number of nodes to return
        node_weight_col: Column name for node weights ('dummy' for uniform)

    Returns:
        Series of node weights indexed by node ID
    """
    n = ox.graph_to_gdfs(g, nodes=True, edges=False)

    if node_weight_col == "dummy":
        n[node_weight_col] = 1

    # Filter nodes: at least 3 connections and positive weight
    n = n.loc[(n["street_count"] >= 3) & (n[node_weight_col] > 0), node_weight_col]
    logger.info(f"{len(n):,} nodes available for sampling.")

    if len(n) > max_nodes:
        n = n.sample(max_nodes, random_state=rng, replace=False, weights=n)
        logger.info(f"Sampled {max_nodes:,} nodes for processing.")

    return n


def networkx_to_igraph_with_indices(
    g: nx.MultiDiGraph,
) -> Tuple[ig.Graph, Dict[str, dict]]:
    """Convert networkx graph to igraph with bidirectional index mappings.

    Args:
        g: NetworkX MultiDiGraph

    Returns:
        Tuple of (igraph Graph, index mappings dict)
        Index mappings contain: node_nx_to_ig, node_ig_to_nx, edge_nx_to_ig, edge_ig_to_nx
    """
    e = ox.graph_to_gdfs(g, nodes=False, edges=True)
    nx.set_edge_attributes(g, {idx: idx for idx in e.index}, name="nx_edge_id")
    h = ig.Graph.from_networkx(g)

    idx_maps = {
        "node_nx_to_ig": {a: b for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "node_ig_to_nx": {b: a for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "edge_nx_to_ig": {a: b for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
        "edge_ig_to_nx": {b: a for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
    }

    return h, idx_maps


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

    Args:
        h: igraph Graph
        expected_km_driven: Expected total km driven per day for normalization
        directed: Whether to treat graph as directed
        cutoff: Maximum distance to consider
        weights: Edge weight attribute name
        sources: Source node indices for sampling
        targets: Target node indices for sampling

    Returns:
        Dict mapping edge tuples to normalized betweenness values
    """
    bc_result = h.edge_betweenness(directed, cutoff, weights, sources, targets)

    # Normalize betweenness by total km and edge length
    total_sum = sum([bc * length for bc, length in zip(bc_result, h.es["length"])])
    factor = expected_km_driven * 1_000 / total_sum
    bc_dict = {idx: bc * factor for idx, bc in zip(h.get_edgelist(), bc_result)}

    return bc_dict


def travel_time_matrix_igraph(h: ig.Graph, nodes: List[int], weight_name: str) -> List[List[float]]:
    """Compute all-pairs travel time matrix using igraph.

    Args:
        h: igraph Graph
        nodes: Node indices to compute matrix for
        weight_name: Edge weight attribute name

    Returns:
        Matrix of travel times (list of lists)
    """
    return h.distances(source=nodes, target=nodes, weights=weight_name)


def igraph_matrix_to_dict(
    t_matrix: List[List[float]], nodes_ig: List[int], idx_maps: dict
) -> Dict[int, Dict[int, float]]:
    """Convert igraph travel time matrix to dict with NetworkX node IDs.

    Args:
        t_matrix: Travel time matrix from igraph
        nodes_ig: igraph node indices
        idx_maps: Index mapping dictionary

    Returns:
        Nested dict: {origin_nx_id: {dest_nx_id: travel_time}}
    """
    t_matrix_dict = {}
    for row_id, t_list in zip(nodes_ig, t_matrix):
        d = {idx_maps["node_ig_to_nx"][col_id]: t for col_id, t in zip(nodes_ig, t_list)}
        t_matrix_dict[idx_maps["node_ig_to_nx"][row_id]] = d
    return t_matrix_dict


def sample_od_pairs(
    nodes: pd.Series,
    rng: np.random.RandomState,
    n_samples: int,
    lognorm_mu: float,
    lognorm_sigma: float,
    t_matrix_dict: Dict[int, Dict[int, float]],
) -> Dict[int, List[int]]:
    """Sample OD pairs using lognormal distance-based weighting.

    Args:
        nodes: Node weights (Series indexed by node ID)
        rng: Random state
        n_samples: Number of ORIGINS to sample (each origin will get n_samples destinations)
        lognorm_mu: Lognormal mu parameter
        lognorm_sigma: Lognormal sigma parameter
        t_matrix_dict: Travel time matrix as nested dict

    Returns:
        Dict mapping origin to list of destinations (n_samples origins → n_samples destinations each)
    """
    # Sample origins WITH replacement (nodes can be sampled multiple times)
    origins = list(nodes.sample(n_samples, random_state=rng, replace=True, weights=nodes).index)

    od_pairs = {}
    failed_origins = []

    for origin in origins:
        times = [t_matrix_dict[origin][dest] for dest in nodes.index]
        time_weights = lognorm.pdf(times, s=lognorm_sigma, scale=np.exp(lognorm_mu))
        weights = nodes * time_weights

        try:
            destinations = list(
                nodes.sample(n_samples, random_state=rng, replace=True, weights=weights).index
            )
            od_pairs[origin] = destinations
        except ValueError:
            failed_origins.append(origin)

    if failed_origins:
        logger.warning(
            f"Failed to sample destinations for {len(failed_origins)} origins (disconnected nodes?)"
        )

    return od_pairs


def generate_research_based_pairs(
    g: nx.MultiDiGraph,
    n_pairs: int,
    config: Optional[SamplingConfig] = None,
    seed: int = 42,
) -> List:
    """Generate OD pairs using research-based methodology.

    This is the main entry point that orchestrates the entire sampling process:
    1. Prepare network and sample candidate nodes
    2. Calculate betweenness centrality with congestion modeling
    3. Compute travel time matrix
    4. Sample final OD pairs using lognormal distribution

    Args:
        g: NetworkX MultiDiGraph with required attributes (length, speed_kph, lanes)
        n_pairs: Number of OD pairs to generate
        config: Sampling configuration (uses defaults if None)
        seed: Random seed for reproducibility

    Returns:
        List of NodePair objects
    """
    # Import here to avoid circular dependency
    from app.models.route import NodePair

    config = config or SamplingConfig()

    # Validate configuration
    if config.n_nodes_preprocess < n_pairs * 1.05:
        raise ValueError(
            f"n_nodes_preprocess ({config.n_nodes_preprocess}) should be at least "
            f"5% higher than n_pairs ({n_pairs})"
        )

    logger.info("Starting research-based OD pair sampling")
    logger.info(f"Configuration: {config.model_dump()}")
    show_weight_info(config.lognorm_mu, config.lognorm_sigma)

    # Step 1: Prepare data
    rng = np.random.RandomState(seed)
    edge_attr = load_edge_attributes(g)

    # Initial edge weights (no congestion)
    edge_weight_default = "duration"
    g = assign_edge_weight(g, edge_weight_default, edge_attr, None, None)

    # Sample nodes for processing
    nodes = get_considered_nodes(g, rng, config.n_nodes_preprocess, config.node_weight_col)

    # Convert to igraph for performance
    h, idx_maps = networkx_to_igraph_with_indices(g)
    nodes_ig = [idx_maps["node_nx_to_ig"][idx] for idx in nodes.index]

    # Step 2: Calculate betweenness centrality
    logger.info("Calculating betweenness centrality...")
    bc_dict = edge_betweenness_igraph(
        h, config.daily_km_driven, weights=edge_weight_default, sources=nodes_ig, targets=nodes_ig
    )
    betweenness = {idx_maps["edge_ig_to_nx"][idx]: bc for idx, bc in bc_dict.items()}
    betweenness = pd.Series({k: betweenness.get(k, 0) for k in edge_attr.index}, name="betweenness")

    # Step 3: Re-calculate edge weights with congestion
    edge_weight_bc = "duration_bc"
    g = assign_edge_weight(
        g, edge_weight_bc, edge_attr, betweenness, config.betweenness_to_slowdown
    )

    # Update igraph weights
    duration = nx.get_edge_attributes(g, edge_weight_bc)
    h.es[edge_weight_bc] = [duration[idx_maps["edge_ig_to_nx"][idx]] for idx in h.get_edgelist()]

    # Step 4: Calculate travel time matrix
    logger.info("Computing travel time matrix...")
    t_matrix = travel_time_matrix_igraph(h, nodes_ig, edge_weight_bc)
    t_matrix_dict = igraph_matrix_to_dict(t_matrix, nodes_ig, idx_maps)

    # Step 5: Sample OD pairs using configured origins and destinations
    logger.info(
        f"Sampling {config.n_origins} origins × {config.n_destinations_per_origin} destinations per origin..."
    )
    od_pairs_dict = sample_od_pairs(
        nodes,
        rng,
        config.n_origins,  # Number of origins to sample
        config.lognorm_mu,
        config.lognorm_sigma,
        t_matrix_dict,
    )

    # Convert to flat list of NodePair objects
    # Take only n_destinations_per_origin destinations from each origin
    node_pairs = []
    for origin, destinations in od_pairs_dict.items():
        for destination in destinations[: config.n_destinations_per_origin]:
            node_pairs.append(NodePair(origin=origin, destination=destination))

    # Keep pairs ordered by betweenness (high-betweenness origins first)
    # Then select first n_pairs
    # total_candidates = len(node_pairs)
    # logger.info(f"Generated {total_candidates} candidate OD pairs, selecting first {n_pairs}")
    # return node_pairs[:n_pairs]
    return node_pairs
