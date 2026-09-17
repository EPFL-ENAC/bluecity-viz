"""Where the trips go: drawing the origin-destination sample.

The tool does not know real traffic counts, so it builds a synthetic demand:
a fixed set of trips, drawn once, reused by every scenario. Two scenarios are
comparable because they move the same trips over a different network.

The draw, in one sentence: junctions are picked as origins in proportion to
their weight, and each origin picks its destinations in proportion to how
plausible a trip of that length is, on a network that already carries traffic.

    origin      ~ w(o)
    destination ~ w(d) · lognorm.pdf(t_od ; sigma, exp(mu))

where `w` is the junction weight (uniform, or residents and jobs) and `t_od`
is the travel time under congestion. The lognormal is the trip-length
distribution of the Swiss travel survey: few very short trips, a peak around
eight minutes, a long tail.

The set is drawn once at startup, at `OD_PAIRS_MAX` pairs. A request asking
for N pairs gets the first N: the origin draws are in random order, so a
prefix is itself a fair sample, and a result at 20,000 pairs is a subset of
the one at 76,400 rather than a different experiment.
"""

import logging
import math
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import lognorm

if TYPE_CHECKING:
    from app.services.routing_engine import PairArrays

logger = logging.getLogger(__name__)


@dataclass
class OdSample:
    """What one draw produces, and what the area keeps of it."""

    pairs: "PairArrays"
    nodes: pd.Series  # the junction pool, {node id: weight}
    betweenness: np.ndarray  # per igraph edge, veh/day, over that pool


def show_weight_info(lognorm_mu: float, lognorm_sigma: float) -> None:
    """Log the trip-length distribution the destinations are drawn from."""
    mode = np.exp(lognorm_mu - lognorm_sigma**2)
    logger.info(f"Most likely trip: {mode:.0f} s ({mode / 60:.1f} min) of travel time")
    times = [1, 2, 5, 10, 30, 60]
    weights = lognorm.pdf(
        [mode] + [t * 60 for t in times], s=lognorm_sigma, scale=np.exp(lognorm_mu)
    )
    weights = weights / weights[0]
    logger.info(
        "Relative weights: " + ", ".join(f"{t} min: {w:.2f}" for t, w in zip(times, weights[1:]))
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
    """Draw the origins, then each origin's destinations.

    Origins are drawn WITH replacement, so a heavy junction attracts more
    trips: an origin drawn twice gets twice as many destinations.

    Args:
        nodes: junction weights, indexed by node id
        n_origins: number of origin draws
        n_destinations: destinations per origin draw
        t_matrix: (N, N) travel times, rows and columns in ``nodes.index`` order
        row_of: {node id: row index in t_matrix}

    Returns:
        {origin: [destination, ...]}, in the order the origins were first drawn.
    """
    origins = list(nodes.sample(n_origins, random_state=rng, replace=True, weights=nodes).index)

    od_pairs: Dict[int, List[int]] = {}
    failed_origins = []

    for origin, draws in Counter(origins).items():
        times = t_matrix[row_of[origin]]
        time_weights = lognorm.pdf(times, s=lognorm_sigma, scale=np.exp(lognorm_mu))
        weights = nodes * time_weights

        try:
            od_pairs[origin] = list(
                nodes.sample(
                    n_destinations * draws, random_state=rng, replace=True, weights=weights
                ).index
            )
        except ValueError:
            # Every destination is unreachable from here, so every weight is 0.
            failed_origins.append(origin)

    if failed_origins:
        logger.warning(
            f"Failed to sample destinations for {len(failed_origins)} origins (disconnected nodes?)"
        )

    return od_pairs


def generate_research_based_pairs_mirror(
    mirror,
    n_pairs: int,
    config=None,
    seed: int = 42,
    betweenness: Optional[np.ndarray] = None,
) -> OdSample:
    """Draw `n_pairs` origin-destination pairs on a graph mirror.

    Five steps:
      1. the junction pool and its weights
      2. betweenness of the network, in veh/day
      3. the travel times that betweenness implies, through the BPR formula:
         a trip does not choose its destination on an empty city
      4. the travel-time matrix over the pool, on those congested times
      5. the draw itself, see the module docstring

    Step 2 is the expensive one and depends on the pool only, which is the
    same for every weighting of one area: pass `betweenness` from an earlier
    draw to skip it.
    """
    from app.services.betweenness import edge_betweenness
    from app.services.bpr import congested_speed
    from app.services.sampling.config import SamplingConfig
    from app.services.sampling.node_pool import junction_pool

    config = config or SamplingConfig()

    if n_pairs < 1:
        raise ValueError(f"n_pairs must be at least 1, got {n_pairs}")

    n_destinations = config.n_destinations_per_origin
    n_origins = max(1, math.ceil(n_pairs / n_destinations))

    logger.info("Starting research-based OD pair sampling")
    logger.info(f"Configuration: {config.model_dump()}")
    show_weight_info(config.lognorm_mu, config.lognorm_sigma)

    rng = np.random.RandomState(seed)

    # 1. the junctions trips can start and end at
    nodes = junction_pool(mirror, rng, config.n_nodes_preprocess, config.node_weight_col)
    nodes_ig = [mirror.node_index[int(n)] for n in nodes.index]

    # 2. how much traffic the structure of the network puts on each street
    if betweenness is None:
        logger.info("Calculating betweenness centrality...")
        betweenness = edge_betweenness(
            mirror, mirror.travel_time, nodes_ig, config.daily_km_driven, label="sampling BC"
        )

    # 3. the travel times that traffic implies
    speed_bc = congested_speed(
        mirror, betweenness, mirror.speed_kph, config.betweenness_to_slowdown
    )
    reduction = (mirror.speed_kph - speed_bc) / mirror.speed_kph * 100
    logger.info(f"Speed reduction — Avg: {reduction.mean():.1f}%  Max: {reduction.max():.1f}%")
    duration_bc = mirror.length / (speed_bc / 3.6)

    # 4. how far every junction is from every other one
    logger.info("Computing travel-time matrix...")
    t_matrix = np.asarray(
        mirror.h.distances(source=nodes_ig, target=nodes_ig, weights=duration_bc), dtype=float
    )
    row_of = {int(node): i for i, node in enumerate(nodes.index)}

    # 5. the draw
    logger.info(
        f"Sampling {n_pairs} OD pairs: {n_origins} origin draws × "
        f"{n_destinations} destinations per draw..."
    )
    od_pairs = sample_od_pairs_matrix(
        nodes,
        rng,
        n_origins,
        n_destinations,
        config.lognorm_mu,
        config.lognorm_sigma,
        t_matrix,
        row_of,
    )

    pairs = _flatten(od_pairs, n_pairs)
    logger.info(f"Generated {len(pairs)} OD pairs from {len(od_pairs)} distinct origins")
    return OdSample(pairs=pairs, nodes=nodes, betweenness=betweenness)


def _flatten(od_pairs: Dict[int, List[int]], n_pairs: int):
    """{origin: [destination]} to two flat arrays, cut to n_pairs."""
    # Lazy: models.route imports sampling.config, and routing_engine imports
    # models.route, so a top-level import here would be circular.
    from app.services.routing_engine import PairArrays

    total = sum(len(d) for d in od_pairs.values())
    origins = np.empty(total, dtype=np.int64)
    destinations = np.empty(total, dtype=np.int64)
    at = 0
    for origin, dests in od_pairs.items():
        stop = at + len(dests)
        origins[at:stop] = origin
        destinations[at:stop] = dests
        at = stop
    return PairArrays(origins=origins[:n_pairs], destinations=destinations[:n_pairs])


def resample_od_destinations(pairs, nodes: pd.Series, mirror, weights, config, seed: int):
    """Draw new destinations for the same origins, on the modified network.

    Elastic demand: a traveller whose destination became far away does not
    drive there anyway, they go somewhere else. The origins and the number of
    trips per origin do not change; each destination is drawn again with the
    same rule as the initial sample, on the travel times of the modified
    network.

    Args:
        pairs: PairArrays giving the origins and how many trips each one has
        nodes: the junction pool, {node id: weight}
        mirror: GraphMirror of the network
        weights: per-edge travel time of the modified network
        config: SamplingConfig (uses lognorm_mu / lognorm_sigma)
        seed: the area's seed, so the same request gives the same answer

    Returns:
        PairArrays, the same length as the input.
    """
    from app.services.routing_engine import PairArrays

    pa = PairArrays.coerce(pairs)
    nx_to_ig = mirror.node_index

    # The candidates: the pool, minus anything not in this graph.
    candidate_nx_ids = [n for n in nodes.index if n in nx_to_ig]
    candidate_ig_ids = [nx_to_ig[n] for n in candidate_nx_ids]
    candidate_weights = nodes.reindex(candidate_nx_ids).values.astype(float)
    candidate_arr = np.asarray(candidate_nx_ids, dtype=np.int64)

    # Trips per origin, in first-seen order (what the dict used to give).
    uniq, first_seen, counts = np.unique(pa.origins, return_index=True, return_counts=True)
    keep = np.argsort(first_seen)
    uniq, counts = uniq[keep], counts[keep]

    valid = np.asarray([int(o) in nx_to_ig for o in uniq], dtype=bool)
    valid_origin_nx = uniq[valid]
    valid_counts = counts[valid]
    origin_ig_ids = [nx_to_ig[int(o)] for o in valid_origin_nx]

    t_matrix = mirror.h.distances(source=origin_ig_ids, target=candidate_ig_ids, weights=weights)

    rng = np.random.RandomState(seed)
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

        dest_indices = rng.choice(
            len(candidate_nx_ids), size=n_dests, replace=True, p=combined / total
        )
        out_origins.append(np.full(n_dests, origin_nx, dtype=np.int64))
        out_dests.append(candidate_arr[dest_indices])

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
