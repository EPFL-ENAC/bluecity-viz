"""Graph helper functions for geometry, metrics and edge statistics."""

from typing import List, Optional

from app.models.route import EdgeUsageStats, PathGeometry, Route
from app.services.co2_calculator import CO2Calculator


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
    """Calculate travel time, distance, elevation gain for a path."""
    if not graph or not path or len(path) < 2:
        return {"travel_time": None, "distance": None, "elevation_gain": None, "edges_data": []}

    travel_time = distance = elevation_gain = 0.0
    edges_data = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = get_edge_data(graph, u, v)
        if not edge_data:
            continue

        edge_time = edge_data.get("travel_time", 0)
        edge_len = edge_data.get("length", 0)
        travel_time += edge_time
        distance += edge_len

        edge_elev = 0.0
        if "elevation" in graph.nodes[u] and "elevation" in graph.nodes[v]:
            elev_diff = graph.nodes[v]["elevation"] - graph.nodes[u]["elevation"]
            if elev_diff > 0:
                elevation_gain += elev_diff
                edge_elev = elev_diff

        speed_kph = (
            (edge_len / 1000) / (edge_time / 3600) if edge_time > 0 and edge_len > 0 else None
        )
        edges_data.append(
            {"travel_time": edge_time, "speed_kph": speed_kph, "elevation_gain": edge_elev}
        )

    return {
        "travel_time": travel_time,
        "distance": distance,
        "elevation_gain": elevation_gain if elevation_gain > 0 else None,
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
        travel_time=edge_time, speed_kph=speed_kph, elevation_gain=edge_elev
    )


def count_edge_usage(routes: List[Route]) -> dict:
    """Count how many times each edge is used across routes."""
    counts = {}
    for route in routes:
        for i in range(len(route.path) - 1):
            key = (route.path[i], route.path[i + 1])
            counts[key] = counts.get(key, 0) + 1
    return counts


def build_edge_usage_stats(
    graph, routes: List[Route], total_routes: int, original_counts: Optional[dict] = None
) -> List[EdgeUsageStats]:
    """Build edge usage statistics from routes."""
    counts = count_edge_usage(routes)
    stats = []

    for (u, v), count in counts.items():
        freq = count / total_routes if total_routes > 0 else 0
        delta_count = delta_freq = None

        if original_counts is not None:
            if (u, v) in original_counts:
                delta_count = count - original_counts[(u, v)]
                orig_freq = original_counts[(u, v)] / total_routes if total_routes > 0 else 0
                delta_freq = freq - orig_freq
            else:
                delta_count = count
                delta_freq = freq

        stats.append(
            EdgeUsageStats(
                u=u,
                v=v,
                count=count,
                frequency=freq,
                delta_count=delta_count,
                delta_frequency=delta_freq,
                co2_per_use=calculate_edge_co2(graph, u, v),
            )
        )

    stats.sort(key=lambda x: x.frequency, reverse=True)
    return stats
