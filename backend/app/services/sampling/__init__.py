"""Research-based OD pair sampling subpackage.

Exposes the same public API as the original node_sampling_service module
for backward compatibility.
"""

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
from app.services.sampling.od_sampler import (
    generate_research_based_pairs,
    resample_od_destinations,
    sample_od_pairs,
    show_weight_info,
)

__all__ = [
    "SamplingConfig",
    "assign_edge_weight",
    "edge_betweenness_igraph",
    "generate_research_based_pairs",
    "get_considered_nodes",
    "igraph_matrix_to_dict",
    "load_edge_attributes",
    "networkx_to_igraph_with_indices",
    "resample_od_destinations",
    "sample_od_pairs",
    "show_weight_info",
    "travel_time_matrix_igraph",
]
