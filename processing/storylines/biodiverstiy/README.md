# Biodiversity Area Clustering
This directory contains the code for identifying and clustering biodiversity areas near roads in the city of Lausanne.

## Overview

This project implements a spatial analysis pipeline to identify biodiversity corridors along roads in Lausanne. The clustering algorithm takes into account:
- **Spatial proximity to roads**: Biodiversity areas within a buffer distance (default 10m) of roads are identified
- **Biodiversity type compatibility**: Areas are grouped based on similar habitat types (TypoCH classification)
- **Road connectivity**: Clusters are formed where similar biodiversity areas exist on both sides of a road segment

The algorithm uses a multi-phase approach:
1. **Data filtering**: Select relevant biodiversity areas within Lausanne, excluding built surfaces, transport zones, and water bodies
2. **Road proximity analysis**: Identify biodiversity areas within buffer distance of road network using spatial joins
3. **Initial clustering**: Create clusters where biodiversity areas of the same type exist on both sides of a road
4. **Cluster merging**: Connect adjacent clusters that share biodiversity areas (POLYIDs)
5. **Statistical enrichment**: Calculate cluster metrics including total area, maximum area, marginal gain, and road count

## Files

- `biodiversity.ipynb`: Jupyter notebook containing the complete analysis workflow with interactive visualizations
- `biodiversity.py`: Python script version of the clustering algorithm for automated processing
- `DataAccess.ipynb`: Notebook for data download and access
- `DataAccess.py`: Python script for data download
- `Makefile`: Build automation for data generation
- `roads_areas_clusters.gpkg`: Output GeoPackage file containing clustered biodiversity areas with metadata
- `.gitignore`: Git ignore configuration

## Input Data

The clustering algorithm requires the following input data files, which should be placed in the [data/](data/) directory:

- `Lebensraumkarte_v1_1_VD_20241025.gdb`: GeoDB file containing biodiversity habitat classification data for Canton Vaud with TypoCH codes
- `lausanne_drive_edges.gpkg`: GeoPackage file containing the road network (LineStrings) for Lausanne
- `Lausanne Districts.gpkg`: GeoPackage file containing polygon boundaries of Lausanne districts for spatial analysis

All of these files are available in the shared OneDrive folder.

## Usage

### Using Make (recommended)
```bash
make generate-data
```

### Using Python directly
```bash
python biodiversity.py
```

### Using Jupyter Notebook
Open `biodiversity.ipynb` in Jupyter Lab or VS Code to run the analysis interactively with visualizations.

### Requirements
- Python 3.x
- geopandas
- pandas
- matplotlib
- contextily
- geoviews
- hvplot
- fiona
- shapely

## Output

The script generates `roads_areas_clusters.gpkg`, a GeoPackage file containing:
- **Geometry**: Polygon geometries of biodiversity areas
- **cluster_v2**: Cluster ID (groups of connected biodiversity areas along roads)
- **POLYID**: Unique identifier for each biodiversity area polygon
- **TypoCH**: Full biodiversity habitat type code
- **TypoCH_v2**: Simplified habitat type (first 3 characters)
- **TypoCH_NUM**: Numeric habitat type code
- **road_id**: ID of the nearby road segment
- **side**: Whether the area is on the left or right side of the road
- **area**: Area of the biodiversity polygon in square meters
- **total_area**: Total area of all polygons in the cluster
- **max_area**: Area of the largest polygon in the cluster
- **gain_marginal**: Ratio of total area to maximum area (> 1 indicates multiple areas)
- **road_amount**: Number of unique road segments associated with the cluster
- **road_geometry**: WKT representation of the buffered road geometry

The output can be visualized in QGIS or other GIS software, or loaded back into Python for further analysis.

## Biodiversity Classification

The TypoCH classification system categorizes habitat types:
- **1-3**: Natural and semi-natural vegetation (forests, meadows, wetlands)
- **4**: Open surfaces (excluded from analysis)
- **5**: Built surfaces (excluded from analysis)
- **8**: Transport zones (excluded from analysis)
- **9**: Special zones (excluded from analysis)

The analysis focuses on natural biodiversity areas (types 1-3) that could benefit from road crossing infrastructure or connectivity improvements.