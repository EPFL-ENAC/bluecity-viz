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
   https://enacit4r-cdn.epfl.ch/bluecity/(your-file-name)
   ```
2. No further configuration is needed on the server as the bucket handles availability automatically.
3. You never write that host in the code. `baseUrl` in
   `frontend/src/config/layerTypes.ts` points at this CDN in production and at
   `/geodata` in dev, where the files are read from the local checkout.

---

## 3. Editing the Frontend

One object per layer, in one file. The map, the layers panel and the legend
all read the same registry, there is nothing else to wire.

### a. Declare the source and the layers

Open the config file of the work package, for example
`frontend/src/config/sp3_nature.ts`, or create a new one next to them.

```ts
import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

const noiseSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'lausanne_noise',            // saved in the investigations, do not rename
  label: 'Noise levels - SP3',     // shown in the datasets panel
  attribution: 'Ville de Lausanne',
  url: `pmtiles://${baseUrl}/lausanne_noise.pmtiles`,
  minzoom: 5
}

export const noiseGroup = defineGroup({
  id: 'sp3_noise',
  label: 'SP3 Noise',
  multiple: false,                 // true lets the user tick several layers
  layers: [
    defineLayer({
      id: 'lausanne_noise_day',    // the map layer id becomes <id>-layer
      label: 'Noise, day',
      unit: 'dB',
      info: 'Average noise level between 6am and 10pm.',
      source: noiseSource,
      encoding: {
        kind: 'sequential',
        property: 'lden',
        domain: [45, 55, 65, 75],
        scheme: ['#f7f7f7', '#fdae61', '#d73027', '#7f0000']
      },
      layer: {
        type: 'fill',
        'source-layer': 'lausanne_noise',   // the layer name inside the pmtiles
        paint: { 'fill-opacity': 0.8 }
      }
    })
  ]
})
```

`defineLayer` fills the layer id and the source id, and turns the `encoding`
into the paint expression. Use `kind: 'categorical'` for a value per class:

```ts
encoding: {
  kind: 'categorical',
  property: 'zone',
  categories: [
    { value: 'Residential', color: '#2E8B57' },
    { value: 'Industrial', color: '#8A2BE2' }
  ],
  defaultColor: '#757575'
}
```

The encoding is what the legend shows, so a layer that has one gets its legend
for free, with a colour ramp or one checkbox per category. A layer whose colour
is not a plain ramp (a hash, a `case`) just leaves `encoding` out and writes the
paint by hand. It then has no legend.

### b. Add the group to the registry

In `frontend/src/config/mapConfig.ts`, add the group to the `datasets` list:

```ts
const datasets: LayerGroup[] = [
  sp2MobilityGroup,
  sp3NatureGroup,
  noiseGroup,
  ...
]
```

That is the whole wiring. The layers, the sources and the groups are all read
from this list. The order of the list is the order the layers are drawn in and
the order of the datasets panel, so put a background layer before the layers
that must cover it.

The map loads a source the first time one of its layers is shown, so adding a
dataset costs nothing until someone ticks it.

### c. Check it

```bash
cd frontend
npx vitest run        # the registry snapshot fails, see below
npm run dev
```

The snapshot test in `src/config/__tests__/mapConfig.spec.ts` holds the whole
registry, so it fails on any new layer. Read the diff, make sure it only shows
what you added, then record it:

```bash
npx vitest run -u
```

Open the app, add the dataset in the datasets panel, tick the layer and check
the map and the legend.
