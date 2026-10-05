"""The junctions the model works with.

Both the demand model and the betweenness draw from one pool: the real
junctions of the network (three streets or more, so no dead end and no
mid-street node osmnx left behind), capped at `n_nodes_preprocess` because an
all-pairs travel-time matrix is quadratic.

Each junction carries two weights: how likely a trip is to start there (its
origin weight) and to end there (its destination weight).

  * ``dummy``           every junction alike, at both ends
  * ``population``      the residents and jobs around it, the same at both
                        ends ("Daily average" in the UI), see `population_score`
  * ``weekday_morning`` residents at the origin, jobs at the destination
  * ``weekday_evening`` jobs at the origin, residents at the destination
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# The node weights the mirror knows. "dummy" is uniform, every junction weighs
# 1. The others are scores of `population_score`, see RESIDENT_SHARE.
NODE_WEIGHTS = ("dummy", "population", "weekday_morning", "weekday_evening")

# Share of the residents rank in the score, at the (origin, destination). The
# jobs rank takes the rest. The morning goes from home to work, the evening
# back, and the daily average is the mean of the two.
RESIDENT_SHARE = {
    "population": (0.5, 0.5),
    "weekday_morning": (1.0, 0.0),
    "weekday_evening": (0.0, 1.0),
}

# Weight of a node with no resident and no job. Not 0: a rural area has many
# such junctions, and a 0 would take them out of the draw completely, so a
# trip could never start at the edge of a village. 1 against up to 100 keeps
# them rare.
POPULATION_SCORE_FLOOR = 1.0

# A node needs this many streets to count as a junction.
MIN_STREET_COUNT = 3


def population_score(residents, jobs_fte, resident_share: float = 0.5) -> np.ndarray:
    """Node weight from its residents and jobs, from 1 to 100.

    ``score = 100 · (a · rank_pct(residents) + (1 - a) · rank_pct(jobs_fte))``
    with ``a = resident_share``. At the default 0.5 a node at the 75th
    percentile of residents and the 85th of jobs scores 80; at 1 the score is
    the residents rank alone, at 0 the jobs rank alone. The ranks are over
    the nodes given, which is one area: the score says "busy for this area",
    not "busy for Switzerland".

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

    a = resident_share
    score = 100.0 * (a * rank_pct(residents) + (1.0 - a) * rank_pct(jobs_fte))
    return np.maximum(score, POPULATION_SCORE_FLOOR)


def junction_pool(
    mirror,
    rng: np.random.RandomState,
    max_nodes: int,
    node_weight_col: str = "dummy",
) -> pd.DataFrame:
    """The junctions of this area and their weights.

    One row per junction, indexed by node id, with two columns: ``origin``
    and ``destination``, the weight of the junction at each end of a trip.

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
    index = pd.Index(mirror.node_ids[keep], name="osmid")
    if node_weight_col == "dummy":
        pool = pd.DataFrame({"origin": 1.0, "destination": 1.0}, index=index)
    else:
        residents, jobs = mirror.residents[keep], mirror.jobs_fte[keep]
        at_origin, at_destination = RESIDENT_SHARE[node_weight_col]
        pool = pd.DataFrame(
            {
                "origin": population_score(residents, jobs, at_origin),
                "destination": population_score(residents, jobs, at_destination),
            },
            index=index,
        )
    logger.info(f"{len(pool):,} junctions available for sampling.")

    if len(pool) > max_nodes:
        pool = pool.sample(max_nodes, random_state=rng, replace=False)
        logger.info(f"Sampled {max_nodes:,} junctions for processing.")

    return pool
