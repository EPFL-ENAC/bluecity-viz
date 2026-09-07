"""Graph helper functions for geometry, metrics, edge statistics, and graph serialization."""

import logging
import time
from typing import List, Optional, Tuple

import numpy as np

from app.models.route import (
    EdgeModification,
    GraphData,
    GraphEdge,
    PathGeometry,
)
from app.services.co2_calculator import CO2Calculator

logger = logging.getLogger(__name__)


def get_edge_data(graph, u: int, v: int) -> dict:
    """Get edge data handling MultiGraph vs Graph."""
    edge_data_dict = graph.get_edge_data(u, v)
    if not edge_data_dict:
        return {}
    if isinstance(edge_data_dict, dict) and 0 in edge_data_dict:
        return edge_data_dict[0]
    return edge_data_dict


def build_path_geometry(graph, path: List[int]) -> PathGeometry:
    """Build geometry for a path using actual road geometries."""
    if not graph or not path or len(path) < 2:
        return PathGeometry(coordinates=[])

    coordinates = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = graph.get_edge_data(u, v)
        if edge_data and "geometry" in edge_data:
            coords = list(edge_data["geometry"].coords)
            start_idx = 0 if i == 0 else 1
            coordinates.extend([[lon, lat] for lon, lat in coords[start_idx:]])
        else:
            if i == 0:
                coordinates.append([graph.nodes[u]["x"], graph.nodes[u]["y"]])
            coordinates.append([graph.nodes[v]["x"], graph.nodes[v]["y"]])

    return PathGeometry(coordinates=coordinates)


def calculate_route_metrics(graph, path: List[int]) -> dict:
    """Calculate travel time, distance, elevation gain, and CO2."""
    if not graph or not path or len(path) < 2:
        return {
            "travel_time": None,
            "distance": None,
            "elevation_gain": None,
            "co2_emissions": None,
            "edges_data": [],
        }

    travel_time = distance = elevation_gain = co2_emissions = 0.0
    edges_data = []

    for u, v in zip(path[:-1], path[1:]):
        edge_data = get_edge_data(graph, u, v)
        if not edge_data:
            continue

        # Basic metrics
        t = edge_data.get("travel_time", 0)
        d = edge_data.get("length", 0)
        travel_time += t
        distance += d

        # Elevation (use pre-computed if available)
        e_gain = edge_data.get("elevation_gain")
        if e_gain is None:
            e_gain = 0.0
            if "elevation" in graph.nodes[u] and "elevation" in graph.nodes[v]:
                diff = graph.nodes[v]["elevation"] - graph.nodes[u]["elevation"]
                if diff > 0:
                    e_gain = diff

        if e_gain > 0:
            elevation_gain += e_gain

        # CO2 (use pre-computed if available)
        c = edge_data.get("co2_g")
        speed_kph = edge_data.get("speed_kph")

        if c is None:
            c = CO2Calculator.calculate_edge_co2(
                length=d,
                speed_kph=speed_kph,
                elevation_gain=e_gain,
                travel_time=t,
            )

        co2_emissions += c

        # Maintain edges_data structure but add CO2
        edges_data.append(
            {
                "travel_time": t,
                "speed_kph": speed_kph,
                "elevation_gain": e_gain,
                "co2_g": c,
            }
        )

    return {
        "travel_time": travel_time,
        "distance": distance,
        "elevation_gain": (elevation_gain if elevation_gain > 0 else None),
        "co2_emissions": co2_emissions,
        "edges_data": edges_data,
    }


def calculate_edge_co2(graph, u: int, v: int) -> Optional[float]:
    """Calculate CO2 for a single edge."""
    edge_data = get_edge_data(graph, u, v)
    if not edge_data:
        return None

    edge_time = edge_data.get("travel_time", 0)
    edge_len = edge_data.get("length", 0)
    speed_kph = (edge_len / 1000) / (edge_time / 3600) if edge_time > 0 and edge_len > 0 else None

    edge_elev = 0.0
    if u in graph.nodes and v in graph.nodes:
        if "elevation" in graph.nodes[u] and "elevation" in graph.nodes[v]:
            elev_diff = graph.nodes[v]["elevation"] - graph.nodes[u]["elevation"]
            if elev_diff > 0:
                edge_elev = elev_diff

    return CO2Calculator.calculate_edge_co2(
        length=edge_len, speed_kph=speed_kph, elevation_gain=edge_elev, travel_time=edge_time
    )


def build_edge_usage_rows(
    mirror,
    counts: np.ndarray,
    total_routes: int,
    co2_per_km: np.ndarray,
    original_counts: Optional[np.ndarray] = None,
    betweenness: Optional[np.ndarray] = None,
    delta_betweenness: Optional[np.ndarray] = None,
) -> List[dict]:
    """Build the per-(u, v) usage rows of a recalculate response.

    Every array is indexed by (u, v) group, see GraphMirror.uv_group. Only
    groups actually used by a route produce a row. Values are rounded here:
    the payload holds about 6,400 rows twice, and full float precision adds
    around 30 % of bytes that no one reads.
    """
    t0 = time.perf_counter()
    used = np.flatnonzero(counts > 0)
    if len(used) == 0:
        return []

    freq = counts[used] / total_routes if total_routes > 0 else np.zeros(len(used))
    order = np.argsort(-freq, kind="stable")
    used = used[order]
    freq = freq[order]

    us = mirror.uv_u[used]
    vs = mirror.uv_v[used]
    cnt = counts[used].astype(np.int64)
    co2 = np.round(co2_per_km[used], 2)
    freq_r = np.round(freq, 6)

    delta_cnt = delta_freq = None
    if original_counts is not None:
        delta_cnt = (counts[used] - original_counts[used]).astype(np.int64)
        orig_freq = original_counts[used] / total_routes if total_routes > 0 else 0.0
        delta_freq = np.round(freq - orig_freq, 6)

    bc = np.round(betweenness[used], 2) if betweenness is not None else None
    d_bc = np.round(delta_betweenness[used], 2) if delta_betweenness is not None else None

    rows = [
        {
            "u": int(us[i]),
            "v": int(vs[i]),
            "count": int(cnt[i]),
            "frequency": float(freq_r[i]),
            "delta_count": int(delta_cnt[i]) if delta_cnt is not None else None,
            "delta_frequency": float(delta_freq[i]) if delta_freq is not None else None,
            "co2_per_km": float(co2[i]),
            "betweenness_centrality": float(bc[i]) if bc is not None else None,
            "delta_betweenness": float(d_bc[i]) if d_bc is not None else None,
        }
        for i in range(len(used))
    ]

    logger.debug(
        "[TIMING] edge usage rows | %d rows | %.1f ms", len(rows), (time.perf_counter() - t0) * 1000
    )
    return rows


# ── Edge Modification Helpers ─────────────────────────────────────────────────


def modifications_to_arrays(
    mirror,
    base_travel_time: np.ndarray,
    base_speed: np.ndarray,
    base_co2_per_km: np.ndarray,
    base_co2_g: np.ndarray,
    modifications: List[EdgeModification],
) -> Tuple[list, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Turn edge modifications into per-request weight arrays.

    Nothing is written to the shared graph. A removed edge gets a travel time
    of +inf, which igraph treats as "do not use", so there is no rollback and
    two requests cannot see each other's changes.

    Returns:
        (applied, travel_time, speed, co2_per_km, co2_g, blocked, changed_edge_ids)
    """
    travel_time = base_travel_time.copy()
    speed = base_speed.copy()
    co2_per_km = base_co2_per_km.copy()
    co2_g = base_co2_g.copy()
    blocked = np.zeros(mirror.n_edges, dtype=bool)

    applied: list = []
    changed: List[int] = []

    for mod in modifications:
        ids = mirror.edge_ids_for(mod.u, mod.v)
        if ids is None:
            continue

        if mod.action == "remove":
            blocked[ids] = True
            travel_time[ids] = np.inf
            applied.append(mod)
            changed.extend(int(i) for i in ids)

        elif mod.action == "modify" and mod.speed_kph is not None:
            keep = ids[np.abs(speed[ids] - mod.speed_kph) >= 0.1]
            if len(keep) > 0:
                speed[keep] = mod.speed_kph
                travel_time[keep] = mirror.length[keep] / (mod.speed_kph / 3.6)
                grams = CO2Calculator.edge_co2_array(
                    mirror.length[keep],
                    np.full(len(keep), float(mod.speed_kph)),
                    mirror.elev_gain[keep],
                )
                co2_g[keep] = grams
                length_km = mirror.length[keep] / 1000.0
                co2_per_km[keep] = np.where(
                    length_km > 0, grams / np.where(length_km > 0, length_km, 1.0), 0.0
                )
                changed.extend(int(i) for i in keep)
            applied.append(mod)

    return (
        applied,
        travel_time,
        speed,
        co2_per_km,
        co2_g,
        blocked,
        np.asarray(sorted(set(changed)), dtype=np.int64),
    )


def apply_edge_modifications(
    graph,
    edge_metrics_cache: dict,
    edge_co2_cache: dict,
    modifications: List[EdgeModification],
) -> Tuple[list, set, list, list]:
    """Apply edge modifications in-place; return rollback data.

    Returns:
        (applied, effective_modified_set, removed_edges, modified_edges)
        - removed_edges: [(u, v, key, data_dict)] for rollback
        - modified_edges: [(u, v, key, orig_speed, orig_tt, orig_co2)] for rollback
    """
    applied = []
    effective_modified_set = set()
    removed_edges = []
    modified_edges = []

    for mod in modifications:
        if not graph.has_edge(mod.u, mod.v):
            continue

        if mod.action == "remove":
            keys = list(graph[mod.u][mod.v].keys())
            for key in keys:
                removed_edges.append((mod.u, mod.v, key, dict(graph[mod.u][mod.v][key])))
            for key in keys:
                graph.remove_edge(mod.u, mod.v, key=key)
            applied.append(mod)
            effective_modified_set.add((mod.u, mod.v))

        elif mod.action == "modify" and mod.speed_kph is not None:
            keys = list(graph[mod.u][mod.v].keys())
            for key in keys:
                edge_data = graph[mod.u][mod.v][key]
                if abs(edge_data.get("speed_kph", 0) - mod.speed_kph) < 0.1:
                    continue

                modified_edges.append(
                    (
                        mod.u,
                        mod.v,
                        key,
                        edge_data.get("speed_kph"),
                        edge_data.get("travel_time"),
                        edge_data.get("co2_g"),
                    )
                )
                length = edge_data.get("length", 0)
                edge_data["speed_kph"] = mod.speed_kph
                edge_data["travel_time"] = (
                    (length / 1000) / (mod.speed_kph / 3600) if mod.speed_kph > 0 else 0
                )
                elev_gain = edge_data.get("elevation_gain", 0)
                edge_data["co2_g"] = CO2Calculator.calculate_edge_co2(
                    length=length, speed_kph=mod.speed_kph, elevation_gain=elev_gain
                )
                edge_metrics_cache[(mod.u, mod.v)] = (
                    edge_data["travel_time"],
                    length,
                    elev_gain,
                    edge_data["co2_g"],
                )
                length_km = length / 1000
                edge_co2_cache[(mod.u, mod.v)] = (
                    edge_data["co2_g"] / length_km if length_km > 0 else 0.0
                )
            applied.append(mod)
            effective_modified_set.add((mod.u, mod.v))

    return applied, effective_modified_set, removed_edges, modified_edges


def restore_edge_modifications(
    graph,
    edge_metrics_cache: dict,
    edge_co2_cache: dict,
    removed_edges: list,
    modified_edges: list,
) -> None:
    """Restore graph and caches to their pre-modification state."""
    for u, v, key, data in removed_edges:
        graph.add_edge(u, v, key=key, **data)

    for u, v, key, orig_speed, orig_tt, orig_co2 in modified_edges:
        ed = graph[u][v][key]
        ed["speed_kph"] = orig_speed
        ed["travel_time"] = orig_tt
        ed["co2_g"] = orig_co2
        length = ed.get("length", 0.0)
        edge_metrics_cache[(u, v)] = (
            orig_tt or 0.0,
            length,
            ed.get("elevation_gain", 0.0),
            orig_co2 or 0.0,
        )
        length_km = length / 1000
        edge_co2_cache[(u, v)] = (orig_co2 / length_km) if orig_co2 and length_km > 0 else 0.0


# ── Graph Serialization ───────────────────────────────────────────────────────


def get_edge_geometries(graph, limit: Optional[int] = None) -> List[dict]:
    """Get edge geometries and attributes for Deck.gl visualization."""
    edges = []
    for i, (u, v, data) in enumerate(graph.edges(data=True)):
        if limit and i >= limit:
            break
        coords = (
            [[lon, lat] for lon, lat in data["geometry"].coords]
            if "geometry" in data
            else [
                [graph.nodes[u]["x"], graph.nodes[u]["y"]],
                [graph.nodes[v]["x"], graph.nodes[v]["y"]],
            ]
        )
        name_raw = data.get("name")
        name = (
            (name_raw[0] if name_raw else None)
            if isinstance(name_raw, list)
            else (str(name_raw) if name_raw else None)
        )
        highway_raw = data.get("highway", "Unknown")
        edges.append(
            {
                "u": int(u),
                "v": int(v),
                "coordinates": coords,
                "travel_time": data.get("travel_time"),
                "length": data.get("length"),
                "speed_kph": data.get("speed_kph"),
                "name": name,
                "highway": highway_raw[0] if isinstance(highway_raw, list) else highway_raw,
                "bus_route_count": int(data.get("bus_route_count", 0) or 0),
                "bus_route_refs": str(data.get("bus_route_refs", "") or ""),
                "habitat_area_m2": float(data.get("habitat_area_m2", 0.0) or 0.0),
            }
        )
    return edges


def get_graph_data(graph) -> GraphData:
    """Get complete graph data for visualization."""
    edges = []
    for u, v, d in graph.edges(data=True):
        coords = (
            [[lon, lat] for lon, lat in d["geometry"].coords]
            if "geometry" in d
            else [
                [graph.nodes[u]["x"], graph.nodes[u]["y"]],
                [graph.nodes[v]["x"], graph.nodes[v]["y"]],
            ]
        )
        name_raw = d.get("name")
        name = (
            " - ".join(str(n) for n in name_raw if n)
            if isinstance(name_raw, list)
            else (str(name_raw) if name_raw else None)
        )
        highway_raw = d.get("highway", "Unknown")
        edges.append(
            GraphEdge(
                u=u,
                v=v,
                geometry=PathGeometry(coordinates=coords),
                name=name,
                highway=(highway_raw[0] if isinstance(highway_raw, list) else highway_raw),
                speed_kph=d.get("speed_kph"),
                length=d.get("length"),
                travel_time=d.get("travel_time"),
                bus_route_count=int(d.get("bus_route_count", 0) or 0),
                bus_route_refs=str(d.get("bus_route_refs", "") or ""),
                habitat_area_m2=float(d.get("habitat_area_m2", 0.0) or 0.0),
            )
        )
    return GraphData(
        edges=edges,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
    )
