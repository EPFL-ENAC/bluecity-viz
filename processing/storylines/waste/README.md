# Waste collection point clustering
This directory contains the code for clustering waste collection points in the city of Lausanne.

## overview

This project implements a capacitated spatial clustering algorithm to group waste collection points in Lausanne. The clustering algorithm takes into account:
- **Spatial proximity**: Points that are geographically close are grouped together
- **Capacity constraints**: Each cluster has a maximum weekly waste capacity (default 4000 kg/week)
- **Waste type**: Different waste types (household, paper, glass, organic) are clustered separately

The algorithm uses a three-phase approach:
1. **Pre-clustering**: K-means initialization to create many small micro-clusters
2. **Greedy merging**: Nearby clusters are merged while respecting capacity constraints
3. **Local improvement**: Iterative refinement by reassigning points to nearby clusters

## Files

- `waste.ipynb`: Jupyter notebook containing the complete analysis workflow with visualizations
- `waste.py`: Python script version of the clustering algorithm for automated processing
- `Makefile`: Build automation for data generation
- `final_waste_clusters.gpkg`: Output GeoPackage file containing clustered waste collection points
- `.gitignore`: Git ignore configuration

## Usage

### Using Make (recommended)
```bash
make generate-data
```

### Using Python directly
```bash
python waste.py
```

### Using Jupyter Notebook
Open `waste.ipynb` in Jupyter Lab or VS Code to run the analysis interactively.

### Requirements
- Python 3.x
- geopandas
- pandas
- numpy
- scikit-learn
- matplotlib

## Output

The script generates `final_waste_clusters.gpkg`, a GeoPackage file containing:
- **Geometry**: Point locations of waste collection sites
- **cluster**: Cluster ID (offset by 100×type_index to separate waste types)
- **type**: Waste type code (DI=household, PC=paper, VE=glass, DV=organic)
- **amount_week**: Weekly waste amount in kg
- **quartier**: Neighborhood name
- Additional metadata fields from the input data

The output can be visualized in QGIS or other GIS software, or loaded back into Python for further analysis.