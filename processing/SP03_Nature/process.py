import json
import os
import glob
from shapely.geometry import Polygon, Point
import geopandas as gpd
from pyproj import Transformer, Geod
import pandas as pd
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Helper function to create a square around a point
def create_square(lat, lon, size_m=200):
    """
    Create a square polygon around a point (lat, lon) with sides of length size_m meters.
    """
    # Calculate half the size
    half_size = size_m / 2.0

    # Initialize the geoid model for accurate distance calculations
    geod = Geod(ellps="WGS84")

    # Calculate corner points
    # Starting from the center, move to each corner
    points = []
    for angle in [45, 135, 225, 315]:
        dest_lon, dest_lat, _ = geod.fwd(
            lon, lat, angle, half_size * 1.4142
        )  # Diagonal distance
        points.append((dest_lon, dest_lat))

    # Close the polygon
    points.append(points[0])

    return Polygon(points)


def process_json_to_geojson(input_file, output_file):
    """
    Process a JSON file with lat/lon/value entries into a GeoJSON file
    """
    logging.info(f"Processing {input_file} to {output_file}")

    # Check if input file exists
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: {input_file}")
        return False

    try:
        # Load JSON data
        with open(input_file, "r") as f:
            data = json.load(f)

        # Extract data points
        points = data.get("data", [])

        if not points:
            logging.warning(f"No data points found in {input_file}")
            return False

        logging.info(f"Found {len(points)} data points in {input_file}")

        # Log first few points for verification
        for i, point in enumerate(points[:3]):
            logging.info(
                f"Sample point {i+1}: lat={point.get('lat')}, lon={point.get('lon')}, value={point.get('value')}"
            )

        # Create DataFrame from points
        df = pd.DataFrame(points)

        # Check for missing or invalid values
        if df.isnull().any().any():
            logging.warning(f"Found null values in the data: {df.isnull().sum()}")

        # Generate polygons - one square for each lat/lon point
        logging.info("Generating polygons...")
        polygons = []
        for point in points:
            try:
                polygon = create_square(point["lat"], point["lon"], size_m=200)
                polygons.append(polygon)
            except Exception as e:
                logging.error(f"Failed to create polygon for point {point}: {e}")

        logging.info(f"Created {len(polygons)} polygons")

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {"value": [point["value"] for point in points]},
            geometry=polygons,
            crs="EPSG:4326",
        )

        # Save to GeoJSON
        gdf.to_file(output_file, driver="GeoJSON")
        logging.info(f"Created GeoJSON file: {output_file} with {len(gdf)} features")
        return True

    except Exception as e:
        logging.error(f"Error processing {input_file}: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


def process_directory(input_dir, output_prefix):
    """
    Process all JSON files in a directory and create one unified GeoJSON
    """
    logging.info(
        f"Processing directory: {input_dir} with output prefix: {output_prefix}"
    )

    # Log current directory for context
    current_dir = os.getcwd()
    logging.info(f"Current working directory: {current_dir}")

    # Resolve absolute path
    abs_input_dir = os.path.abspath(input_dir)
    logging.info(f"Absolute path to input directory: {abs_input_dir}")

    # Check if directory exists
    if not os.path.isdir(input_dir):
        logging.error(f"Directory not found: {input_dir}")
        return False

    # Find all JSON files in the directory
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    logging.info(f"Found {len(json_files)} JSON files in {input_dir}")

    # Log all found files
    for file in json_files:
        logging.info(f"Found file: {file}")

    if not json_files:
        logging.warning(f"No JSON files found in {input_dir}")
        return False

    success = False

    # Process yearly data (if available)
    yearly_files = [f for f in json_files if "yearly" in f.lower()]
    if yearly_files:
        logging.info(f"Found {len(yearly_files)} yearly files: {yearly_files}")
        success |= process_json_to_geojson(
            yearly_files[0], f"{output_prefix}_yearly.geojson"
        )
    else:
        logging.warning(f"No yearly files found in {input_dir}")

    # Process monthly data (optional)
    monthly_files = [
        f for f in json_files if "monthly" in f.lower() or "month" in f.lower()
    ]
    if monthly_files:
        logging.info(f"Found {len(monthly_files)} monthly files: {monthly_files}")
        success |= process_json_to_geojson(
            monthly_files[0], f"{output_prefix}_monthly.geojson"
        )
    else:
        logging.warning(f"No monthly files found in {input_dir}")

    return success


def main():
    logging.info("Starting SP03 Nature data processing")

    # Process AQI data
    logging.info("===== Processing AQI data =====")
    aqi_success = process_directory("AQI_JSON", "lausanne_aqi")
    logging.info(f"AQI processing {'successful' if aqi_success else 'failed'}")

    # Process temperature data
    logging.info("===== Processing temperature data =====")
    temp_success = process_directory("temperature_output_json", "lausanne_temperature")
    logging.info(f"Temperature processing {'successful' if temp_success else 'failed'}")

    # Check if any data was processed successfully
    if aqi_success or temp_success:
        logging.info("Processing completed with some success")
    else:
        logging.error("No data was processed successfully")

    logging.info("SP03 Nature data processing finished")


if __name__ == "__main__":
    main()
