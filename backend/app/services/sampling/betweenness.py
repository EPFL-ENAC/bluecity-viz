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
    """Assign travel-time edge weights, optionally applying BPR congestion.

    BPR speed-reduction formula (when betweenness is provided):
        speed_cong = speed_free / (1 + BC / (lanes × betweenness_to_slowdown))

    A BC value equal to betweenness_to_slowdown causes a 50% speed reduction.
    """
    if betweenness is not None and betweenness_to_slowdown:
        speed_kph_new = edge_attr["speed_kph"] / (
            1 + betweenness / edge_attr["lanes"] / betweenness_to_slowdown
        )
        speed_reduction = (edge_attr["speed_kph"] - speed_kph_new) / edge_attr["speed_kph"] * 100
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
        # The pool is drawn uniformly: it only spreads the junctions of the
        # travel time matrix. The population score weighs the origins and the
        # destinations later, once. Weighting the pool too would count it
        # twice, and pandas refuses a skewed draw without replacement.
        pool_weights = n if node_weight_col == "dummy" else None
        n = n.sample(max_nodes, random_state=rng, replace=False, weights=pool_weights)
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


# The node weights the mirror knows. "dummy" is uniform, every junction weighs
# 1. "population" is the score of `population_score`.
MIRROR_NODE_WEIGHTS = ("dummy", "population")

# Weight of a node with no resident and no job. Not 0: a rural area has many
# such junctions, and a 0 would take them out of the draw completely, so a
# trip could never start at the edge of a village. 1 against up to 100 keeps
# them rare.
POPULATION_SCORE_FLOOR = 1.0


def population_score(residents, jobs_fte) -> np.ndarray:
    """Node weight from its residents and jobs, from 1 to 100.

    ``node_coef = 100 * (rank_pct(residents) + rank_pct(jobs_fte)) / 2``, so a
    node at the 75th percentile of residents and the 85th of jobs scores 80.
    The ranks are over the nodes given, which is one area: the score says
    "busy for this area", not "busy for Switzerland".

    Ties share their average rank (pandas default). A count of 0 ranks 0, not
    the average rank of all the zeros: in a town half the junctions have no
    job at all, and they would otherwise get a quarter of the top weight.
    The score then never goes under ``POPULATION_SCORE_FLOOR``.
    """
    residents = pd.Series(np.asarray(residents, dtype=np.float64))
    jobs_fte = pd.Series(np.asarray(jobs_fte, dtype=np.float64))
    if residents.empty:
        return np.empty(0, dtype=np.float64)

    def rank_pct(values: pd.Series) -> np.ndarray:
        ranks = values.rank(pct=True).to_numpy()
        return np.where(values.to_numpy() > 0, ranks, 0.0)

    score = 100.0 * (rank_pct(residents) + rank_pct(jobs_fte)) / 2.0
    return np.maximum(score, POPULATION_SCORE_FLOOR)


def considered_nodes_from_mirror(
    mirror,
    rng: np.random.RandomState,
    max_nodes: int,
    node_weight_col: str,
) -> pd.Series:
    """Same node pool as ``get_considered_nodes``, read from the graph mirror.

    The mirror keeps the nodes in NetworkX order, so the filtered Series has
    the same index order as the GeoDataFrame the NetworkX version builds, and
    ``sample`` draws exactly the same nodes for the same seed.

    The mirror does not carry arbitrary node attributes, so only the weights
    of ``MIRROR_NODE_WEIGHTS`` exist: "dummy" (uniform) and "population"
    (residents and jobs, see ``population_score``). The score is ranked over
    all the junctions, and the pool is drawn uniformly from them.
    """
    if node_weight_col not in MIRROR_NODE_WEIGHTS:
        raise ValueError(
            f"node_weight_col={node_weight_col!r} is not known on the graph mirror, "
            f"use one of {MIRROR_NODE_WEIGHTS}"
        )

    keep = mirror.street_count >= 3
    if node_weight_col == "population":
        weights = population_score(mirror.residents[keep], mirror.jobs_fte[keep])
    else:
        weights = 1
    n = pd.Series(
        weights,
        index=pd.Index(mirror.node_ids[keep], name="osmid"),
        name=node_weight_col,
    )
    logger.info(f"{len(n):,} nodes available for sampling.")

    if len(n) > max_nodes:
        # The pool is drawn uniformly: it only spreads the junctions of the
        # travel time matrix. The population score weighs the origins and the
        # destinations later, once. Weighting the pool too would count it
        # twice, and pandas refuses a skewed draw without replacement.
        pool_weights = n if node_weight_col == "dummy" else None
        n = n.sample(max_nodes, random_state=rng, replace=False, weights=pool_weights)
        logger.info(f"Sampled {max_nodes:,} nodes for processing.")

    return n


def edge_betweenness_mirror(
    mirror,
    weights: np.ndarray,
    expected_km_driven: float,
    sources: List[int],
    targets: List[int],
) -> np.ndarray:
    """``edge_betweenness_igraph`` on the mirror, as a per-edge array.

    Same single igraph call and same normalisation, so the numbers match the
    NetworkX version bit for bit.

    One quirk is kept on purpose: the old code stored the result in a dict
    keyed by (u, v), so among parallel edges only the last one kept its value
    and the others read back as 0. Changing that would move every OD pair of
    the existing Lausanne sample, so it stays until we decide to resample.
    """
    bc_result = mirror.h.edge_betweenness(True, None, weights, sources, targets)

    raw = np.asarray(bc_result, dtype=np.float64)
    total_sum = float(np.dot(raw, mirror.length))
    # A network where nothing is on a shortest path: nothing to scale, and the
    # division would raise.
    if total_sum <= 0:
        return np.zeros(mirror.n_edges, dtype=np.float64)
    factor = expected_km_driven * 1_000 / total_sum

    out = np.zeros(mirror.n_edges, dtype=np.float64)
    last = mirror.last_of_group
    out[last] = raw[last] * factor
    return out
