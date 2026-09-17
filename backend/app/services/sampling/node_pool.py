"""The junctions the model works with.

Both the demand model and the betweenness draw from one pool: the real
junctions of the network (three streets or more, so no dead end and no
mid-street node osmnx left behind), capped at `n_nodes_preprocess` because an
all-pairs travel-time matrix is quadratic.

Each junction carries a weight, which is how likely a trip is to start or end
there:

  * ``dummy``      every junction alike
  * ``population`` the residents and jobs around it, see `population_score`
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# The node weights the mirror knows. "dummy" is uniform, every junction weighs
# 1. "population" is the score of `population_score`.
NODE_WEIGHTS = ("dummy", "population")

# Weight of a node with no resident and no job. Not 0: a rural area has many
# such junctions, and a 0 would take them out of the draw completely, so a
# trip could never start at the edge of a village. 1 against up to 100 keeps
# them rare.
POPULATION_SCORE_FLOOR = 1.0

# A node needs this many streets to count as a junction.
MIN_STREET_COUNT = 3


def population_score(residents, jobs_fte) -> np.ndarray:
    """Node weight from its residents and jobs, from 1 to 100.

    ``score = 100 · (rank_pct(residents) + rank_pct(jobs_fte)) / 2``, so a
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


def junction_pool(
    mirror,
    rng: np.random.RandomState,
    max_nodes: int,
    node_weight_col: str = "dummy",
) -> pd.Series:
    """The junctions of this area and their weights, as {node id: weight}.

    Drawn down to `max_nodes` uniformly, whatever the weighting: the pool only
    decides which junctions the travel-time matrix covers. The weight itself
    is applied once, later, when the origins and destinations are drawn.
    Weighting the pool too would count it twice, and pandas refuses a skewed
    draw without replacement.
    """
    if node_weight_col not in NODE_WEIGHTS:
        raise ValueError(
            f"node_weight_col={node_weight_col!r} is not known on the graph mirror, "
            f"use one of {NODE_WEIGHTS}"
        )

    keep = mirror.street_count >= MIN_STREET_COUNT
    if node_weight_col == "population":
        weights = population_score(mirror.residents[keep], mirror.jobs_fte[keep])
    else:
        weights = 1
    pool = pd.Series(
        weights,
        index=pd.Index(mirror.node_ids[keep], name="osmid"),
        name=node_weight_col,
    )
    logger.info(f"{len(pool):,} junctions available for sampling.")

    if len(pool) > max_nodes:
        pool = pool.sample(max_nodes, random_state=rng, replace=False)
        logger.info(f"Sampled {max_nodes:,} junctions for processing.")

    return pool
