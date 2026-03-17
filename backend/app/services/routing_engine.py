"""Core igraph routing engine: one-to-many Dijkstra path calculation.

Standalone functions that take explicit graph/cache parameters so they can be
called from GraphService, run_congestion_routing, or test code without a service instance.
"""

import logging
import time
from collections import defaultdict
from typing import List, Optional

from app.models.route import NodePair, Route

logger = logging.getLogger(__name__)


def group_pairs_by_origin(pairs: List[NodePair]) -> dict:
    """Group OD pairs by origin for one-to-many routing optimisation."""
    origin_groups = defaultdict(list)
    for pair in pairs:
        origin_groups[pair.origin].append((pair.destination, pair))
    return origin_groups


def build_route_edge_index(routes: List[Route]) -> dict:
    """Build inverted index: edge → list of route indices that use it."""
    edge_index: dict = {}
    for i, route in enumerate(routes):
        for j in range(len(route.path) - 1):
            key = (route.path[j], route.path[j + 1])
            edge_index.setdefault(key, []).append(i)
    return edge_index


def copy_weight_to_igraph(graph, h, idx_maps: dict, weight: str) -> None:
    """Copy a weight attribute from NetworkX graph edges into an igraph edge sequence."""
    edge_weights = []
    for edge_ig_idx in h.get_edgelist():
        edge_nx_idx = idx_maps["edge_ig_to_nx"][edge_ig_idx]
        edge_data = graph.edges[edge_nx_idx]
        edge_weights.append(edge_data.get(weight, edge_data.get("length", 1)))
    h.es[weight] = edge_weights


async def calculate_routes_igraph(
    graph,
    edge_metrics_cache: dict,
    origin_groups: dict,
    weight: str = "travel_time",
    compute_metrics: bool = True,
    prebuilt_igraph: Optional[tuple] = None,
) -> List[Route]:
    """Calculate routes using igraph one-to-many shortest paths.

    One Dijkstra call per origin covers all its destinations efficiently,
    reducing total runtime from O(pairs) to O(unique_origins) Dijkstra calls.

    Args:
        graph: NetworkX MultiDiGraph
        edge_metrics_cache: {(u,v): (travel_time, distance, elevation_gain, co2_g)}
        origin_groups: {origin → [(destination, pair_object), ...]}
        weight: Edge weight attribute to minimise
        compute_metrics: If False, return paths only (for intermediate congestion
            iterations where per-route metrics aren't needed yet)
        prebuilt_igraph: Optional (h, idx_maps) to skip graph conversion
    """
    from app.services.node_sampling_service import networkx_to_igraph_with_indices

    if prebuilt_igraph is not None:
        h, idx_maps = prebuilt_igraph
    else:
        t0 = time.time()
        h, idx_maps = networkx_to_igraph_with_indices(graph)
        logger.info(f"Graph conversion: {(time.time()-t0):.2f}s")
        if weight not in h.es.attributes():
            copy_weight_to_igraph(graph, h, idx_maps, weight)

    all_routes = []
    failed_origins = 0
    t_start = time.time()
    t_routing_pure = 0.0

    for origin_nx, dest_pairs in origin_groups.items():
        if origin_nx not in idx_maps["node_nx_to_ig"]:
            logger.warning(f"Origin {origin_nx} not found in igraph")
            failed_origins += 1
            continue

        origin_ig = idx_maps["node_nx_to_ig"][origin_nx]
        destinations_ig = []
        dest_pair_mapping = []

        for dest_nx, pair_obj in dest_pairs:
            if dest_nx in idx_maps["node_nx_to_ig"]:
                destinations_ig.append(idx_maps["node_nx_to_ig"][dest_nx])
                dest_pair_mapping.append((dest_nx, pair_obj))

        if not destinations_ig:
            failed_origins += 1
            continue

        try:
            t0 = time.time()
            paths_ig = h.get_shortest_paths(
                v=origin_ig, to=destinations_ig, weights=weight, output="vpath"
            )
            t_routing_pure += time.time() - t0

            for path_ig, (dest_nx, pair_obj) in zip(paths_ig, dest_pair_mapping):
                if not path_ig or len(path_ig) < 2:
                    continue  # disconnected

                path_nx = [idx_maps["node_ig_to_nx"][n] for n in path_ig]

                if compute_metrics:
                    travel_time = distance = elevation_gain = co2 = 0.0
                    for u, v in zip(path_nx[:-1], path_nx[1:]):
                        tt, dist, elev, co2_g = edge_metrics_cache.get(
                            (u, v), (0.0, 0.0, 0.0, 0.0)
                        )
                        travel_time += tt
                        distance += dist
                        elevation_gain += elev
                        co2 += co2_g
                    all_routes.append(Route(
                        origin=pair_obj.origin,
                        destination=pair_obj.destination,
                        path=path_nx,
                        travel_time=travel_time,
                        distance=distance,
                        elevation_gain=(elevation_gain if elevation_gain > 0 else None),
                        co2_emissions=co2,
                    ))
                else:
                    all_routes.append(Route(
                        origin=pair_obj.origin,
                        destination=pair_obj.destination,
                        path=path_nx,
                    ))

        except Exception as e:
            logger.warning(f"Failed to route from origin {origin_nx}: {e}")
            failed_origins += 1

    total_time = time.time() - t_start
    if failed_origins > 0:
        logger.warning(f"Failed to route from {failed_origins} origins")
    if total_time > 0:
        logger.info(
            f"Calculated {len(all_routes)} routes in {total_time:.2f}s "
            f"({len(all_routes)/total_time:.0f} routes/sec, igraph: {t_routing_pure:.2f}s)"
        )
    return all_routes
