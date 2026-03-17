"""OD pair sampling using lognormal travel-time weighting."""

import logging
from typing import Dict, List, Optional

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import lognorm

logger = logging.getLogger(__name__)


def show_weight_info(lognorm_mu: float, lognorm_sigma: float) -> None:
    """Log relative destination weights at representative travel times."""
    max_time = np.exp(lognorm_mu - lognorm_sigma**2)
    logger.info(
        f"Maximum weight at {max_time:.0f} s ({max_time/60:.1f} min) travel time"
    )
    times = [1, 2, 5, 10, 30, 60]
    weights = lognorm.pdf(
        [max_time] + [t * 60 for t in times], s=lognorm_sigma, scale=np.exp(lognorm_mu)
    )
    weights = weights / weights[0]
    logger.info(
        "Relative weights: "
        + ", ".join(f"{t} min: {w:.2f}" for t, w in zip(times, weights[1:]))
    )


def sample_od_pairs(
    nodes: pd.Series,
    rng: np.random.RandomState,
    n_samples: int,
    lognorm_mu: float,
    lognorm_sigma: float,
    t_matrix_dict: Dict[int, Dict[int, float]],
) -> Dict[int, List[int]]:
    """Sample OD pairs using lognormal travel-time weighting.

    Destinations are weighted by a lognormal distribution over travel time from
    each origin. Parameters (mu=6.85, sigma=0.83) are calibrated to travel survey
    data with mode ≈ 940 s (≈ 15 min), reflecting typical urban trip lengths.

    Origins are sampled WITH replacement so high-weight nodes attract more trips.

    Args:
        nodes: Node weights indexed by NetworkX node ID
        n_samples: Number of origins to sample (each gets n_samples destinations)
        t_matrix_dict: {origin_nx_id: {dest_nx_id: travel_time_s}}
    """
    origins = list(
        nodes.sample(n_samples, random_state=rng, replace=True, weights=nodes).index
    )

    od_pairs: Dict[int, List[int]] = {}
    failed_origins = []

    for origin in origins:
        times = [t_matrix_dict[origin][dest] for dest in nodes.index]
        time_weights = lognorm.pdf(times, s=lognorm_sigma, scale=np.exp(lognorm_mu))
        weights = nodes * time_weights

        try:
            destinations = list(
                nodes.sample(
                    n_samples, random_state=rng, replace=True, weights=weights
                ).index
            )
            od_pairs[origin] = destinations
        except ValueError:
            failed_origins.append(origin)

    if failed_origins:
        logger.warning(
            f"Failed to sample destinations for {len(failed_origins)} origins "
            f"(disconnected nodes?)"
        )

    return od_pairs


def generate_research_based_pairs(
    g: nx.MultiDiGraph,
    n_pairs: int,
    config=None,
    seed: int = 42,
) -> List:
    """Generate OD pairs using research-based methodology.

    Pipeline:
    1. Sample candidate nodes (street_count ≥ 3, uniform weights)
    2. Compute edge betweenness centrality (igraph, sampled sources/targets)
    3. Derive BC-congested edge weights via BPR formula
    4. Compute all-pairs travel-time matrix on congested graph
    5. Sample OD pairs using lognormal travel-time weights

    Args:
        g: NetworkX MultiDiGraph with length, speed_kph, lanes attributes
        n_pairs: Number of OD pairs to generate
        config: SamplingConfig (uses defaults if None)
        seed: Random seed for reproducibility

    Returns:
        List of NodePair objects
    """
    from app.models.route import NodePair
    from app.services.sampling.betweenness import (
        assign_edge_weight,
        edge_betweenness_igraph,
        get_considered_nodes,
        load_edge_attributes,
    )
    from app.services.sampling.config import SamplingConfig
    from app.services.sampling.igraph_utils import (
        igraph_matrix_to_dict,
        networkx_to_igraph_with_indices,
        travel_time_matrix_igraph,
    )

    config = config or SamplingConfig()

    if config.n_nodes_preprocess < n_pairs * 1.05:
        raise ValueError(
            f"n_nodes_preprocess ({config.n_nodes_preprocess}) must be at least "
            f"5% higher than n_pairs ({n_pairs})"
        )

    logger.info("Starting research-based OD pair sampling")
    logger.info(f"Configuration: {config.model_dump()}")
    show_weight_info(config.lognorm_mu, config.lognorm_sigma)

    rng = np.random.RandomState(seed)
    edge_attr = load_edge_attributes(g)

    # Step 1: Free-flow edge weights
    edge_weight_default = "duration"
    g = assign_edge_weight(g, edge_weight_default, edge_attr, None, None)
    nodes = get_considered_nodes(g, rng, config.n_nodes_preprocess, config.node_weight_col)

    h, idx_maps = networkx_to_igraph_with_indices(g)
    nodes_ig = [idx_maps["node_nx_to_ig"][idx] for idx in nodes.index]

    # Step 2: Betweenness centrality
    logger.info("Calculating betweenness centrality...")
    bc_dict = edge_betweenness_igraph(
        h,
        config.daily_km_driven,
        weights=edge_weight_default,
        sources=nodes_ig,
        targets=nodes_ig,
    )
    betweenness = {idx_maps["edge_ig_to_nx"][idx]: bc for idx, bc in bc_dict.items()}
    betweenness = pd.Series(
        {k: betweenness.get(k, 0) for k in edge_attr.index}, name="betweenness"
    )

    # Step 3: BC-congested edge weights
    edge_weight_bc = "duration_bc"
    g = assign_edge_weight(
        g, edge_weight_bc, edge_attr, betweenness, config.betweenness_to_slowdown
    )
    duration = nx.get_edge_attributes(g, edge_weight_bc)
    h.es[edge_weight_bc] = [
        duration[idx_maps["edge_ig_to_nx"][idx]] for idx in h.get_edgelist()
    ]

    # Step 4: Travel-time matrix
    logger.info("Computing travel-time matrix...")
    t_matrix = travel_time_matrix_igraph(h, nodes_ig, edge_weight_bc)
    t_matrix_dict = igraph_matrix_to_dict(t_matrix, nodes_ig, idx_maps)

    # Step 5: Sample OD pairs
    logger.info(
        f"Sampling {config.n_origins} origins × "
        f"{config.n_destinations_per_origin} destinations per origin..."
    )
    od_pairs_dict = sample_od_pairs(
        nodes,
        rng,
        config.n_origins,
        config.lognorm_mu,
        config.lognorm_sigma,
        t_matrix_dict,
    )

    node_pairs = []
    for origin, destinations in od_pairs_dict.items():
        for destination in destinations[: config.n_destinations_per_origin]:
            node_pairs.append(NodePair(origin=origin, destination=destination))

    return node_pairs
