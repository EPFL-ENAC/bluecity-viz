# Updating Datasets for the Application

This guide outlines the process for updating datasets in the application. It is divided into three sections:

1. **Processing Data**
2. **Uploading Data to the Server**
3. **Editing the Frontend**

---

## 1. Processing Data

### Prerequisites

Ensure you have the following tools installed:

- **GDAL**: For processing geospatial data.
- **Tippecanoe**: For creating PMTiles.

### Step-by-Step Guide

#### a. Convert Data to GeoJSON

##### Shapefiles to GeoJSON

1. Navigate to the directory containing your shapefiles:
   ```bash
   cd path/to/shapefiles
   ```
2. Convert the shapefile to GeoJSON and reproject it to WGS 84 (EPSG:4326):
   ```bash
   ogr2ogr -t_srs EPSG:4326 output.geojson input.shp
   ```
   Example from history:
   ```bash
   ogr2ogr -t_srs EPSG:4326 swissBOUNDARIES3D_1_5_TLM_geojson.json swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET.shp
   ```

##### CSV to GeoJSON

1. To process CSV files into GeoJSON, refer to the `process.py` script in the `Population and Households Statistics` folder. This script includes logic for transforming grid points into polygons (e.g., squares).

   ```bash
   python process.py input.csv output.geojson
   ```

   The associated `Makefile` provides predefined commands to streamline the processing workflow. Example:

   ```bash
   make generate-data
   ```

   Adjust the `Makefile` variables as needed for your input and output files.

2. Review the `process.py` script for specific customization options, such as grid size or coordinate transformations, to ensure proper formatting of your data into GeoJSON.

##### Other Formats to GeoJSON

1. If your data is in another format supported by GDAL, convert it using a similar `ogr2ogr` command:
   ```bash
   ogr2ogr -f GeoJSON -t_srs EPSG:4326 output.geojson input.file
   ```

#### b. Prepare GeoJSON for PMTiles (Optional)

If your dataset has too many dimensions, ensure the GeoJSON is in 2D format before generating PMTiles:

1. Convert geometries to 2D if necessary:
   ```bash
   ogr2ogr -f GeoJSON -dim 2 output_2D.geojson input.geojson
   ```
   Example:
   ```bash
   ogr2ogr -f GeoJSON -dim 2 swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET_2D.geojson swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET.geojson
   ```

#### c. Generate PMTiles

1. Use `tippecanoe` to generate PMTiles from GeoJSON. The `Makefile` in the `Population and Households Statistics` folder includes a convenient target for Tippecanoe:

   ```bash
   make generate-pmtiles
   ```

2. For finer control, directly use the following command to coalesce polygons and create optimized PMTiles:

   ```bash
   tippecanoe --force -zg --coalesce-densest-as-needed --read-parallel -o output.pmtiles input.geojson
   ```

3. **Additional Tippecanoe Options:**

   - `--accumulate-attribute=GTOT:mean`: Calculates the mean of the attribute `GTOT` across features aggregated during tile generation. This is useful for continuous data like averages or densities.
   - `--extend-zooms-if-still-dropping`: Ensures that tiles continue to be created at higher zoom levels if significant data is still being dropped at the current zoom level. This helps maintain data integrity for detailed visualization.

4. Review the `Makefile` and `process.py` for examples of integrating Tippecanoe commands into the processing pipeline.
   - Create PMTiles with default settings:
     ```bash
     tippecanoe -zg --projection=EPSG:4326 -o swissBOUNDARIES3D_1_5_TLM_tiles.pmtiles -l swissBOUNDARIES3D_1_5_TLM_geojson.json
     ```
   - Customize zoom levels:
     ```bash
     tippecanoe --force -z12 -U 2 --read-parallel -o hoheitsgebiet.pmtiles swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET_2D.geojson
     ```

---

## 2. Uploading Data to the S3 Bucket

### Step-by-Step Guide

#### a. Upload Files to the S3 Bucket

1. Open the S3 web interface: [https://s3.epfl.ch/\_/s3browser](https://s3.epfl.ch/_/s3browser)
2. Log in using the provided access and secret key credentials.
   - **Warning**: These credentials are sensitive. Do not share them.
3. Use the web interface to upload your processed files (e.g., GeoJSON or PMTiles).

#### b. Confirm File Accessibility

1. Once uploaded, the files will be automatically available at the designated URL:
   ```
   https://enacit4r-cdn.epfl.ch/urbes-viz/(your-file-name)
   ```
2. No further configuration is needed on the server as the bucket handles availability automatically.

---

## 3. Editing the Frontend

### Step-by-Step Guide

#### a. Add Dataset URL to the Layer Selector

1. Open the `LayerSelector.vue` component:
   ```
   frontend/src/components/LayerSelector.vue
   ```
2. Add the dataset’s URL and metadata to the `layers` array.

#### b. Update the Map Component

1. Open the `MapLibreMap.vue` component:
   ```
   frontend/src/components/MapLibreMap.vue
   ```
2. Add the new dataset as a source and layer:
   ```javascript
   map.addSource("new-layer", {
     type: "vector",
     url: "https://enacit4r-cdn.epfl.ch/urbes-viz/(your-file-name)",
   });
   map.addLayer({
     id: "new-layer",
     type: "fill",
     source: "new-layer",
     "source-layer": "layer-name",
     paint: {
       "fill-color": "#888",
       "fill-opacity": 0.4,
     },
   });
   ```

#### c. Test the Integration

1. Run the development server:
   ```bash
   npm run dev
   ```
2. Verify the dataset is visible and behaves as expected on the map.
