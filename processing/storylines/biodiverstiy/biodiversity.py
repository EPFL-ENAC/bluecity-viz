import pandas as pd
import geopandas as gpd
from matplotlib import pyplot as plt
import fiona
import os


data_dir = os.path.join(os.getcwd(), 'data')

gdb_path = os.path.join(data_dir, 'Lebensraumkarte_v1_1_VD_20241025.gdb')
layers = fiona.listlayers(gdb_path)
areas = gpd.read_file(gdb_path, layer=layers[0], columns=['TypoCH_NUM', 'TypoCH', 'POLYID', 'geometry'])

roads_path = os.path.join(data_dir, 'lausanne_drive_edges.gpkg')
roads = gpd.read_file(roads_path, columns=['geometry'])


buffer_distance = 10  # meters

# select only biodiversity areas within Lausanne
lausanne_boundary = gpd.read_file(os.path.join(data_dir, 'Lausanne Districts.gpkg'), columns=['geometry'])
lausanne_boundary["geometry"] = lausanne_boundary.geometry.buffer(buffer_distance)  # includes outside areas that are close to the boundary
xmin, ymin, xmax, ymax = lausanne_boundary.total_bounds

# Clip the areas to the bounding box of Lausanne and remove unwanted areas
areas_lausanne = areas.cx[xmin:xmax, ymin:ymax]
areas_lausanne = areas_lausanne[~areas_lausanne["TypoCH"].str.startswith("9")] # Zones spéciales
areas_lausanne = areas_lausanne[~areas_lausanne["TypoCH"].str.startswith("8")] # Zones de trasport
areas_lausanne = areas_lausanne[~areas_lausanne["TypoCH"].str.startswith("5")] # Surfaces bâties
areas_lausanne = areas_lausanne[~areas_lausanne["TypoCH"].str.startswith("4")] # Surfaces ouvertes
areas_lausanne = areas_lausanne[areas_lausanne["POLYID"] != 21691543] # Lac


# Create a buffered version of roads without modifying the original
roads_buffered = roads.copy()
roads_buffered["road_id"] = roads_buffered.index
roads_buffered['geometry'] = roads_buffered.geometry.buffer(buffer_distance)

# Spatial join - this will give you road geometry
roads_areas = gpd.sjoin(roads_buffered, areas_lausanne, how='inner', predicate='intersects')

# To keep BOTH geometries, rename the road geometry and add area geometry
roads_areas = roads_areas.rename(columns={'geometry': 'road_geometry'})
# Add the area geometry by merging with original areas
roads_areas = roads_areas.merge(
    areas_lausanne[['POLYID', 'geometry']], 
    on='POLYID', 
    how='left'
).rename(columns={'geometry': 'area_geometry'})

roads_areas.drop(columns=['index_right'], inplace=True)

# Set which geometry you want as the active geometry (area in your case)
roads_areas = roads_areas.set_geometry('area_geometry')

road_centroids_x = roads_areas['road_geometry'].centroid.x
area_centroids_x = roads_areas['area_geometry'].centroid.x
roads_areas["side"] = (road_centroids_x < area_centroids_x).map({True: 'left', False: 'right'})

roads_areas["cluster"] = None

# Create the clusters
cluster = 0

for road in roads_areas['road_id'].unique():
    for area_type in roads_areas['TypoCH'].unique():
        mask = (roads_areas['road_id'] == road) & (roads_areas['TypoCH'] == area_type)
        roads_areas.loc[mask, 'cluster'] = cluster
        cluster += 1

# Save data

roads_areas["road_geometry"] = roads_areas["road_geometry"].to_wkt()
roads_areas.to_file(os.path.join(data_dir, 'roads_areas_clusters.gpkg'), layer='roads_areas_clusters', driver='GPKG')