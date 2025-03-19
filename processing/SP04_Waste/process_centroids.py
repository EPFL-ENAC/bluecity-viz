import os
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Define mapping for waste type codes to English labels
WASTE_TYPE_MAPPING = {
    "DV": "Organic Waste",
    "DI": "Household Waste",
    "PC": "Paper & Cardboard",
    "VE": "Glass",
}


def process_centroid_file(file_path):
    """Load CSV file with centroids and add 'type' field based on filename."""
    logging.info(f"Processing centroid file: {file_path}")

    # Extract the type from the filename (first two letters)
    file_type_code = os.path.basename(file_path)[:2]
    file_type = WASTE_TYPE_MAPPING.get(file_type_code, file_type_code)
    logging.info(f"Extracted type: {file_type_code} -> {file_type}")

    try:
        # Read CSV
        df = pd.read_csv(file_path)

        if len(df) == 0:
            logging.warning(f"No centroids found in {file_path}")
            return None

        logging.info(f"Loaded {len(df)} centroids from {file_path}")

        # Create geometry from latitude and longitude
        geometry = [
            Point(lon, lat) for lon, lat in zip(df["centroid_lon"], df["centroid_lat"])
        ]

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        # Add the type fields to each centroid
        gdf["type_code"] = file_type_code
        gdf["type"] = file_type

        return gdf

    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return None


def combine_centroid_files(directory, output_file):
    """Combine all centroid CSV files into a single GeoJSON file with added type field."""
    logging.info(f"Searching for centroid CSV files in {directory}")

    # Find all CSV files that match the pattern of waste type centroids
    csv_files = glob.glob(os.path.join(directory, "*_final_clustered_centroids.csv"))
    logging.info(
        f"Found {len(csv_files)} centroid CSV files: {[os.path.basename(f) for f in csv_files]}"
    )

    if not csv_files:
        logging.error(f"No centroid CSV files found in {directory}")
        return False

    # List to store GeoDataFrames from each file
    gdfs = []

    # Process each file
    for file_path in csv_files:
        gdf = process_centroid_file(file_path)
        if gdf is not None and len(gdf) > 0:
            gdfs.append(gdf)
            logging.info(
                f"Added {len(gdf)} centroids from {os.path.basename(file_path)}"
            )

    if not gdfs:
        logging.error("No valid centroids found across all files.")
        return False

    # Combine all GeoDataFrames
    combined_gdf = pd.concat(gdfs, ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(combined_gdf, geometry="geometry", crs="EPSG:4326")

    # Save to GeoJSON
    combined_gdf.to_file(output_file, driver="GeoJSON")

    logging.info(
        f"Created combined GeoJSON file with {len(combined_gdf)} centroids: {output_file}"
    )
    return True


def main():
    """Main function to process waste collection centroids data."""
    logging.info("Starting waste collection centroids processing")

    # Input directory containing the centroid CSV files
    input_dir = "Waste collection points by types (density-based spatial clustering)"

    # Check if input directory exists
    if not os.path.isdir(input_dir):
        logging.error(f"Input directory not found: {input_dir}")
        return False

    # Output file
    processed_geojson = "lausanne_waste_centroids.geojson"

    # Combine all centroid CSV files with added type field
    success = combine_centroid_files(input_dir, processed_geojson)

    if not success:
        logging.error("Failed to process the centroid data.")
        return False

    logging.info(
        f"Successfully created waste collection centroids GeoJSON: {processed_geojson}"
    )
    return True


if __name__ == "__main__":
    success = main()
    if success:
        logging.info("Waste centroids processing completed successfully.")
    else:
        logging.error("Waste centroids processing failed.")
