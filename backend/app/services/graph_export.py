"""Serialising the NetworkX graph for the legacy endpoints.

The frontend loads the network from a static GeoJSON file, so these are only
used by /routes/graph, /routes/edge-geometries (both deprecated) and
/routes/habitat-geojson. Nothing here is on the routing path.
"""

from typing import List, Optional


def edge_coordinates(graph, u, v, data) -> List[List[float]]:
    """Coordinates of an edge, rounded to 6 decimals (about 10 cm)."""
    if "geometry" in data:
        return [[round(lon, 6), round(lat, 6)] for lon, lat in data["geometry"].coords]
    return [
        [round(graph.nodes[u]["x"], 6), round(graph.nodes[u]["y"], 6)],
        [round(graph.nodes[v]["x"], 6), round(graph.nodes[v]["y"], 6)],
    ]


def habitat_geojson(graph) -> dict:
    """Habitat density per edge as a GeoJSON FeatureCollection."""
    features = []
    for u, v, data in graph.edges(data=True):
        habitat = float(data.get("habitat_area_m2", 0.0) or 0.0)
        if habitat <= 0:
            continue
        length = float(data.get("length", 1.0) or 1.0)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": edge_coordinates(graph, u, v, data),
                },
                "properties": {
                    "u": int(u),
                    "v": int(v),
                    "habitat_density_m2_per_m": round(habitat / length if length > 0 else 0.0, 4),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def get_edge_geometries(graph, limit: Optional[int] = None) -> List[dict]:
    """Get edge geometries and attributes for Deck.gl visualization."""
    edges = []
    for i, (u, v, data) in enumerate(graph.edges(data=True)):
        if limit and i >= limit:
            break
        coords = edge_coordinates(graph, u, v, data)
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


def get_graph_data(graph) -> dict:
    """Get complete graph data for visualization, as plain dicts."""
    edges = []
    for u, v, d in graph.edges(data=True):
        coords = edge_coordinates(graph, u, v, d)
        name_raw = d.get("name")
        name = (
            " - ".join(str(n) for n in name_raw if n)
            if isinstance(name_raw, list)
            else (str(name_raw) if name_raw else None)
        )
        highway_raw = d.get("highway", "Unknown")
        edges.append(
            {
                "u": int(u),
                "v": int(v),
                "geometry": {"coordinates": coords},
                "name": name,
                "highway": (highway_raw[0] if isinstance(highway_raw, list) else highway_raw),
                "speed_kph": d.get("speed_kph"),
                "length": d.get("length"),
                "travel_time": d.get("travel_time"),
                "bus_route_count": int(d.get("bus_route_count", 0) or 0),
                "bus_route_refs": str(d.get("bus_route_refs", "") or ""),
                "habitat_area_m2": float(d.get("habitat_area_m2", 0.0) or 0.0),
            }
        )
    return {
        "edges": edges,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
    }
