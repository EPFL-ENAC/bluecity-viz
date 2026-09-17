"""Betweenness centrality computation and edge weight assignment for road networks."""

import logging
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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
