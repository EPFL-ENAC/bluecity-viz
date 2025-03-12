import pandas as pd
from shapely.geometry import Polygon, Point, box
import geopandas as gpd
from pyproj import Transformer, Geod


data = pd.read_csv("lausanne_migration_2011_2023.csv", delimiter=",")


# Initialize transformers
transformer_to_wgs84 = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
geod = Geod(ellps="WGS84")


lon, lat = transformer_to_wgs84.transform(
    data["x_coord"].values, data["y_coord"].values
)


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
        dest_lon, dest_lat, _ = geod.fwd(
            lon, lat, angle, half_size * 1.4142
        )  # Diagonal distance
        points.append((dest_lon, dest_lat))

    # Close the polygon
    points.append(points[0])

    return Polygon(points)


def create_square2(lat, lon, size_m=100):
    from shapely.geometry import box, Point
    import geopandas as gpd

    # Create GeoDataFrame with a Point in EPSG:4326
    gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")

    # Convert to a projection that uses meters (EPSG:3857 is not rotated)
    gdf = gdf.to_crs("EPSG:3857")

    # Create an axis-aligned square (box) centered on the point
    center = gdf.geometry.iloc[0]
    half = size_m / 2
    square = box(center.x - half, center.y - half, center.x + half, center.y + half)
    gdf.loc[0, "geometry"] = square

    # Convert back to EPSG:4326
    gdf = gdf.to_crs("EPSG:4326")
    return gdf.iloc[0].geometry


# Generate polygons
polygons = [create_square(lat_i, lon_i, size_m=100) for lat_i, lon_i in zip(lat, lon)]

# Create a GeoDataFrame
gdf = gpd.GeoDataFrame(data, geometry=polygons, crs="EPSG:4326")

gdf.to_file("lausanne_migration_2011_2023.geojson", driver="GeoJSON")
