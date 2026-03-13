import os
import pandas as pd
import geopandas as gpd
from shapely import Polygon

def create_square_polygon(e, n, size):
    """create square polygon of size ^ 2 meteres
    Args:
        e: E coordinates
        n: N coordinates
        size: Length and width of the polygon. Defaults to 100.
    """
    return Polygon([(e, n), (e + size, n), (e + size, n + size), (e, n + size)])

data_folder = os.path.join("data")

statpop_filename = os.path.join(data_folder, "ag-b-00.03-vz2022statpop", "STATPOP2022.csv")
statpop = pd.read_csv(statpop_filename, sep=';', encoding='utf-8', usecols=["E_KOORD", "N_KOORD", "RELI", "B22BTOT"])

statent_filename = os.path.join(data_folder, "ag-b-00.03-22-STATENT2022", "STATENT_2022.csv")
statent = pd.read_csv(statent_filename, sep=';', encoding='utf-8', usecols=["ERHJAHR", "E_KOORD", "N_KOORD", "RELI", "B08T", "B08EMPT", "B08VZAT"])

LAUSANNE_HULL_WKT = (
    "POLYGON ((6.6973149 46.4991489, 6.5474464 46.508319, 6.5441708 46.5091808, "
    "6.5429015 46.5134131, 6.5361596 46.5588201, 6.5949948 46.5926757, "
    "6.6582251 46.5991119, 6.7121747 46.571259, 6.7180473 46.5236707, "
    "6.7159339 46.5179337, 6.7123702 46.5099251, 6.7077559 46.5021425, "
    "6.7016307 46.4999401, 6.6973149 46.4991489))"
)

lausanne = gpd.GeoDataFrame(geometry=gpd.GeoSeries.from_wkt([LAUSANNE_HULL_WKT]), crs="EPSG:4326")

nodes_filename = os.path.join(data_folder, "lausanne_drive_nodes.gpkg")
nodes = gpd.read_file(nodes_filename, columns=["osmid", "geometry"])

common_crs = "EPSG:2056"

statpop_statent = statpop.merge(statent, on=["RELI", "N_KOORD", "E_KOORD"], how="outer", suffixes=("_statpop", "_statent"))

statpop_statent["geometry"] = statpop_statent.apply(lambda row: create_square_polygon(row["E_KOORD"], row["N_KOORD"], 100), axis=1)

statpop_statent = gpd.GeoDataFrame(statpop_statent, geometry="geometry", crs=common_crs)

pop_ent_laus = gpd.sjoin(statpop_statent, lausanne.to_crs(common_crs), how="inner", predicate="within")
pop_ent_laus.drop(columns=["index_right"], inplace=True)

# join each row in statpop_statent to the nearest node
nodes_data = nodes.to_crs(common_crs).sjoin_nearest(pop_ent_laus, how="right", distance_col="distance_to_node")

last_revision = nodes_data["ERHJAHR"].max()
nodes_data = nodes_data[nodes_data["ERHJAHR"] == last_revision]
print(f"Using data from year {last_revision}")

nodes_data.drop(columns=["RELI", "E_KOORD", "N_KOORD", "distance_to_node", "ERHJAHR"], inplace=True)

# Keep your existing dissolve
nodes_data = nodes_data.dissolve(by="osmid", aggfunc="sum")

# Reattach node point geometry by osmid
node_geoms = (
    nodes.to_crs(common_crs)[["osmid", "geometry"]]
    .drop_duplicates(subset="osmid")
    .set_index("osmid")
)

nodes_data = (
    nodes_data.drop(columns="geometry")
    .join(node_geoms, how="left")
)

nodes_data = gpd.GeoDataFrame(nodes_data, geometry="geometry", crs=common_crs)

nodes_data["population_percentile"] = nodes_data["B22BTOT"].rank(pct=True)
nodes_data["workers_percentile"] = nodes_data["B08EMPT"].rank(pct=True)
nodes_data["node_coef"] = (nodes_data["population_percentile"] + nodes_data["workers_percentile"]) / 2

nodes_data.to_file(os.path.join("lausanne_nodes_data.gpkg"), driver="GPKG")