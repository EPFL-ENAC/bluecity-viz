"""Build an OSM-based travel-time matrix for the Swiss Post locations.

The pipeline mirrors the one in ``backend/app/services/cvrp_service.py`` but
fixes its index-ordering bug: here the OD matrix rows/columns are ordered
EXACTLY like the input dataframe (i.e. like ``03-index_mapping.parquet``), and
each location's snap distance is recorded for the outlier forensics in
notebook 04.

Requires network access the first time (graph download via OSMnx); the graph
and matrix are cached under ``data/cache/``.
"""

import numpy as np
import pandas as pd

from . import config

GRAPH_CACHE = config.CACHE_DIR / "bern_drive.graphml"
MATRIX_CACHE = config.CACHE_DIR / "osm_matrix_seconds.npy"
SNAP_CACHE = config.CACHE_DIR / "osm_snap_distances.csv"


def _download_graph(nodes: pd.DataFrame, pad_deg: float = 0.05):
    """Download (or load cached) drive network covering all locations."""
    import osmnx as ox

    if GRAPH_CACHE.exists():
        return ox.load_graphml(GRAPH_CACHE)

    west, east = nodes.lon.min() - pad_deg, nodes.lon.max() + pad_deg
    south, north = nodes.lat.min() - pad_deg, nodes.lat.max() + pad_deg
    try:  # osmnx >= 2.0
        g = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive")
    except TypeError:  # osmnx 1.x
        g = ox.graph_from_bbox(north, south, east, west, network_type="drive")

    g = ox.add_edge_speeds(g)  # imputes maxspeed per highway type where missing
    g = ox.add_edge_travel_times(g)  # free-flow seconds per edge
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(g, GRAPH_CACHE)
    return g


def build_osm_matrix(nodes: pd.DataFrame, force: bool = False):
    """(matrix_seconds, snap_distances) for the 82 locations, matrix-ordered.

    ``nodes`` must be the dataframe from :func:`extraction.build_nodes_df`
    (sorted by matrix ``index``). Free-flow travel times — no congestion.
    """
    import igraph as ig
    import osmnx as ox

    if MATRIX_CACHE.exists() and SNAP_CACHE.exists() and not force:
        return np.load(MATRIX_CACHE), pd.read_csv(SNAP_CACHE)

    nodes = nodes.sort_values("index").reset_index(drop=True)
    assert (nodes["index"].values == np.arange(len(nodes))).all()

    g = _download_graph(nodes)
    osm_ids, snap_m = ox.distance.nearest_nodes(
        g, X=nodes.lon.values, Y=nodes.lat.values, return_dist=True
    )

    # networkx -> igraph, keeping the travel_time weights
    h = ig.Graph.from_networkx(g)
    nx_to_ig = {name: i for i, name in enumerate(h.vs["_nx_name"])}
    sources = [nx_to_ig[o] for o in osm_ids]

    # igraph requires unique vertex lists; several locations can snap to the
    # same OSM node, so compute over the unique nodes and expand — using an
    # explicit position map so row/column order stays exactly `nodes` order.
    unique = sorted(set(sources))
    pos = {v: p for p, v in enumerate(unique)}
    dist = np.asarray(h.distances(unique, unique, weights="travel_time"), dtype=float)
    take = [pos[v] for v in sources]
    matrix = dist[np.ix_(take, take)]
    matrix[~np.isfinite(matrix)] = np.nan
    np.fill_diagonal(matrix, 0.0)

    snaps = pd.DataFrame(
        {"index": nodes["index"], "uuid": nodes.uuid, "snap_dist_m": snap_m}
    )
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(MATRIX_CACHE, matrix)
    snaps.to_csv(SNAP_CACHE, index=False)
    return matrix, snaps


def demo_matrix(sp_matrix: np.ndarray, nodes: pd.DataFrame, seed: int = 42):
    """Synthetic stand-in for an OSM matrix, used when no network/graph exists.

    Planted, *known* effects — the notebook must recover all of them:
    - global factor: OSM free-flow is 1/1.15 of Swiss Post everywhere
    - lognormal noise, sigma = 5%
    - a "congested center" (2 km around the mean coordinate) where Swiss Post
      is an ADDITIONAL +25% slower than free-flow
    - 2% of pairs corrupted (mis-snapped: value replaced by a wrong pair's)

    Returns (matrix, ground_truth_dict).
    """
    from .matrixtools import haversine_m

    rng = np.random.default_rng(seed)
    n = len(sp_matrix)

    center_lat, center_lon = nodes.lat.mean(), nodes.lon.mean()
    d_center = haversine_m(
        nodes.lat.values, nodes.lon.values, center_lat, center_lon
    )
    in_center = d_center < 2000

    congestion = np.ones((n, n))
    pair_in_center = in_center[:, None] | in_center[None, :]
    congestion[pair_in_center] = 1.25

    noise = rng.lognormal(0.0, 0.05, (n, n))
    osm = sp_matrix / (1.15 * congestion * noise)

    n_corrupt = int(0.02 * n * n)
    ii = rng.integers(0, n, n_corrupt)
    jj = rng.integers(0, n, n_corrupt)
    kk = rng.integers(0, n, n_corrupt)
    osm[ii, jj] = osm[kk, jj]

    np.fill_diagonal(osm, 0.0)
    truth = {
        "global_factor_sp_over_osm": 1.15,
        "noise_sigma": 0.05,
        "congested_zone_extra": 1.25,
        "n_corrupted_pairs": n_corrupt,
        "center": (float(center_lat), float(center_lon)),
    }
    return osm, truth
