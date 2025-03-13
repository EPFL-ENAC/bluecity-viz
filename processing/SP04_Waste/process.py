import os
import glob
import geopandas as gpd
import pandas as pd
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def process_file(file_path):
    """Load GeoJSON file and add 'type' field based on filename."""
    logging.info(f"Processing file: {file_path}")

    # Extract the type from the filename (first two letters)
    file_type = os.path.basename(file_path)[:2]
    logging.info(f"Extracted type: {file_type}")

    try:
        # Read GeoJSON directly with GeoPandas
        gdf = gpd.read_file(file_path)

        if len(gdf) == 0:
            logging.warning(f"No features found in {file_path}")
            return None

        logging.info(f"Loaded {len(gdf)} features from {file_path}")

        # Add the type field to each feature
        gdf["type"] = file_type

        return gdf

    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return None


def combine_geojson_files(directory, output_file):
    """Combine all GeoJSON files into a single file with added type field."""
    logging.info(f"Searching for JSON files in {directory}")

    # Find all JSON files in the input directory
    json_files = glob.glob(os.path.join(directory, "*.json"))
    logging.info(
        f"Found {len(json_files)} JSON files: {[os.path.basename(f) for f in json_files]}"
    )

    if not json_files:
        logging.error(f"No JSON files found in {directory}")
        return False

    # List to store GeoDataFrames from each file
    gdfs = []

    # Process each file
    for file_path in json_files:
        gdf = process_file(file_path)
        if gdf is not None and len(gdf) > 0:
            gdfs.append(gdf)
            logging.info(
                f"Added {len(gdf)} features from {os.path.basename(file_path)}"
            )

    if not gdfs:
        logging.error("No valid features found across all files.")
        return False

    # Combine all GeoDataFrames
    combined_gdf = pd.concat(gdfs, ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(combined_gdf, geometry="geometry")

    # Ensure proper CRS
    if combined_gdf.crs is None:
        combined_gdf.crs = "EPSG:4326"

    # Save to GeoJSON with maximum precision
    # Use the to_file method with the precision option to preserve coordinates
    combined_gdf.to_file(output_file, driver="GeoJSON")

    logging.info(
        f"Created combined GeoJSON file with {len(combined_gdf)} features: {output_file}"
    )
    return True


def main():
    """Main function to process waste collection route data."""
    logging.info("Starting SP04 Waste collection route data processing")

    # Input directory containing the JSON files
    input_dir = "Waste collection route_aggregated_2023"

    # Check if input directory exists
    if not os.path.isdir(input_dir):
        logging.error(f"Input directory not found: {input_dir}")
        return False

    # Output file
    processed_geojson = "lausanne_waste_routes.geojson"

    # Combine all JSON files with added type field
    success = combine_geojson_files(input_dir, processed_geojson)

    if not success:
        logging.error("Failed to process the data.")
        return False

    logging.info(
        f"Successfully created waste collection route GeoJSON: {processed_geojson}"
    )
    return True


if __name__ == "__main__":
    success = main()
    if success:
        logging.info("SP04 Waste data processing completed successfully.")
    else:
        logging.error("SP04 Waste data processing failed.")
