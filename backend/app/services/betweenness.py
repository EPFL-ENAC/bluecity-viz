"""Edge betweenness centrality, in vehicles per day.

Betweenness answers "how much traffic would this street carry if everybody
drove the shortest path between every pair of junctions". It is a property of
the network alone: it does not look at the OD sample, which is why the app
computes it once per graph and shares it across OD samples.

Two things make the raw igraph number usable:

  * **A node sample.** Betweenness over every pair of the 4,771 Lausanne nodes
    costs minutes. It is computed over the junction pool the OD sampler draws
    (`sampling.node_pool`), a few hundred to a thousand real junctions, which
    is the same population the demand model uses.
  * **A normalisation.** Raw betweenness counts shortest paths, a number with
    no unit. Scaling it so that ``Σ bc·length = daily_km_driven`` turns it into
    veh/day, the unit the BPR congestion formula and the map legend expect.

The result is one value per igraph edge id. Parallel edges each keep their own.
"""

import logging
import time
from typing import List, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Betweenness is computed in chunks of source nodes so a single igraph call
# does not hold the GIL for too long. python-igraph never releases it, so an
# uninterrupted call of 500 ms freezes every other request for 500 ms.
# Betweenness is a sum over (source, target) pairs and the targets are the
# whole sample in every chunk, so chunking the sources and adding the results
# gives exactly the same values.
# 50 sources per chunk measured best: 20 was 10 % slower overall without
# cutting the worst latency spike, which comes from elsewhere (numpy and
# orjson also hold the GIL).
SOURCE_CHUNK = 50


def edge_betweenness(
    mirror,
    weights: np.ndarray,
    sample_vertices: Sequence[int],
    daily_km_driven: float,
    label: str = "BC",
) -> np.ndarray:
    """Sampled edge betweenness on the mirror, normalised to veh/day.

        bc_raw[e] = number of shortest (s, t) paths through e, over the sample
        bc[e]     = bc_raw[e] · daily_km_driven · 1000 / Σ(bc_raw · length)

    `weights` is the per-edge cost the shortest paths minimise: free-flow
    travel time for the baseline, the scenario's travel time for a modified
    network. Pass the same `sample_vertices` every time, or two results are
    not comparable.
    """
    t0 = time.perf_counter()
    vertices: List[int] = list(sample_vertices)
    raw = np.zeros(mirror.n_edges, dtype=np.float64)

    for start in range(0, len(vertices), SOURCE_CHUNK):
        chunk = vertices[start : start + SOURCE_CHUNK]
        raw += np.asarray(
            mirror.h.edge_betweenness(True, None, weights, chunk, vertices), dtype=np.float64
        )

    total_veh_m = float(np.dot(raw, mirror.length))
    # A network where nothing is on a shortest path: nothing to scale.
    factor = (daily_km_driven * 1000.0 / total_veh_m) if total_veh_m > 0 else 1.0

    logger.debug(
        "[TIMING] %s | nodes=%d | chunks=%d | %.0f ms",
        label,
        len(vertices),
        (len(vertices) + SOURCE_CHUNK - 1) // SOURCE_CHUNK,
        (time.perf_counter() - t0) * 1000,
    )
    return raw * factor
