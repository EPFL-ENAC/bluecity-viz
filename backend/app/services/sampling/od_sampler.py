"""OD pair sampling using lognormal travel-time weighting."""

import logging
import math
from collections import Counter
from typing import Dict, List

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import lognorm

logger = logging.getLogger(__name__)


def show_weight_info(lognorm_mu: float, lognorm_sigma: float) -> None:
    """Log relative destination weights at representative travel times."""
    max_time = np.exp(lognorm_mu - lognorm_sigma**2)
    logger.info(f"Maximum weight at {max_time:.0f} s ({max_time / 60:.1f} min) travel time")
    times = [1, 2, 5, 10, 30, 60]
    weights = lognorm.pdf(
        [max_time] + [t * 60 for t in times], s=lognorm_sigma, scale=np.exp(lognorm_mu)
    )
    weights = weights / weights[0]
    logger.info(
        "Relative weights: " + ", ".join(f"{t} min: {w:.2f}" for t, w in zip(times, weights[1:]))
    )


def sample_od_pairs(
    nodes: pd.Series,
    rng: np.random.RandomState,
    n_origins: int,
    n_destinations: int,
    lognorm_mu: float,
    lognorm_sigma: float,
    t_matrix_dict: Dict[int, Dict[int, float]],
) -> Dict[int, List[int]]:
    """Same as ``sample_od_pairs_matrix``, with the travel times as a dict.

    Kept for the NetworkX pipeline and the scripts. The dict of dicts costs a
    million entries at 1,000 nodes, so the array form is used everywhere else.
    """
    index = list(nodes.index)
    row_of = {node: i for i, node in enumerate(index)}
    t_matrix = np.asarray(
        [[t_matrix_dict[origin][dest] for dest in index] for origin in index], dtype=float
    )
    return sample_od_pairs_matrix(
        nodes, rng, n_origins, n_destinations, lognorm_mu, lognorm_sigma, t_matrix, row_of
    )


def sample_od_pairs_matrix(
    nodes: pd.Series,
    rng: np.random.RandomState,
    n_origins: int,
    n_destinations: int,
    lognorm_mu: float,
    lognorm_sigma: float,
    t_matrix: np.ndarray,
    row_of: Dict[int, int],
) -> Dict[int, List[int]]:
    """Sample OD pairs using lognormal travel-time weighting.

    Destinations are weighted by a lognormal distribution over travel time from
    each origin. Parameters (mu=6.85, sigma=0.83) are calibrated to travel survey
    data with mode ≈ 940 s (≈ 15 min), reflecting typical urban trip lengths.

    Origins are sampled WITH replacement so high-weight nodes attract more trips.
    An origin drawn twice gets twice as many destinations. It used to overwrite
    its own entry, so 500 draws gave 382 origins and lost the extra weight.

    Args:
        nodes: Node weights indexed by NetworkX node ID
        n_origins: Number of origin draws
        n_destinations: Number of destinations per origin draw
        t_matrix: (N, N) travel times, rows and columns in ``nodes.index`` order
        row_of: {node id: row index in t_matrix}
    """
    origins = list(nodes.sample(n_origins, random_state=rng, replace=True, weights=nodes).index)

    od_pairs: Dict[int, List[int]] = {}
    failed_origins = []

    for origin, draws in Counter(origins).items():
        times = t_matrix[row_of[origin]]
        time_weights = lognorm.pdf(times, s=lognorm_sigma, scale=np.exp(lognorm_mu))
        weights = nodes * time_weights

        try:
            destinations = list(
                nodes.sample(
                    n_destinations * draws, random_state=rng, replace=True, weights=weights
                ).index
            )
            od_pairs[origin] = destinations
        except ValueError:
            failed_origins.append(origin)

    if failed_origins:
        logger.warning(
            f"Failed to sample destinations for {len(failed_origins)} origins (disconnected nodes?)"
        )

    return od_pairs


def resample_od_destinations(
    pairs,
    nodes: pd.Series,
    mirror,
    weights,
    config,
):
    """Resample destinations for each origin using travel times on the modified graph.

    Preserves origin structure (same origins, same destination count per origin)
    while choosing new destinations based on lognormal-weighted travel times
    on the modified graph, modelling elastic demand adaptation.

    Args:
        pairs: PairArrays (or a NodePair list) giving the origins and how many
            destinations each one has
        nodes: Candidate pool, pd.Series {NX node ID: weight}
        mirror: GraphMirror of the network
        weights: Per-edge travel time array of the modified network
        config: SamplingConfig (uses lognorm_mu / lognorm_sigma)

    Returns:
        PairArrays of the same length as the input.
    """
    from app.services.routing_engine import PairArrays

    pa = PairArrays.coerce(pairs)
    nx_to_ig = mirror.node_index

    # Build candidate arrays (only nodes present in igraph)
    candidate_nx_ids = [n for n in nodes.index if n in nx_to_ig]
    candidate_ig_ids = [nx_to_ig[n] for n in candidate_nx_ids]
    candidate_weights = nodes.reindex(candidate_nx_ids).values.astype(float)
    candidate_arr = np.asarray(candidate_nx_ids, dtype=np.int64)

    # Destinations per origin, in first-seen order (what the dict used to give).
    uniq, first_seen, counts = np.unique(pa.origins, return_index=True, return_counts=True)
    keep = np.argsort(first_seen)
    uniq, counts = uniq[keep], counts[keep]

    valid = np.asarray([int(o) in nx_to_ig for o in uniq], dtype=bool)
    valid_origin_nx = uniq[valid]
    valid_counts = counts[valid]
    origin_ig_ids = [nx_to_ig[int(o)] for o in valid_origin_nx]

    # Compute travel-time matrix: origins x candidates
    t_matrix = mirror.h.distances(source=origin_ig_ids, target=candidate_ig_ids, weights=weights)

    rng = np.random.RandomState()
    out_origins: List[np.ndarray] = []
    out_dests: List[np.ndarray] = []
    failed_origins = []

    def keep_original(origin_nx):
        """Fallback: this origin keeps the destinations it already had."""
        mask = pa.origins == origin_nx
        out_origins.append(pa.origins[mask])
        out_dests.append(pa.destinations[mask])

    for i, origin_nx in enumerate(valid_origin_nx):
        origin_nx = int(origin_nx)
        n_dests = int(valid_counts[i])
        times = np.array(t_matrix[i], dtype=float)
        time_weights = lognorm.pdf(times, s=config.lognorm_sigma, scale=np.exp(config.lognorm_mu))
        combined = candidate_weights * time_weights
        total = combined.sum()

        if total == 0 or not np.isfinite(total):
            failed_origins.append(origin_nx)
            keep_original(origin_nx)
            continue

        try:
            dest_indices = rng.choice(
                len(candidate_nx_ids), size=n_dests, replace=True, p=combined / total
            )
            out_origins.append(np.full(n_dests, origin_nx, dtype=np.int64))
            out_dests.append(candidate_arr[dest_indices])
        except Exception:
            failed_origins.append(origin_nx)
            keep_original(origin_nx)

    if failed_origins:
        logger.warning(
            f"resample_od_destinations: fallback to original pairs for "
            f"{len(failed_origins)} origins"
        )

    if not out_origins:
        return PairArrays(
            origins=np.empty(0, dtype=np.int64), destinations=np.empty(0, dtype=np.int64)
        )
    return PairArrays(origins=np.concatenate(out_origins), destinations=np.concatenate(out_dests))


def generate_research_based_pairs(
    g: nx.MultiDiGraph,
    n_pairs: int,
    config=None,
    seed: int = 42,
    return_nodes: bool = False,
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

    if n_pairs < 1:
        raise ValueError(f"n_pairs must be at least 1, got {n_pairs}")

    # How many origins we need to reach n_pairs. The old code passed n_pairs to
    # a check and then ignored it: the real size was n_origins x
    # n_destinations_per_origin, which is how asking for 500 pairs produced
    # 76,400 of them.
    n_destinations = config.n_destinations_per_origin
    n_origins = max(1, math.ceil(n_pairs / n_destinations))

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
    betweenness = pd.Series({k: betweenness.get(k, 0) for k in edge_attr.index}, name="betweenness")

    # Step 3: BC-congested edge weights
    edge_weight_bc = "duration_bc"
    g = assign_edge_weight(
        g, edge_weight_bc, edge_attr, betweenness, config.betweenness_to_slowdown
    )
    duration = nx.get_edge_attributes(g, edge_weight_bc)
    h.es[edge_weight_bc] = [duration[idx_maps["edge_ig_to_nx"][idx]] for idx in h.get_edgelist()]

    # Step 4: Travel-time matrix
    logger.info("Computing travel-time matrix...")
    t_matrix = travel_time_matrix_igraph(h, nodes_ig, edge_weight_bc)
    t_matrix_dict = igraph_matrix_to_dict(t_matrix, nodes_ig, idx_maps)

    # Step 5: Sample OD pairs
    logger.info(
        f"Sampling {n_pairs} OD pairs: {n_origins} origin draws × "
        f"{n_destinations} destinations per draw..."
    )
    od_pairs_dict = sample_od_pairs(
        nodes,
        rng,
        n_origins,
        n_destinations,
        config.lognorm_mu,
        config.lognorm_sigma,
        t_matrix_dict,
    )

    node_pairs = []
    for origin, destinations in od_pairs_dict.items():
        for destination in destinations:
            node_pairs.append(NodePair(origin=origin, destination=destination))
    node_pairs = node_pairs[:n_pairs]
    logger.info(f"Generated {len(node_pairs)} OD pairs from {len(od_pairs_dict)} distinct origins")

    if return_nodes:
        return node_pairs, nodes
    return node_pairs


def generate_research_based_pairs_mirror(
    mirror,
    n_pairs: int,
    config=None,
    seed: int = 42,
    return_nodes: bool = False,
):
    """Same pipeline as ``generate_research_based_pairs``, on the graph mirror.

    No NetworkX and nothing written to a shared graph, so an area cut out of
    the Swiss store can sample its own OD pairs. For the same graph and the
    same seed it draws exactly the same pairs as the NetworkX version, which
    ``tests/test_sampling_mirror.py`` checks.

    Returns a PairArrays, and the candidate node Series when `return_nodes`.
    """
    from app.services.routing_engine import PairArrays
    from app.services.sampling.betweenness import (
        considered_nodes_from_mirror,
        edge_betweenness_mirror,
    )
    from app.services.sampling.config import SamplingConfig

    config = config or SamplingConfig()

    if n_pairs < 1:
        raise ValueError(f"n_pairs must be at least 1, got {n_pairs}")

    n_destinations = config.n_destinations_per_origin
    n_origins = max(1, math.ceil(n_pairs / n_destinations))

    logger.info("Starting research-based OD pair sampling")
    logger.info(f"Configuration: {config.model_dump()}")
    show_weight_info(config.lognorm_mu, config.lognorm_sigma)

    rng = np.random.RandomState(seed)

    length = mirror.length
    lanes = mirror.lanes
    # speed_free is speed_kph when the data has it, and a 30 km/h fallback
    # otherwise. The NetworkX version reads speed_kph straight and refuses a
    # graph with holes, so on a complete graph the two are the same array.
    speed = mirror.speed_free

    # Step 1: free-flow edge weights
    duration = length / (speed / 3.6)
    nodes = considered_nodes_from_mirror(
        mirror, rng, config.n_nodes_preprocess, config.node_weight_col
    )
    nodes_ig = [mirror.node_index[int(n)] for n in nodes.index]

    # Step 2: betweenness centrality
    logger.info("Calculating betweenness centrality...")
    betweenness = edge_betweenness_mirror(
        mirror, duration, config.daily_km_driven, nodes_ig, nodes_ig
    )

    # Step 3: BC-congested edge weights
    speed_bc = speed / (1 + betweenness / lanes / config.betweenness_to_slowdown)
    reduction = (speed - speed_bc) / speed * 100
    logger.info(f"Speed reduction — Avg: {reduction.mean():.1f}%  Max: {reduction.max():.1f}%")
    duration_bc = length / (speed_bc / 3.6)
    # The NetworkX version copies these weights onto igraph keyed by (u, v),
    # so every parallel edge ends up with the last one's value. Same here.
    duration_bc_ig = duration_bc[mirror.last_of_group[mirror.uv_group]]

    # Step 4: travel-time matrix
    logger.info("Computing travel-time matrix...")
    t_matrix = np.asarray(
        mirror.h.distances(source=nodes_ig, target=nodes_ig, weights=duration_bc_ig),
        dtype=float,
    )
    row_of = {int(node): i for i, node in enumerate(nodes.index)}

    # Step 5: sample OD pairs
    logger.info(
        f"Sampling {n_pairs} OD pairs: {n_origins} origin draws × "
        f"{n_destinations} destinations per draw..."
    )
    od_pairs_dict = sample_od_pairs_matrix(
        nodes,
        rng,
        n_origins,
        n_destinations,
        config.lognorm_mu,
        config.lognorm_sigma,
        t_matrix,
        row_of,
    )

    total = sum(len(d) for d in od_pairs_dict.values())
    origins = np.empty(total, dtype=np.int64)
    destinations = np.empty(total, dtype=np.int64)
    at = 0
    for origin, dests in od_pairs_dict.items():
        stop = at + len(dests)
        origins[at:stop] = origin
        destinations[at:stop] = dests
        at = stop

    pairs = PairArrays(origins=origins[:n_pairs], destinations=destinations[:n_pairs])
    logger.info(f"Generated {len(pairs)} OD pairs from {len(od_pairs_dict)} distinct origins")

    if return_nodes:
        return pairs, nodes
    return pairs
