import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import os
import json
import logging
from datetime import datetime
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def process_csv_to_linestrings(input_file, output_file):
    """
    Process CSV file with vehicle tracking data into GeoJSON linestrings.
    Group by Date and Vehicle ID.
    """
    logging.info(f"Processing CSV file: {input_file}")

    try:
        # Read CSV data
        df = pd.read_csv(input_file)
        logging.info(f"Loaded {len(df)} rows from CSV")

        # Check if required columns exist
        required_columns = ["Date", "Vehicle ID", "Longitude", "Latitude"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            logging.error(f"Missing required columns: {missing_columns}")
            return False

        # Group data by Date and Vehicle ID
        grouped_data = defaultdict(list)
        for _, row in df.iterrows():
            key = (row["Date"], row["Vehicle ID"])
            point = (row["Longitude"], row["Latitude"])

            # Only add point if it has valid coordinates
            if pd.notna(row["Longitude"]) and pd.notna(row["Latitude"]):
                grouped_data[key].append(point)

        logging.info(
            f"Grouped into {len(grouped_data)} unique Date-Vehicle combinations"
        )

        # Create linestrings from grouped points
        features = []
        for (date, vehicle_id), points in grouped_data.items():
            # Skip if less than 2 points (can't form a linestring)
            if len(points) < 2:
                logging.warning(
                    f"Skipping Date={date}, Vehicle={vehicle_id}: Only {len(points)} points"
                )
                continue

            # Create LineString feature
            linestring = LineString(points)

            # Create feature with properties
            feature = {
                "type": "Feature",
                "properties": {
                    "date": date,
                    "vehicle_id": vehicle_id,
                    "point_count": len(points),
                },
                "geometry": linestring,
            }

            features.append(feature)

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(features)

        # Set CRS to WGS84
        gdf.crs = "EPSG:4326"

        # Save to GeoJSON
        gdf.to_file(output_file, driver="GeoJSON")

        # Validate the JSON file
        try:
            with open(output_file, "r") as f:
                json.load(f)
            logging.info(
                f"Created valid GeoJSON with {len(gdf)} linestrings: {output_file}"
            )
        except json.JSONDecodeError as e:
            logging.error(f"Generated GeoJSON is invalid: {e}")
            return False

        return True

    except Exception as e:
        logging.error(f"Error processing CSV: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


def analyze_vehicle_data(gdf):
    """
    Analyze vehicle data and log statistics
    """
    # Get unique dates and vehicles
    unique_dates = gdf["date"].nunique()
    unique_vehicles = gdf["vehicle_id"].nunique()

    # Get average points per track
    avg_points = gdf["point_count"].mean()

    # Get total distance by converting to a projected CRS (Swiss LV95 for Swiss data)
    # Convert to Swiss coordinate system for accurate distance calculation
    gdf_projected = gdf.to_crs("EPSG:2056")  # Swiss LV95
    gdf_projected["length"] = gdf_projected.geometry.length
    total_length_meters = gdf_projected["length"].sum()
    total_length_km = total_length_meters / 1000

    logging.info(f"Data spans {unique_dates} unique dates")
    logging.info(f"Data contains {unique_vehicles} unique vehicles")
    logging.info(f"Average points per track: {avg_points:.1f}")
    logging.info(
        f"Total distance: {total_length_km:.2f} km ({total_length_meters:.0f} meters)"
    )

    return {
        "unique_dates": unique_dates,
        "unique_vehicles": unique_vehicles,
        "avg_points": avg_points,
        "total_length_km": total_length_km,
        "total_length_meters": total_length_meters,
    }


def main():
    """Main function to process vehicle tracking data"""
    logging.info("Starting SP7 Vehicle Tracking data processing")

    # Input CSV file
    input_file = "solution_routes.csv"

    # Output file
    output_file = "vehicle_tracks.geojson"

    # Process CSV to GeoJSON linestrings
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: {input_file}")
        return False

    success = process_csv_to_linestrings(input_file, output_file)

    if success:
        # Load and analyze the results
        gdf = gpd.read_file(output_file)
        analyze_vehicle_data(gdf)
        logging.info(f"Vehicle tracking data successfully converted to GeoJSON")
        return True
    else:
        logging.error("Failed to process vehicle tracking data")
        return False


if __name__ == "__main__":
    success = main()
    if success:
        logging.info("SP7 Vehicle Tracking processing completed successfully.")
    else:
        logging.error("SP7 Vehicle Tracking processing failed.")
