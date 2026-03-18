"""BPR congestion model and betweenness centrality for road networks.

The Bureau of Public Roads (BPR) speed-reduction formula is used throughout:

    speed_cong = speed_free / (1 + BC / (lanes × betweenness_to_slowdown))

where betweenness_to_slowdown is the BC value at which speed halves (50% reduction).
All functions take explicit graph/cache parameters and have no service-layer dependencies.
"""

import logging
import random
import time
from typing import List, Optional, Tuple

from app.services.co2_calculator import CO2Calculator
from app.services.graph_helpers import count_edge_usage

logger = logging.getLogger(__name__)


def _get_lanes(data: dict) -> int:
    """Parse lane count from edge data, defaulting to 2."""
    lanes = data.get("lanes", 2)
    if isinstance(lanes, list):
        lanes = lanes[0]
    try:
        return int(lanes)
    except (ValueError, TypeError):
        return 2


def compute_betweenness(
    graph,
    bc_sample_nodes: list,
    sampling_config=None,
    label: str = "BC",
) -> Tuple[dict, list]:
    """Compute sampled edge betweenness centrality on the given graph.

    Uses a fixed random subset of nodes as sources/targets for tractable runtime.
    The same sample is reused across calls (bc_sample_nodes) to ensure consistent
    normalization when comparing baseline vs. post-modification BC.

    Returns:
        (bc_dict, sample_nodes) where bc_dict is {(u, v): bc} in vehicle-flow
        units (veh/day), and sample_nodes is the node list used (for caching).
    """
    from app.services.node_sampling_service import (
        SamplingConfig,
        edge_betweenness_igraph,
        networkx_to_igraph_with_indices,
    )

    config = sampling_config or SamplingConfig()

    t0 = time.perf_counter()
    h, idx_maps = networkx_to_igraph_with_indices(graph)
    t_convert = (time.perf_counter() - t0) * 1000

    all_nx = list(graph.nodes())
    if bc_sample_nodes:
        nodes_nx = bc_sample_nodes
        reused = True
    else:
        n = min(config.n_nodes_preprocess, len(all_nx))
        nodes_nx = random.sample(all_nx, n)
        reused = False

    nodes_ig = [
        idx_maps["node_nx_to_ig"][n]
        for n in nodes_nx
        if n in idx_maps["node_nx_to_ig"]
    ]

    t0 = time.perf_counter()
    bc_raw = edge_betweenness_igraph(
        h,
        config.daily_km_driven,
        weights="travel_time",
        sources=nodes_ig,
        targets=nodes_ig,
    )
    t_bc = (time.perf_counter() - t0) * 1000

    result = {}
    for edge_ig_key, bc in bc_raw.items():
        nx_key = idx_maps["edge_ig_to_nx"].get(edge_ig_key)
        if nx_key is not None:
            u, v, _ = nx_key
            result[(u, v)] = bc

    logger.info(
        f"[TIMING] {label} | nodes={len(nodes_ig)} (reused={reused}) | "
        f"graph_convert={t_convert:.0f}ms | bc_compute={t_bc:.0f}ms | "
        f"edges_with_bc={len(result)}"
    )
    return result, nodes_nx


def update_co2_with_congestion(
    graph, edge_bc_cache: dict, edge_co2_cache: dict, sampling_config=None
) -> None:
    """Recompute edge_co2_cache using BC-derived congested speeds (in-place).

    BPR formula: speed_cong = speed_free / (1 + BC / (lanes × betweenness_to_slowdown))

    Called once at startup so CO2/km values reflect the baseline network's
    congested operating conditions rather than free-flow speeds.
    """
    from app.services.node_sampling_service import SamplingConfig

    config = sampling_config or SamplingConfig()

    for u, v, data in graph.edges(data=True):
        bc = edge_bc_cache.get((u, v), 0.0)
        speed_free = data.get("speed_kph") or 30.0
        length = data.get("length") or 1.0
        elevation_gain = data.get("elevation_gain") or 0.0
        speed_cong = (
            speed_free / (1 + bc / (_get_lanes(data) * config.betweenness_to_slowdown))
            if bc > 0
            else speed_free
        )
        co2_g = CO2Calculator.calculate_edge_co2(
            length=length, speed_kph=speed_cong, elevation_gain=elevation_gain
        )
        length_km = length / 1000.0
        edge_co2_cache[(u, v)] = co2_g / length_km if length_km > 0 else 0.0


def write_bc_duration(graph, bc_dict: dict) -> None:
    """Write duration_bc to every graph edge using BC-derived congested speeds.

    BPR formula:
        speed_cong = speed_free / (1 + BC / (lanes × betweenness_to_slowdown))
        duration_bc = (length_km) / (speed_cong / 3.6)   [seconds]

    Used by the targeted reroute strategy (Marco's model) so affected trips
    are assigned to routes reflecting the modified network's congestion level.
    """
    from app.services.sampling.config import SamplingConfig

    config = SamplingConfig()
    for u, v, k, data in graph.edges(keys=True, data=True):
        bc = bc_dict.get((u, v), 0.0)
        speed_free = data.get("speed_kph") or 30.0
        length = data.get("length") or 1.0
        speed_cong = speed_free / (1 + bc / (_get_lanes(data) * config.betweenness_to_slowdown))
        data["duration_bc"] = (
            (length / 1000) / (speed_cong / 3.6)
            if speed_cong > 0
            else data.get("travel_time", 0)
        )


def apply_congestion_weights(graph, routes) -> None:
    """Apply congestion-based edge weights derived from measured route volumes.

    Normalises simulated route counts to daily vehicle-km, then applies BPR
    speed reduction, writing duration_bc on every edge:

        volume = count × (daily_km_driven / total_simulated_veh_m)
        speed_cong = speed_free / (1 + volume / (lanes × betweenness_to_slowdown))
        duration_bc = length_km / (speed_cong / 3.6)   [seconds]
    """
    from app.services.sampling.config import SamplingConfig

    config = SamplingConfig()
    counts = count_edge_usage(routes)

    total_veh_m = sum(
        count * next(iter(graph[u][v].values())).get("length", 0)
        for (u, v), count in counts.items()
        if graph.has_edge(u, v)
    )
    factor = (config.daily_km_driven * 1000 / total_veh_m) if total_veh_m > 0 else 1.0

    for u, v, k, data in graph.edges(keys=True, data=True):
        volume = counts.get((u, v), 0) * factor
        speed_free = data.get("speed_kph", 30)
        speed_cong = speed_free / (1 + volume / (_get_lanes(data) * config.betweenness_to_slowdown))
        length = data.get("length", 0)
        data["duration_bc"] = (
            (length / 1000) / (speed_cong / 3600)
            if speed_cong > 0
            else data.get("travel_time", 0)
        )


async def run_congestion_routing(
    graph, edge_metrics_cache: dict, pairs, n_iterations: int
) -> List:
    """Route pairs iteratively, converging toward Wardrop user equilibrium.

    At equilibrium, no driver can reduce their travel time by switching routes.
    Iteration 0 uses free-flow travel_time; subsequent iterations use
    duration_bc derived from the previous iteration's route volumes.
    igraph is built once — only edge weights change between iterations.
    Metrics are computed only on the final iteration.
    """
    from app.services.node_sampling_service import networkx_to_igraph_with_indices
    from app.services.routing_engine import (
        calculate_routes_igraph,
        copy_weight_to_igraph,
        group_pairs_by_origin,
    )

    h, idx_maps = networkx_to_igraph_with_indices(graph)
    prebuilt = (h, idx_maps)
    origin_groups = group_pairs_by_origin(pairs)

    # Iteration 0: free-flow routing (path only, no metrics yet)
    copy_weight_to_igraph(graph, h, idx_maps, "travel_time")
    routes = await calculate_routes_igraph(
        graph, edge_metrics_cache, origin_groups,
        "travel_time", compute_metrics=False, prebuilt_igraph=prebuilt,
    )

    for i in range(n_iterations):
        apply_congestion_weights(graph, routes)
        copy_weight_to_igraph(graph, h, idx_maps, "duration_bc")
        is_final = i == n_iterations - 1
        routes = await calculate_routes_igraph(
            graph, edge_metrics_cache, origin_groups,
            "duration_bc", compute_metrics=is_final, prebuilt_igraph=prebuilt,
        )

    return routes
