"""NetworkX helpers the CVRP solver needs.

The routing model works on the igraph mirror and never touches NetworkX
(see ``graph_mirror.py``). The CVRP solver still works on a private copy of
the NetworkX graph, so the two helpers it needs live here rather than in the
routing layer.
"""

from typing import Dict, List, Tuple

import igraph as ig
import networkx as nx

from app.models.route import EdgeModification
from app.services.co2_calculator import CO2Calculator


def networkx_to_igraph_with_indices(
    g: nx.MultiDiGraph,
) -> Tuple[ig.Graph, Dict[str, dict]]:
    """Convert a NetworkX MultiDiGraph to igraph with bidirectional index mappings.

    Returns:
        (h, idx_maps) where idx_maps contains:
            node_nx_to_ig, node_ig_to_nx  — node ID ↔ igraph vertex index
            edge_nx_to_ig, edge_ig_to_nx  — (u, v, key) ↔ igraph edge tuple
    """
    nx.set_edge_attributes(
        g, {(u, v, k): (u, v, k) for u, v, k in g.edges(keys=True)}, name="nx_edge_id"
    )
    h = ig.Graph.from_networkx(g)

    idx_maps = {
        "node_nx_to_ig": {a: b for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "node_ig_to_nx": {b: a for a, b in zip(h.vs()["_nx_name"], h.vs.indices)},
        "edge_nx_to_ig": {a: b for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
        "edge_ig_to_nx": {b: a for a, b in zip(h.es()["nx_edge_id"], h.get_edgelist())},
    }
    return h, idx_maps


def apply_edge_modifications(g: nx.MultiDiGraph, modifications: List[EdgeModification]) -> None:
    """Apply edge modifications in place, on a graph the caller owns.

    The CVRP solver calls this on a private copy it throws away after the
    solve, so there is no rollback: a removed edge is really removed and a
    speed limit is written on the edge with its travel time and CO2.
    """
    for mod in modifications:
        if not g.has_edge(mod.u, mod.v):
            continue

        if mod.action == "remove":
            for key in list(g[mod.u][mod.v].keys()):
                g.remove_edge(mod.u, mod.v, key=key)

        elif mod.action == "modify" and mod.speed_kph is not None:
            for key in list(g[mod.u][mod.v].keys()):
                data = g[mod.u][mod.v][key]
                length = data.get("length", 0)
                data["speed_kph"] = mod.speed_kph
                data["travel_time"] = length / (mod.speed_kph / 3.6)
                data["co2_g"] = CO2Calculator.calculate_edge_co2(
                    length=length,
                    speed_kph=mod.speed_kph,
                    elevation_gain=data.get("elevation_gain", 0),
                )
