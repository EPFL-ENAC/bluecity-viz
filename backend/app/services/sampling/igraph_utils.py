"""Utilities for converting between NetworkX and igraph data structures."""

from typing import Dict, List, Tuple

import igraph as ig
import networkx as nx
import osmnx as ox


def networkx_to_igraph_with_indices(
    g: nx.MultiDiGraph,
) -> Tuple[ig.Graph, Dict[str, dict]]:
    """Convert a NetworkX MultiDiGraph to igraph with bidirectional index mappings.

    Returns:
        (h, idx_maps) where idx_maps contains:
            node_nx_to_ig, node_ig_to_nx  — node ID ↔ igraph vertex index
            edge_nx_to_ig, edge_ig_to_nx  — (u, v, key) ↔ igraph edge tuple
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


def travel_time_matrix_igraph(
    h: ig.Graph, nodes: List[int], weight_name: str
) -> List[List[float]]:
    """Compute all-pairs travel time matrix using igraph shortest paths."""
    return h.distances(source=nodes, target=nodes, weights=weight_name)


def igraph_matrix_to_dict(
    t_matrix: List[List[float]], nodes_ig: List[int], idx_maps: dict
) -> Dict[int, Dict[int, float]]:
    """Convert igraph distance matrix to {origin_nx_id: {dest_nx_id: travel_time}}."""
    t_matrix_dict = {}
    for row_id, t_list in zip(nodes_ig, t_matrix):
        d = {
            idx_maps["node_ig_to_nx"][col_id]: t
            for col_id, t in zip(nodes_ig, t_list)
        }
        t_matrix_dict[idx_maps["node_ig_to_nx"][row_id]] = d
    return t_matrix_dict
