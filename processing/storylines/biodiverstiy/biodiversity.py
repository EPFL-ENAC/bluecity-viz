from matplotlib import pyplot as plt
import contextily as ctx
import geopandas as gpd
import pandas as pd
import fiona
import os


data_dir = os.path.join(os.getcwd(), 'data')

gdb_path = os.path.join(data_dir, 'HabitatMap_v1_2_20251211_VD.gdb')
layers = fiona.listlayers(gdb_path)
areas = gpd.read_file(gdb_path, layer=layers[0], columns=['TypoCH_NUM', 'TypoCH', 'POLYID', 'geometry'])

roads_path = os.path.join(data_dir, 'lausanne_drive_edges.gpkg')
roads = gpd.read_file(roads_path, columns=['u', 'v', 'geometry'])

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
areas_lausanne = areas_lausanne[areas_lausanne["TypoCH"] != "4"] # Surfaces ouvertes
areas_lausanne = areas_lausanne[areas_lausanne["POLYID"] != 21691543] # Lac
areas_lausanne = areas_lausanne[~areas_lausanne["TypoCH"].str.startswith("STR")] # STR

# Ensure same CRS by reprojecting roads to match areas_lausanne
roads = roads.to_crs(areas_lausanne.crs)

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

#roads_areas["cluster_v1"] = pd.NA # Clusters based on the exact TypoCH code
roads_areas["cluster_v2"] = pd.NA # Clusters based on the first 3 characters of the TypoCH code (more general)

#roads_areas["cluster_v1"] = roads_areas["cluster_v1"].astype("Int64")
roads_areas["cluster_v2"] = roads_areas["cluster_v2"].astype("Int64")

roads_areas["TypoCH_v2"] = roads_areas["TypoCH"].str[:3]

cluster = 0

for (road_id, typo_ch), group_df in roads_areas.groupby(['road_id', 'TypoCH_v2']):
    if 'right' in group_df['side'].values and 'left' in group_df['side'].values:
        roads_areas.loc[group_df.index, 'cluster_v2'] = cluster
        cluster += 1

done = False

while not done:

    done = True
    for polyid, group_df in roads_areas.groupby('POLYID'):
        if group_df['cluster_v2'].nunique(dropna = True) > 1:

            done = False

            final_cluster = group_df['cluster_v2'].iloc[0]
            
            if pd.isna(final_cluster):
                final_cluster = group_df['cluster_v2'].iloc[1]
            
            for cluster_id in group_df['cluster_v2'].unique():
                if pd.isna(cluster_id):
                    continue
                roads_areas.loc[roads_areas['cluster_v2'] == cluster_id, 'cluster_v2'] = final_cluster
            break

# Drop duplicate rows
roads_areas = roads_areas.drop_duplicates(subset=['road_id', 'POLYID'], keep='first')
roads_areas = roads_areas.drop_duplicates(subset=['cluster_v2', 'POLYID'], keep='first')

# Drop rows with NA in cluster_v2
roads_areas = roads_areas[roads_areas["cluster_v2"].notna()]

roads_areas['area'] = roads_areas.geometry.area

roads_areas['total_area'] = roads_areas.groupby('cluster_v2')['area'].transform('sum')
roads_areas['max_area'] = roads_areas.groupby('cluster_v2')['area'].transform('max')

roads_areas['gain_marginal'] = roads_areas['total_area'] / roads_areas['max_area']

roads_areas["road_amount"] = roads_areas.groupby('cluster_v2')["road_id"].transform('nunique')

roads_areas["sous_types"] = roads_areas.groupby('cluster_v2')["TypoCH"].transform(lambda x: ', '.join(x.unique()))

roads_areas["road_geometry"] = roads_areas["road_geometry"].to_wkt()
roads_areas.to_file('roads_areas_clusters.gpkg', layer='roads_areas_clusters', driver='GPKG')

# Export habitat area per road edge (keyed by osmnx u, v)
roads_id_map = roads[['u', 'v']].copy()
roads_id_map.index.name = 'road_id'

road_habitat = roads_areas.groupby('road_id')['area'].sum().to_frame('habitat_area_m2')
road_habitat = road_habitat.join(roads_id_map)
road_habitat = road_habitat.dropna(subset=['u', 'v'])
road_habitat[['u', 'v', 'habitat_area_m2']].to_csv(
    os.path.join(data_dir, 'habitat_areas.csv'), index=False
)