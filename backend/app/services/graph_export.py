"""Serialising the NetworkX graph for /routes/habitat-geojson.

The habitat layer is the last reader of the GraphML outside CVRP. Nothing
here is on the routing path.
"""

from typing import List


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
