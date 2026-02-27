import argparse
import calendar
import logging
import os
from typing import Tuple

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.ndimage import gaussian_filter
from shapely.geometry import Point, Polygon

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load environment variables
load_dotenv()

# Constants
BBOX = (46.4, 6.5, 46.6, 6.8)  # Lausanne area (start_lat, start_lon, end_lat, end_lon)
H3_RESOLUTION_AGGREGATE = 10  # Resolution for initial H3 binning
H3_RESOLUTION_SAMPLE = 11  # Resolution for final sampling hexagons
GAUSSIAN_SIGMA = 2  # Sigma parameter for Gaussian smoothing
HISTOGRAM_BINS = 300  # Number of bins for 2D histogram
YEAR = 2024  # Year for data fetching
FILTER_NAME = "co2"  # Sparrow API filter name

# Paths
DATA_DIR = "data"
OUTPUT_DIR = "outputs"
CACHED_CSV = "sparrow_co2_2024.csv"
QUARTIERS_SHP = os.path.join(DATA_DIR, "Quartiers statistiques.shp")


def fetch_monthly_data(year, month, bbox, filter_name, api_key):
    """
    Fetch data from the Sparrow API for a specific month and filter
    within a bounding box.

    Args:
        year (int): The year (e.g., 2024).
        month (int): The month (1-12).
        bbox (tuple): A tuple containing (start_lat, start_lon, end_lat, end_lon).
        filter_name (str): The specific filter to query (e.g., 'co2').
        api_key (str): The API key.

    Returns:
        pd.DataFrame: A DataFrame containing the fetched data.
    """
    url = "https://api.sparrow.city/get"
    headers = {"Accept": "application/json"}

    # Calculate the last day of the specific month
    _, last_day = calendar.monthrange(year, month)

    # Format start and end dates based on API requirements
    start_date = f"{year}-{month:02d}-01T00:00:00"
    end_date = f"{year}-{month:02d}-{last_day:02d}T23:59:59"

    start_lat, start_lon, end_lat, end_lon = bbox

    params = {
        "filter": filter_name,
        "start_date": start_date,
        "end_date": end_date,
        "start_lat": start_lat,
        "start_lon": start_lon,
        "end_lat": end_lat,
        "end_lon": end_lon,
        "api_key": api_key,
    }

    logging.info(f"Fetching {filter_name} data for {start_date} to {end_date}...")

    try:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()  # Raise error for bad status codes
        data = r.json()

        if "body" in data and data["body"]:
            df = pd.DataFrame(data["body"])
            df["filter"] = filter_name
            logging.info(f"Retrieved {len(df)} records for month {month}")
            return df
        else:
            logging.warning(f"No data found for month {month}")
            return pd.DataFrame()

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed for month {month}: {e}")
        return pd.DataFrame()


def fetch_all_data(year, bbox, api_key):
    """
    Fetch data from the Sparrow API for all 12 months of the specified year.

    Args:
        year (int): The year to fetch data for.
        bbox (tuple): Bounding box (start_lat, start_lon, end_lat, end_lon).
        api_key (str): The API key.

    Returns:
        pd.DataFrame: Combined DataFrame with all monthly data.
    """
    logging.info(f"Fetching data for all 12 months of {year}...")
    all_data = []

    for month in range(1, 13):
        df_month = fetch_monthly_data(year, month, bbox, FILTER_NAME, api_key)
        if not df_month.empty:
            all_data.append(df_month)

    if not all_data:
        logging.error("No data retrieved from API")
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    logging.info(f"Total records fetched: {len(combined_df)}")
    return combined_df


def create_point_geodataframe(df):
    """
    Convert DataFrame with x, y columns to GeoDataFrame with Point geometries.

    Args:
        df (pd.DataFrame): DataFrame with 'x' and 'y' columns.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with Point geometries.
    """
    logging.info("Converting DataFrame to GeoDataFrame with Point geometries...")

    # Validate required columns
    if "x" not in df.columns or "y" not in df.columns:
        raise ValueError("DataFrame must contain 'x' and 'y' columns")

    # Create Point geometries from x, y coordinates
    geometry = [Point(xy) for xy in zip(df["x"], df["y"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    logging.info(f"Created GeoDataFrame with {len(gdf)} points")
    return gdf


def create_h3_bins(gdf, resolution=10):
    """
    Create H3 hexagonal bins for each point in the GeoDataFrame.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame with Point geometries.
        resolution (int): H3 resolution level.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with added 'hex_bin' column.
    """
    logging.info(f"Creating H3 bins at resolution {resolution}...")

    hex_bins = []
    for idx, row in gdf.iterrows():
        # Note: h3.latlng_to_cell expects (lat, lng), but geometry.x is lng,
        # geometry.y is lat
        h3_index = h3.latlng_to_cell(row.geometry.y, row.geometry.x, resolution)
        hex_bins.append(h3_index)

    gdf["hex_bin"] = hex_bins
    unique_bins = gdf["hex_bin"].nunique()
    logging.info(f"Created {unique_bins} unique H3 bins")

    return gdf


def aggregate_by_h3(gdf):
    """
    Aggregate data by H3 hexagonal bins and create polygon geometries.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame with 'hex_bin' and 'v' columns.

    Returns:
        gpd.GeoDataFrame: Aggregated GeoDataFrame with H3 polygon geometries.
    """
    logging.info("Aggregating values by H3 bins...")

    # Calculate average value for each hex bin
    hex_avg = gdf.groupby(["hex_bin", "filter"])["v"].mean().reset_index()
    logging.info(f"Aggregated to {len(hex_avg)} H3 bins")

    # Create polygon geometries from H3 cells
    # h3.cell_to_boundary returns coordinates in (lat, lng) order
    # Shapely Polygon expects (x, y) = (lng, lat) order, so we need to swap
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        # Swap from (lat, lng) to (lng, lat) for Shapely
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = hex_avg["hex_bin"].apply(h3_to_polygon)

    h3_geo = gpd.GeoDataFrame(data=hex_avg, geometry=geometries, crs="EPSG:4326")

    # Add log-transformed values for visualization
    h3_geo["log_v"] = h3_geo["v"].apply(lambda x: np.log(x + 1) if x > 0 else 0)

    return h3_geo


def remove_outliers(gdf, column="v", iqr_multiplier=1.5):
    """
    Remove outliers using the IQR (Interquartile Range) method.

    Args:
        gdf (gpd.GeoDataFrame): Input GeoDataFrame.
        column (str): Column to use for outlier detection.
        iqr_multiplier (float): Multiplier for IQR (default 1.5).

    Returns:
        gpd.GeoDataFrame: Filtered GeoDataFrame without outliers.
    """
    logging.info(f"Removing outliers from column '{column}' using IQR method...")

    Q1 = gdf[column].quantile(0.25)
    Q3 = gdf[column].quantile(0.75)
    IQR = Q3 - Q1

    lower_bound = Q1 - iqr_multiplier * IQR
    upper_bound = Q3 + iqr_multiplier * IQR

    original_count = len(gdf)
    filtered_gdf = gdf[
        (gdf[column] >= lower_bound) & (gdf[column] <= upper_bound)
    ].copy()
    removed_count = original_count - len(filtered_gdf)

    logging.info(
        f"Removed {removed_count} outliers ({removed_count/original_count*100:.1f}%)"
    )
    col_min = filtered_gdf[column].min()
    col_max = filtered_gdf[column].max()
    logging.info(f"Value range: [{col_min:.2f}, {col_max:.2f}]")

    return filtered_gdf


def create_smoothed_heatmap(
    gdf, bins=300, sigma=2
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create a smoothed 2D heatmap using Gaussian filtering.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame with polygons and 'v' column.
        bins (int): Number of bins for the 2D histogram.
        sigma (float): Standard deviation for Gaussian kernel.

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: (heatmap_smooth, xedges, yedges)
    """
    logging.info(f"Creating smoothed heatmap with {bins} bins and sigma={sigma}...")

    # Project to EPSG:3857 for accurate distance-based calculations
    h3_3857 = gdf.to_crs(epsg=3857)

    # Get centroid coordinates and values
    x = h3_3857.geometry.centroid.x.values
    y = h3_3857.geometry.centroid.y.values
    v = h3_3857["v"].values

    logging.info(
        f"Heatmap coordinate ranges: X=[{x.min():.2f}, {x.max():.2f}], "
        f"Y=[{y.min():.2f}, {y.max():.2f}]"
    )

    # Create 2D histogram weighted by values
    heatmap, xedges, yedges = np.histogram2d(x, y, bins=bins, weights=v)
    counts, _, _ = np.histogram2d(x, y, bins=bins)

    # Avoid division by zero - compute average value per bin
    heatmap = np.divide(heatmap, counts, out=np.zeros_like(heatmap), where=counts != 0)

    # Apply Gaussian smoothing
    heatmap_smooth = gaussian_filter(heatmap, sigma=sigma)

    logging.info(
        f"Heatmap created: shape={heatmap_smooth.shape}, "
        f"value range=[{heatmap_smooth.min():.2f}, {heatmap_smooth.max():.2f}]"
    )

    return heatmap_smooth, xedges, yedges


def sample_heatmap(geometry, heatmap, xedges, yedges):
    """
    Sample the heatmap value at the geometry's centroid coordinates.

    Args:
        geometry: Shapely geometry (assumed to be in EPSG:3857).
        heatmap (np.ndarray): 2D array of smoothed heatmap values.
        xedges (np.ndarray): X-axis bin edges.
        yedges (np.ndarray): Y-axis bin edges.

    Returns:
        float: Sampled heatmap value, or np.nan if outside bounds.
    """
    # Get centroid coordinates
    px = geometry.x
    py = geometry.y

    # Check if point is inside the heatmap bounds
    if px < xedges[0] or px > xedges[-1] or py < yedges[0] or py > yedges[-1]:
        return np.nan

    # Calculate bin indices
    x_idx = int((px - xedges[0]) / (xedges[-1] - xedges[0]) * (len(xedges) - 1))
    y_idx = int((py - yedges[0]) / (yedges[-1] - yedges[0]) * (len(yedges) - 1))

    # Clip indices to ensure they are within bounds
    x_idx = min(max(x_idx, 0), heatmap.shape[0] - 1)
    y_idx = min(max(y_idx, 0), heatmap.shape[1] - 1)

    # Return value from the smoothed heatmap
    return heatmap[x_idx, y_idx]


def generate_sampling_hexagons(quartiers_path, resolution=11):
    """
    Generate H3 hexagons within Lausanne quartiers boundaries.

    Args:
        quartiers_path (str): Path to the Quartiers statistiques shapefile.
        resolution (int): H3 resolution for sampling hexagons.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame of unique H3 hexagons.
    """
    logging.info(f"Generating H3 hexagons at resolution {resolution} from quartiers...")

    # Read quartiers shapefile
    if not os.path.exists(quartiers_path):
        raise FileNotFoundError(f"Quartiers shapefile not found: {quartiers_path}")

    quartiers_gdf = gpd.read_file(quartiers_path)
    logging.info(f"Loaded {len(quartiers_gdf)} quartiers")

    # Filter out "Zones foraines"
    quartiers_gdf = quartiers_gdf[
        quartiers_gdf["NOMQUARTIE"] != "Zones foraines"
    ].copy()
    logging.info(
        f"Filtered to {len(quartiers_gdf)} quartiers (excluded 'Zones foraines')"
    )

    # Generate H3 hexagons for each quartier
    # h3.geo_to_cells expects GeoJSON-like geometry in EPSG:4326
    quartiers_4326 = quartiers_gdf.to_crs(epsg=4326)

    # Generate hexagons for all quartiers
    all_hexagons = []
    for idx, row in quartiers_4326.iterrows():
        h3_cells = h3.geo_to_cells(row.geometry, res=resolution)
        all_hexagons.extend(h3_cells)

    logging.info(f"Generated {len(all_hexagons)} total H3 cells")

    # Convert to unique set and create GeoDataFrame
    unique_hexagons = list(set(all_hexagons))
    logging.info(f"Unique H3 cells: {len(unique_hexagons)}")

    # Create geometries from H3 cells
    # h3.cell_to_boundary returns coordinates in (lat, lng) order
    # Shapely Polygon expects (x, y) = (lng, lat) order, so we need to swap
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        # Swap from (lat, lng) to (lng, lat) for Shapely
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = [h3_to_polygon(cell) for cell in unique_hexagons]

    hex_gdf = gpd.GeoDataFrame(
        {"hex_id": unique_hexagons}, geometry=geometries, crs="EPSG:4326"
    )

    return hex_gdf


def save_intermediate(gdf, filename, description):
    """
    Save intermediate GeoDataFrame to the outputs directory.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame to save.
        filename (str): Filename (without path).
        description (str): Description for logging.
    """
    output_path = os.path.join(OUTPUT_DIR, filename)
    gdf.to_file(output_path, driver="GeoJSON")
    logging.info(f"Saved {description} to {output_path} ({len(gdf)} features)")


def main(fetch_fresh=False):
    """
    Main function to process Sparrow CO2 emissions data.

    Args:
        fetch_fresh (bool): If True, fetch fresh data from API.
            Otherwise, use cached CSV.

    Returns:
        bool: True if successful, False otherwise.
    """
    logging.info("Starting Sparrow CO2 emissions data processing")

    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Step 1: Load or fetch data
        api_key = os.getenv("APIKEY")
        if fetch_fresh or not os.path.exists(CACHED_CSV):
            if not api_key:
                logging.error(
                    "APIKEY not found in environment. Please set it in .env file."
                )
                return False

            logging.info("Fetching fresh data from Sparrow API...")
            df = fetch_all_data(YEAR, BBOX, api_key)

            if df.empty:
                logging.error("No data retrieved from API")
                return False

            # Cache the data
            df.to_csv(CACHED_CSV, index=False)
            logging.info(f"Cached data to {CACHED_CSV}")
        else:
            logging.info(f"Loading cached data from {CACHED_CSV}")
            df = pd.read_csv(CACHED_CSV)
            logging.info(f"Loaded {len(df)} records from cache")

        # Step 2: Convert to GeoDataFrame
        gdf = create_point_geodataframe(df)

        # Step 3: Create H3 bins and aggregate
        gdf = create_h3_bins(gdf, H3_RESOLUTION_AGGREGATE)
        h3_aggregated = aggregate_by_h3(gdf)
        save_intermediate(h3_aggregated, "h3_aggregated.geojson", "H3 aggregated data")

        # Step 4: Remove outliers
        h3_filtered = remove_outliers(h3_aggregated)

        # Step 5: Create smoothed heatmap
        heatmap, xedges, yedges = create_smoothed_heatmap(
            h3_filtered, HISTOGRAM_BINS, GAUSSIAN_SIGMA
        )

        # Save heatmap data
        heatmap_path = os.path.join(OUTPUT_DIR, "heatmap_smooth.npz")
        np.savez(heatmap_path, heatmap=heatmap, xedges=xedges, yedges=yedges)
        logging.info(f"Saved smoothed heatmap to {heatmap_path}")

        # Step 6: Generate sampling hexagons
        hex_gdf = generate_sampling_hexagons(QUARTIERS_SHP, H3_RESOLUTION_SAMPLE)

        # Step 7: Sample at hexagon centroids
        logging.info("Sampling smoothed heatmap at hexagon centroids...")
        hex_gdf_3857 = hex_gdf.to_crs(epsg=3857)

        # Debug: log coordinate ranges of sampling hexagons
        sample_x = hex_gdf_3857.geometry.centroid.x.values
        sample_y = hex_gdf_3857.geometry.centroid.y.values
        logging.info(
            f"Sampling hexagon ranges: X=[{sample_x.min():.2f}, {sample_x.max():.2f}], "
            f"Y=[{sample_y.min():.2f}, {sample_y.max():.2f}]"
        )

        co2_values = hex_gdf_3857.geometry.centroid.apply(
            lambda geom: sample_heatmap(geom, heatmap, xedges, yedges)
        )
        hex_gdf["co2_smooth"] = co2_values

        # Remove hexagons with NaN values (outside the heatmap bounds)
        valid_count = hex_gdf["co2_smooth"].notna().sum()
        hex_gdf = hex_gdf[hex_gdf["co2_smooth"].notna()].copy()
        logging.info(
            f"Sampled {valid_count} hexagons with valid CO2 values "
            f"(removed {len(co2_values) - valid_count} NaN values)"
        )

        # Step 8: Keep only required columns
        output_gdf = hex_gdf[["hex_id", "co2_smooth", "geometry"]].copy()

        # Step 9: Save final output
        output_path = os.path.join(OUTPUT_DIR, "lausanne_co2_emissions.geojson")
        output_gdf.to_file(output_path, driver="GeoJSON")

        num_features = len(output_gdf)
        logging.info(
            f"Successfully created final output: {output_path} "
            f"({num_features} features)"
        )
        co2_min = output_gdf["co2_smooth"].min()
        co2_max = output_gdf["co2_smooth"].max()
        logging.info(f"CO2 value range: [{co2_min:.2f}, {co2_max:.2f}]")

        return True

    except Exception as e:
        logging.error(f"Error during processing: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Sparrow CO2 emissions data")
    parser.add_argument(
        "--fetch-data",
        action="store_true",
        help="Fetch fresh data from Sparrow API instead of using cached CSV",
    )
    args = parser.parse_args()

    success = main(fetch_fresh=args.fetch_data)
    if success:
        logging.info("Sparrow CO2 processing completed successfully.")
    else:
        logging.error("Sparrow CO2 processing failed.")
