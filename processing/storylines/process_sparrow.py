import argparse
import calendar
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.ndimage import gaussian_filter
from shapely import wkt
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

# Sparrow API filters
ALLOWED_FILTERS = ["co2", "no2", "pm25", "o3", "temperature"]
DEFAULT_FILTERS = ALLOWED_FILTERS
DEFAULT_YEARS = list(range(2023, datetime.now().year + 1))  # 2023 to current year

# Time period definitions (hours)
TIME_PERIODS = {
    "night": [20, 21, 22, 23, 0, 1, 2, 3, 4, 5],
    "morning_commute": [7, 8],
    "work_hours": [10, 11, 12, 13, 14, 15],
    "late_afternoon_commute": [17, 18],
}

# Paths
DATA_DIR = "data"
OUTPUT_DIR = "outputs"

LAUSANNE_HULL_WKT = (
    "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
    "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
    "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
    "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
    "6.7016307 46.4999401, 6.6973149 46.4991489))"
)


def parse_and_validate_args(args) -> Tuple[List[int], List[str]]:
    """
    Parse and validate command-line arguments for years and filters.

    Args:
        args: Parsed argparse arguments.

    Returns:
        Tuple[List[int], List[str]]: (validated_years, validated_filters)

    Raises:
        ValueError: If years or filters are invalid.
    """
    # Parse years
    if args.years is None:
        years = DEFAULT_YEARS
    else:
        try:
            years = [int(y.strip()) for y in args.years.split(",")]
        except ValueError:
            raise ValueError(
                f"Invalid year format: {args.years}. Use comma-separated integers."
            )

    # Validate years
    current_year = datetime.now().year
    for year in years:
        if year < 2023:
            raise ValueError(
                f"Year {year} is too early. Sparrow API data starts from 2023."
            )
        if year > current_year:
            raise ValueError(
                f"Year {year} is in the future. Current year is {current_year}."
            )

    # Parse filters
    if args.filters is None:
        filters = DEFAULT_FILTERS
    else:
        filters = [f.strip() for f in args.filters.split(",")]

    # Validate filters
    for filter_name in filters:
        if filter_name not in ALLOWED_FILTERS:
            allowed = ", ".join(ALLOWED_FILTERS)
            raise ValueError(
                f"Invalid filter '{filter_name}'. Allowed filters: {allowed}"
            )

    logging.info(f"Validated years: {years}")
    logging.info(f"Validated filters: {filters}")

    return years, filters


def get_cache_filename(years: List[int], filters: List[str]) -> str:
    """
    Generate cache filename based on years and filters.

    Args:
        years: List of years.
        filters: List of filter names.

    Returns:
        str: Cache filename.
    """
    year_range = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])
    filter_str = "-".join(sorted(filters))
    return f"sparrow_{year_range}_{filter_str}.csv"


def add_time_period(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add time_period column to GeoDataFrame based on hour.

    Time periods:
    - night: 20-05 (8pm to 6am)
    - morning_commute: 07-08 (7am to 9am)
    - work_hours: 10-15 (10am to 4pm)
    - late_afternoon_commute: 17-18 (5pm to 7pm)

    Args:
        gdf: GeoDataFrame with 'hour' column.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with added 'time_period' column.
    """
    logging.info("Adding time_period column based on hour...")

    def hour_to_period(hour):
        for period_name, hours in TIME_PERIODS.items():
            if hour in hours:
                return period_name
        return "other"  # Hours not in any defined period (6, 9, 16, 19)

    gdf["time_period"] = gdf["hour"].apply(hour_to_period)

    # Log distribution
    period_counts = gdf["time_period"].value_counts()
    logging.info(f"Time period distribution: {period_counts.to_dict()}")

    return gdf


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


def fetch_all_data(years: List[int], filters: List[str], bbox, api_key):
    """
    Fetch data from the Sparrow API for specified years and filters.

    Args:
        years: List of years to fetch data for.
        filters: List of filter names to fetch.
        bbox (tuple): Bounding box (start_lat, start_lon, end_lat, end_lon).
        api_key (str): The API key.

    Returns:
        pd.DataFrame: Combined DataFrame with all data.
    """
    logging.info(
        f"Fetching data for {len(years)} year(s) and {len(filters)} filter(s)..."
    )
    all_data = []
    total_combinations = len(years) * len(filters) * 12
    completed = 0

    for year in years:
        for filter_name in filters:
            for month in range(1, 13):
                df_month = fetch_monthly_data(year, month, bbox, filter_name, api_key)
                if not df_month.empty:
                    all_data.append(df_month)

                completed += 1
                if completed % 10 == 0:
                    logging.info(
                        f"Progress: {completed}/{total_combinations} requests completed"
                    )

    if not all_data:
        logging.error("No data retrieved from API")
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    logging.info(
        f"Total records fetched: {len(combined_df)} across "
        f"{len(all_data)} successful requests"
    )
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
    gdf["t"] = pd.to_datetime(gdf["t"], unit="s")
    gdf["hour"] = gdf["t"].dt.hour
    gdf["month"] = gdf["t"].dt.month
    gdf["year"] = gdf["t"].dt.year

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

    lats = gdf.geometry.y.to_numpy()
    lngs = gdf.geometry.x.to_numpy()

    gdf["hex_bin"] = list(
        map(lambda lat, lng: h3.latlng_to_cell(lat, lng, resolution), lats, lngs)
    )
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


def aggregate_level1(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Level 1 aggregation: Overall aggregate per hexagon per filter.

    Args:
        gdf: GeoDataFrame with 'hex_bin', 'filter', and 'v' columns.

    Returns:
        gpd.GeoDataFrame: Aggregated data with polygon geometries.
    """
    logging.info("Creating Level 1 aggregation (overall per hex/filter)...")

    # Calculate average value for each hex bin and filter
    hex_avg = gdf.groupby(["hex_bin", "filter"])["v"].mean().reset_index()
    logging.info(f"Level 1: Aggregated to {len(hex_avg)} hex/filter combinations")

    # Create polygon geometries from H3 cells
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = hex_avg["hex_bin"].apply(h3_to_polygon)
    h3_geo = gpd.GeoDataFrame(data=hex_avg, geometry=geometries, crs="EPSG:4326")

    return h3_geo


def aggregate_level2(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Level 2 aggregation: Monthly aggregates per hexagon per filter.

    Args:
        gdf: GeoDataFrame with 'hex_bin', 'filter', 'month', and 'v' columns.

    Returns:
        gpd.GeoDataFrame: Aggregated data with polygon geometries.
    """
    logging.info("Creating Level 2 aggregation (monthly per hex/filter)...")

    # Calculate average value for each hex bin, filter, and month
    hex_avg = gdf.groupby(["hex_bin", "filter", "month"])["v"].mean().reset_index()
    logging.info(f"Level 2: Aggregated to {len(hex_avg)} hex/filter/month combinations")

    # Create polygon geometries from H3 cells
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = hex_avg["hex_bin"].apply(h3_to_polygon)
    h3_geo = gpd.GeoDataFrame(data=hex_avg, geometry=geometries, crs="EPSG:4326")

    return h3_geo


def aggregate_level3(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Level 3 aggregation: Time-of-day aggregates per hexagon per filter.

    Args:
        gdf: GeoDataFrame with 'hex_bin', 'filter', 'time_period', and 'v' columns.

    Returns:
        gpd.GeoDataFrame: Aggregated data with polygon geometries.
    """
    logging.info("Creating Level 3 aggregation (time-of-day per hex/filter)...")

    # Filter out "other" time periods (hours not in any defined period)
    gdf_filtered = gdf[gdf["time_period"] != "other"].copy()

    # Calculate average value for each hex bin, filter, and time period
    hex_avg = (
        gdf_filtered.groupby(["hex_bin", "filter", "time_period"])["v"]
        .mean()
        .reset_index()
    )
    logging.info(
        f"Level 3: Aggregated to {len(hex_avg)} hex/filter/time_period combinations"
    )

    # Create polygon geometries from H3 cells
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = hex_avg["hex_bin"].apply(h3_to_polygon)
    h3_geo = gpd.GeoDataFrame(data=hex_avg, geometry=geometries, crs="EPSG:4326")

    return h3_geo


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


def create_all_smoothed_heatmaps(
    gdf_level1: gpd.GeoDataFrame,
    gdf_level2: gpd.GeoDataFrame,
    gdf_level3: gpd.GeoDataFrame,
    bins=300,
    sigma=2,
) -> Dict:
    """
    Create smoothed heatmaps for all three aggregation levels.

    Args:
        gdf_level1: Level 1 aggregated data (overall per hex/filter).
        gdf_level2: Level 2 aggregated data (monthly per hex/filter).
        gdf_level3: Level 3 aggregated data (time-of-day per hex/filter).
        bins: Number of bins for 2D histogram.
        sigma: Standard deviation for Gaussian kernel.

    Returns:
        dict: {
            'level1': {filter: (heatmap, xedges, yedges)},
            'level2': {(filter, month): (heatmap, xedges, yedges)},
            'level3': {(filter, period): (heatmap, xedges, yedges)}
        }
    """
    heatmaps = {"level1": {}, "level2": {}, "level3": {}}
    total_heatmaps = 0

    # Count total heatmaps for progress tracking
    num_filters_l1 = gdf_level1["filter"].nunique()
    num_filters_l2 = gdf_level2["filter"].nunique() if not gdf_level2.empty else 0
    num_months_l2 = gdf_level2["month"].nunique() if not gdf_level2.empty else 0
    num_filters_l3 = gdf_level3["filter"].nunique() if not gdf_level3.empty else 0
    num_periods_l3 = gdf_level3["time_period"].nunique() if not gdf_level3.empty else 0

    expected_total = (
        num_filters_l1
        + (num_filters_l2 * num_months_l2)
        + (num_filters_l3 * num_periods_l3)
    )
    logging.info(f"Creating {expected_total} smoothed heatmaps across 3 levels...")

    # Level 1: One heatmap per filter
    for filter_name in gdf_level1["filter"].unique():
        subset = gdf_level1[gdf_level1["filter"] == filter_name]
        heatmap, xedges, yedges = create_smoothed_heatmap(subset, bins, sigma)
        heatmaps["level1"][filter_name] = (heatmap, xedges, yedges)
        total_heatmaps += 1
        logging.info(
            f"Progress: {total_heatmaps}/{expected_total} - Level 1: {filter_name}"
        )

    # Level 2: One heatmap per filter per month
    if not gdf_level2.empty:
        for filter_name in gdf_level2["filter"].unique():
            for month in gdf_level2["month"].unique():
                subset = gdf_level2[
                    (gdf_level2["filter"] == filter_name)
                    & (gdf_level2["month"] == month)
                ]
                if len(subset) > 0:
                    heatmap, xedges, yedges = create_smoothed_heatmap(
                        subset, bins, sigma
                    )
                    heatmaps["level2"][(filter_name, int(month))] = (
                        heatmap,
                        xedges,
                        yedges,
                    )
                    total_heatmaps += 1
                    if total_heatmaps % 10 == 0:
                        logging.info(
                            f"Progress: {total_heatmaps}/{expected_total} - "
                            f"Level 2: {filter_name}, month {month}"
                        )

    # Level 3: One heatmap per filter per time period
    if not gdf_level3.empty:
        for filter_name in gdf_level3["filter"].unique():
            for period in gdf_level3["time_period"].unique():
                subset = gdf_level3[
                    (gdf_level3["filter"] == filter_name)
                    & (gdf_level3["time_period"] == period)
                ]
                if len(subset) > 0:
                    heatmap, xedges, yedges = create_smoothed_heatmap(
                        subset, bins, sigma
                    )
                    heatmaps["level3"][(filter_name, period)] = (
                        heatmap,
                        xedges,
                        yedges,
                    )
                    total_heatmaps += 1
                    logging.info(
                        f"Progress: {total_heatmaps}/{expected_total} - "
                        f"Level 3: {filter_name}, {period}"
                    )

    logging.info(f"Created {total_heatmaps} smoothed heatmaps")
    return heatmaps


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


def generate_sampling_hexagons(resolution=11):
    """
    Generate H3 hexagons within Lausanne hull boundary.

    Args:
        resolution (int): H3 resolution for sampling hexagons.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame of unique H3 hexagons.
    """
    logging.info(
        f"Generating H3 hexagons at resolution {resolution} from Lausanne hull..."
    )

    # Parse the Lausanne hull WKT string
    lausanne_polygon = wkt.loads(LAUSANNE_HULL_WKT)

    # Create GeoDataFrame with the hull polygon
    logging.info("Loaded Lausanne hull polygon")

    # Generate H3 hexagons using h3.geo_to_cells
    # h3.geo_to_cells expects GeoJSON-like geometry in EPSG:4326
    h3_cells = h3.geo_to_cells(lausanne_polygon, res=resolution)
    all_hexagons = list(h3_cells)

    logging.info(f"Generated {len(all_hexagons)} H3 cells")

    # Create geometries from H3 cells
    # h3.cell_to_boundary returns coordinates in (lat, lng) order
    # Shapely Polygon expects (x, y) = (lng, lat) order, so we need to swap
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        # Swap from (lat, lng) to (lng, lat) for Shapely
        return Polygon([(lng, lat) for lat, lng in boundary])

    geometries = [h3_to_polygon(cell) for cell in all_hexagons]

    hex_gdf = gpd.GeoDataFrame(
        {"hex_id": all_hexagons}, geometry=geometries, crs="EPSG:4326"
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


def sample_all_heatmaps(
    hex_gdf: gpd.GeoDataFrame, heatmaps: Dict, filters: List[str]
) -> gpd.GeoDataFrame:
    """
    Sample all smoothed heatmaps at hexagon centroids and build nested structure.

    Args:
        hex_gdf: GeoDataFrame of sampling hexagons.
        heatmaps: Dictionary of heatmaps from create_all_smoothed_heatmaps.
        filters: List of filter names.

    Returns:
        gpd.GeoDataFrame: Hexagons with nested properties per filter.
    """
    logging.info("Sampling all heatmaps at hexagon centroids...")

    # Convert to EPSG:3857 for sampling
    hex_gdf_3857 = hex_gdf.to_crs(epsg=3857)
    centroids = hex_gdf_3857.geometry.centroid

    # Initialize nested structure for each hexagon
    result_data = []

    for idx, (hex_id, centroid) in enumerate(zip(hex_gdf["hex_id"], centroids)):
        hex_props = {"hex_id": hex_id}

        # Sample all filters
        for filter_name in filters:
            filter_props = {}

            # Level 1: Overall value
            if filter_name in heatmaps["level1"]:
                heatmap, xedges, yedges = heatmaps["level1"][filter_name]
                overall_value = sample_heatmap(centroid, heatmap, xedges, yedges)
                filter_props["overall"] = (
                    float(overall_value) if not np.isnan(overall_value) else None
                )
            else:
                filter_props["overall"] = None

            # Level 2: Monthly values
            monthly_values = {}
            for month in range(1, 13):
                key = (filter_name, month)
                if key in heatmaps["level2"]:
                    heatmap, xedges, yedges = heatmaps["level2"][key]
                    month_value = sample_heatmap(centroid, heatmap, xedges, yedges)
                    monthly_values[str(month)] = (
                        float(month_value) if not np.isnan(month_value) else None
                    )
                else:
                    monthly_values[str(month)] = None
            filter_props["monthly"] = monthly_values

            # Level 3: Time-of-day values
            time_of_day_values = {}
            for period_name in TIME_PERIODS.keys():
                key = (filter_name, period_name)
                if key in heatmaps["level3"]:
                    heatmap, xedges, yedges = heatmaps["level3"][key]
                    period_value = sample_heatmap(centroid, heatmap, xedges, yedges)
                    time_of_day_values[period_name] = (
                        float(period_value) if not np.isnan(period_value) else None
                    )
                else:
                    time_of_day_values[period_name] = None
            filter_props["time_of_day"] = time_of_day_values

            hex_props[filter_name] = filter_props

        result_data.append(hex_props)

        if (idx + 1) % 100 == 0:
            logging.info(f"Sampled {idx + 1}/{len(hex_gdf)} hexagons")

    logging.info(f"Completed sampling for all {len(hex_gdf)} hexagons")

    # Create new GeoDataFrame with nested properties
    result_gdf = gpd.GeoDataFrame(
        result_data, geometry=hex_gdf.geometry, crs="EPSG:4326"
    )

    # Filter out hexagons where all overall values are None
    def has_valid_data(row):
        for filter_name in filters:
            if filter_name in row and row[filter_name]["overall"] is not None:
                return True
        return False

    result_gdf = result_gdf[result_gdf.apply(has_valid_data, axis=1)].copy()
    logging.info(
        f"Filtered to {len(result_gdf)} hexagons with valid data "
        f"(removed {len(hex_gdf) - len(result_gdf)} hexagons with no data)"
    )

    return result_gdf


def main(years: List[int], filters: List[str], fetch_fresh=False):
    """
    Main function to process Sparrow emissions data with multi-level aggregation.

    Args:
        years: List of years to process.
        filters: List of filter names to process.
        fetch_fresh (bool): If True, fetch fresh data from API.
            Otherwise, use cached CSV.

    Returns:
        bool: True if successful, False otherwise.
    """
    logging.info("Starting Sparrow emissions data processing")
    logging.info(f"Years: {years}")
    logging.info(f"Filters: {filters}")

    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Step 1: Load or fetch data
        api_key = os.getenv("APIKEY")
        cache_filename = get_cache_filename(years, filters)
        cache_path = os.path.join(DATA_DIR, cache_filename)

        if fetch_fresh or not os.path.exists(cache_path):
            if not api_key:
                logging.error(
                    "APIKEY not found in environment. Please set it in .env file."
                )
                return False

            logging.info("Fetching fresh data from Sparrow API...")
            df = fetch_all_data(years, filters, BBOX, api_key)

            if df.empty:
                logging.error("No data retrieved from API")
                return False

            # Cache the data
            df.to_csv(cache_path, index=False)
            logging.info(f"Cached data to {cache_path}")
        else:
            logging.info(f"Loading cached data from {cache_path}")
            df = pd.read_csv(cache_path)
            logging.info(f"Loaded {len(df)} records from cache")

        # Step 2: Convert to GeoDataFrame and add time columns
        gdf = create_point_geodataframe(df)
        gdf = add_time_period(gdf)

        # Step 3: Create H3 bins at aggregate resolution
        gdf = create_h3_bins(gdf, H3_RESOLUTION_AGGREGATE)

        # Step 4: Create three aggregation levels
        logging.info("Creating multi-level aggregations...")
        gdf_level1 = aggregate_level1(gdf)
        gdf_level2 = aggregate_level2(gdf)
        gdf_level3 = aggregate_level3(gdf)

        # Save intermediate aggregations
        save_intermediate(
            gdf_level1, "level1_aggregated.geojson", "Level 1 aggregated data"
        )
        save_intermediate(
            gdf_level2, "level2_aggregated.geojson", "Level 2 aggregated data"
        )
        save_intermediate(
            gdf_level3, "level3_aggregated.geojson", "Level 3 aggregated data"
        )

        # Step 5: Remove outliers from each level
        logging.info("Removing outliers from aggregated data...")
        gdf_level1_filtered = remove_outliers(gdf_level1)
        gdf_level2_filtered = remove_outliers(gdf_level2)
        gdf_level3_filtered = remove_outliers(gdf_level3)

        # Step 6: Create all smoothed heatmaps
        heatmaps = create_all_smoothed_heatmaps(
            gdf_level1_filtered,
            gdf_level2_filtered,
            gdf_level3_filtered,
            HISTOGRAM_BINS,
            GAUSSIAN_SIGMA,
        )

        # Step 7: Generate sampling hexagons from Lausanne hull
        hex_gdf = generate_sampling_hexagons(H3_RESOLUTION_SAMPLE)

        # Step 8: Sample all heatmaps and build nested structure
        result_gdf = sample_all_heatmaps(hex_gdf, heatmaps, filters)

        # Step 9: Save final output
        output_path = os.path.join(OUTPUT_DIR, "lausanne_emissions_multilevel.geojson")
        result_gdf.to_file(output_path, driver="GeoJSON")

        num_features = len(result_gdf)
        logging.info(
            f"Successfully created final output: {output_path} "
            f"({num_features} features)"
        )

        # Log summary statistics
        for filter_name in filters:
            if filter_name in result_gdf.columns:
                overall_values = [
                    row[filter_name]["overall"]
                    for _, row in result_gdf.iterrows()
                    if row[filter_name]["overall"] is not None
                ]
                if overall_values:
                    min_val = min(overall_values)
                    max_val = max(overall_values)
                    logging.info(
                        f"{filter_name.upper()} overall value range: "
                        f"[{min_val:.2f}, {max_val:.2f}]"
                    )

        return True

    except Exception as e:
        logging.error(f"Error during processing: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process Sparrow emissions data with multi-level aggregation"
    )
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help=(
            f"Comma-separated years to download (e.g., 2023,2024). "
            f"Default: {min(DEFAULT_YEARS)}-{max(DEFAULT_YEARS)}"
        ),
    )
    parser.add_argument(
        "--filters",
        type=str,
        default=None,
        help=(
            f"Comma-separated filters to download (e.g., co2,no2). "
            f'Allowed: {", ".join(ALLOWED_FILTERS)}. Default: all filters'
        ),
    )
    parser.add_argument(
        "--fetch-data",
        action="store_true",
        help="Fetch fresh data from Sparrow API instead of using cached CSV",
    )
    args = parser.parse_args()

    try:
        # Parse and validate arguments
        years, filters = parse_and_validate_args(args)

        # Run main processing
        success = main(years, filters, fetch_fresh=args.fetch_data)

        if success:
            logging.info("Sparrow emissions processing completed successfully.")
        else:
            logging.error("Sparrow emissions processing failed.")
    except ValueError as e:
        logging.error(f"Validation error: {str(e)}")
        logging.error("Processing aborted.")
