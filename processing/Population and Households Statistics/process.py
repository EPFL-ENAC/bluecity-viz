import pandas as pd
from shapely.geometry import Polygon
import geopandas as gpd
from pyproj import Transformer, Geod

# Load the CSV file
data = pd.read_csv("STATPOP2022.csv", delimiter=";")

# Initialize transformers
transformer_to_wgs84 = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
geod = Geod(ellps='WGS84')

# Transform points to EPSG:4326
lon, lat = transformer_to_wgs84.transform(data['E_KOORD'].values, data['N_KOORD'].values)

# Create functions to generate square polygons
def create_square(lat, lon, size_m=100):
    """
    Create a square polygon around a point (lat, lon) with sides of length size_m meters.
    """
    # Calculate half the size
    half_size = size_m / 2.0

    # Calculate the coordinates of the square's corners
    # Starting from the center point, calculate the corners in N-E-S-W directions
    # Note: Azimuths are calculated clockwise from north: 0° (N), 90° (E), 180° (S), 270° (W)
    points = []

    # Calculate corner points
    # Starting from the center, move to each corner
    for angle in [45, 135, 225, 315]:
        dest_lon, dest_lat, _ = geod.fwd(lon, lat, angle, half_size * 1.4142)  # Diagonal distance
        points.append((dest_lon, dest_lat))

    # Close the polygon
    points.append(points[0])

    return Polygon(points)

# Generate polygons
polygons = [create_square(lat_i, lon_i, size_m=100) for lat_i, lon_i in zip(lat, lon)]

# Create a GeoDataFrame
gdf = gpd.GeoDataFrame(data, geometry=polygons, crs="EPSG:4326")

# Save to GeoJSON
gdf.to_file("statpop_grid_wgs84.geojson", driver="GeoJSON")
