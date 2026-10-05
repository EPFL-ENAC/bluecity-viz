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
    # Free-flow time slowed down by that betweenness, per igraph edge. The
    # destinations were drawn on these times, so the baseline routes on them
    # too: the demand and the routing see the same network.
    congested_time: np.ndarray


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
    from app.services.betweenness import SOURCE_CHUNK, edge_betweenness
    from app.services.bpr import congested_speed, congested_travel_time
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
    duration_bc = congested_travel_time(
        mirror, betweenness, mirror.speed_kph, config.betweenness_to_slowdown
    )

    # 4. how far every junction is from every other one
    # In chunks of sources, for the same reason as the betweenness: igraph
    # holds the GIL for the whole call, and an area being finished in the
    # background must not freeze the requests of the map. Same matrix.
    logger.info("Computing travel-time matrix...")
    t_matrix = np.vstack(
        [
            np.asarray(
                mirror.h.distances(
                    source=nodes_ig[i : i + SOURCE_CHUNK], target=nodes_ig, weights=duration_bc
                ),
                dtype=float,
            ).reshape(-1, len(nodes_ig))
            for i in range(0, len(nodes_ig), SOURCE_CHUNK)
        ]
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
    return OdSample(pairs=pairs, nodes=nodes, betweenness=betweenness, congested_time=duration_bc)


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


# The redraw takes its random numbers from its own stream, so they do not
# repeat the ones the startup draw used from the same seed.
_REDRAW_STREAM = 1


@dataclass
class Redraw:
    """What elastic demand does to the trips of one scenario."""

    pairs: "PairArrays"  # trip i keeps origin i, only some destinations change
    moved: np.ndarray  # the indexes of the trips whose destination changed


def destination_probabilities(times: np.ndarray, weights: np.ndarray, config) -> np.ndarray:
    """P(destination | origin), one row per origin, from its travel-time row.

    The rule of the startup draw: w(d) · lognorm.pdf(t_od). A row that reaches
    nothing is all zeros.
    """
    p = weights * lognorm.pdf(times, s=config.lognorm_sigma, scale=np.exp(config.lognorm_mu))
    total = p.sum(axis=1, keepdims=True)
    return np.divide(p, total, out=np.zeros_like(p), where=total > 0)


def resample_od_destinations(
    pairs, nodes: pd.Series, mirror, base_weights, weights, config, seed: int
) -> Redraw:
    """Draw the destinations again on the modified network, trip by trip.

    Elastic demand: a traveller whose destination became far away does not
    drive there anyway, they go somewhere else. The origins and the number of
    trips per origin do not change. Each destination follows the rule of the
    startup draw, on the times of the modified network.

    The new draw is paired with the startup one, so only the trips the
    scenario touches move. With `p` the probabilities on the times the sample
    was drawn on and `p'` the ones on the scenario times, trip i keeps its
    destination d when v0 < p'(d) / p(d), and else draws one from what the
    scenario added, max(p' - p, 0). The result follows p' exactly, and it is
    the pairing that moves the fewest trips. So:

    - an origin whose times did not change keeps every destination,
    - on the untouched network nobody moves: the redraw is the startup draw,
    - the same request gives the same answer (v0, v1 come from the seed).

    Trip i has its own two numbers, row i of one draw from the seed, so a
    prefix of the trips gets the same numbers whatever the sample size.

    Args:
        pairs: PairArrays of the startup draw (or a prefix of it)
        nodes: the junction pool the startup draw used, {node id: weight}
        mirror: GraphMirror of the network
        base_weights: per-edge times the startup draw was made on
        weights: per-edge times of the modified network
        config: SamplingConfig (uses lognorm_mu / lognorm_sigma)
        seed: the area's seed

    Returns:
        Redraw: the pairs, the same length and order as the input, and the
        indexes of the trips that moved.
    """
    from app.services.routing_engine import PairArrays

    pa = PairArrays.coerce(pairs)
    origins, destinations = pa.origins, pa.destinations.copy()
    nx_to_ig = mirror.node_index
    no_move = Redraw(
        pairs=PairArrays(origins=origins, destinations=destinations),
        moved=np.empty(0, dtype=np.int64),
    )
    if len(origins) == 0:
        return no_move

    # The candidates: the pool, minus anything not in this graph.
    candidates = np.asarray([n for n in nodes.index if n in nx_to_ig], dtype=np.int64)
    candidate_ig = [nx_to_ig[int(n)] for n in candidates]
    candidate_weights = nodes.reindex(candidates).values.astype(float)
    column_of = {int(n): j for j, n in enumerate(candidates)}

    uniq, row_of_trip = np.unique(origins, return_inverse=True)
    in_graph = np.asarray([int(o) in nx_to_ig for o in uniq], dtype=bool)
    sources = [nx_to_ig[int(o)] for o in uniq[in_graph]]
    if not sources:
        return no_move

    def rows_on(times) -> np.ndarray:
        out = np.full((len(uniq), len(candidates)), np.inf)
        out[in_graph] = np.asarray(
            mirror.h.distances(source=sources, target=candidate_ig, weights=times), dtype=float
        )
        return out

    rows_before, rows_after = rows_on(base_weights), rows_on(weights)
    p_before = destination_probabilities(rows_before, candidate_weights, config)
    p_after = destination_probabilities(rows_after, candidate_weights, config)

    v = np.random.default_rng([seed, _REDRAW_STREAM]).random((len(origins), 2))
    column = np.asarray([column_of.get(int(d), -1) for d in destinations], dtype=np.int64)

    changed = in_graph & ~(rows_before == rows_after).all(axis=1)
    stuck = []
    for row in np.flatnonzero(changed):
        after = p_after[row]
        if after.sum() == 0:
            # Every destination is out of reach now: the trips stay as they were.
            stuck.append(int(uniq[row]))
            continue
        trips = np.flatnonzero(row_of_trip == row)
        before = p_before[row]
        col = column[trips]
        known = col >= 0
        keep_chance = np.zeros(len(trips))
        p_d = before[col[known]]
        keep_chance[known] = np.divide(
            after[col[known]], p_d, out=np.zeros_like(p_d), where=p_d > 0
        )
        move = v[trips, 0] >= keep_chance
        if not move.any():
            continue
        gain = np.maximum(after - before, 0.0)
        if gain.sum() == 0:
            continue
        cdf = gain.cumsum()
        cdf /= cdf[-1]
        picked = cdf.searchsorted(v[trips[move], 1], side="right")
        destinations[trips[move]] = candidates[np.minimum(picked, len(candidates) - 1)]

    if stuck:
        logger.warning(f"resample_od_destinations: {len(stuck)} origins reach nothing, kept")

    moved = np.flatnonzero(destinations != pa.destinations).astype(np.int64)
    return Redraw(pairs=PairArrays(origins=origins, destinations=destinations), moved=moved)
