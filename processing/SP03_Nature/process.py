import json
import os
import glob
from shapely.geometry import Polygon, Point
import geopandas as gpd
from pyproj import Transformer, Geod, CRS
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


def process_species_data(input_file, output_file):
    """
    Process species observation CSV file into a GeoJSON point file
    with coordinates transformed from CH1903+/LV95 to WGS84
    """
    logging.info(f"Processing species data from {input_file} to {output_file}")

    # Define mapping for Red List status codes to full names
    RED_LIST_MAPPING = {
        "CR": "Critically Endangered",
        "EN": "Endangered",
        "VU": "Vulnerable",
        "NT": "Near Threatened",
        "LC": "Least Concern",
        "DD": "Data Deficient",
        "NE": "Not Evaluated",
    }

    try:
        # Check if input file exists
        if not os.path.exists(input_file):
            logging.error(f"Input file not found: {input_file}")
            return False

        # Read CSV file
        df = pd.read_csv(input_file)
        logging.info(f"Loaded {len(df)} species observations from CSV")

        # Log the first few entries for verification
        logging.info(f"First few records: \n{df.head()}")

        # Check for missing coordinate values
        if df["Longitude"].isnull().any() or df["Latitude"].isnull().any():
            logging.warning("Missing coordinate values found in the data")
            # Remove rows with missing coordinates
            df = df.dropna(subset=["Longitude", "Latitude"])
            logging.info(f"After dropping missing coordinates: {len(df)} records")

        # Create transformer from CH1903+/LV95 (EPSG:2056) to WGS84 (EPSG:4326)
        transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

        # Apply coordinate transformation
        logging.info("Transforming coordinates from CH1903+/LV95 to WGS84...")

        # Create geometry points after transformation
        geometry = []
        for idx, row in df.iterrows():
            try:
                # Transform coordinates (note the order: x=longitude, y=latitude in LV95)
                lon, lat = transformer.transform(row["Longitude"], row["Latitude"])
                geometry.append(Point(lon, lat))
            except Exception as e:
                logging.error(f"Error transforming coordinates at row {idx}: {e}")
                geometry.append(None)

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        # Drop rows with invalid geometry
        if gdf.geometry.isna().any():
            logging.warning("Found rows with invalid geometry")
            gdf = gdf.dropna(subset=["geometry"])
            logging.info(f"After dropping invalid geometry: {len(gdf)} records")

        # Apply the Red List mapping to add a full label column
        if "Red List" in gdf.columns:
            # First, keep the original code
            gdf["Red List Code"] = gdf["Red List"]

            # Then create a new column with the full label
            gdf["Red List"] = gdf["Red List Code"].apply(
                lambda code: (
                    RED_LIST_MAPPING.get(code, "Unknown")
                    if pd.notnull(code)
                    else "Unknown"
                )
            )

            # Log the mapping results
            status_counts = gdf["Red List"].value_counts()
            logging.info(f"Red List status distribution: \n{status_counts}")
        else:
            logging.warning("Red List column not found in the data")

        # Save to GeoJSON
        gdf.to_file(output_file, driver="GeoJSON")
        logging.info(f"Created GeoJSON file: {output_file} with {len(gdf)} features")
        return True

    except Exception as e:
        logging.error(f"Error processing species data: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


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

    # Process species observation data
    logging.info("===== Processing species observation data =====")
    species_input = os.path.join("species_observations_csv", "data_species.csv")
    species_output = "lausanne_species.geojson"
    species_success = process_species_data(species_input, species_output)
    logging.info(
        f"Species data processing {'successful' if species_success else 'failed'}"
    )

    # Check if any data was processed successfully
    if aqi_success or temp_success or species_success:
        logging.info("Processing completed with some success")
    else:
        logging.error("No data was processed successfully")

    logging.info("SP03 Nature data processing finished")


if __name__ == "__main__":
    main()
