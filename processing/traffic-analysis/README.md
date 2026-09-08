# Traffic Analysis — Data Pipeline

Generates the road network data required by the backend API and the frontend
map layer for the traffic simulation feature.

## How it works

```
OSM (via osmnx)
    │
    ▼
lausanne_network.py          ← Step 1: download + enrich
    │
    └── data/graph/lausanne_drive.graphml
             │
             ├── generate_graph_tiles.py   ← Step 2a: GeoJSON for the backend
             │       └── data/graph/lausanne_drive.geojson
             │
             └── generate_graph_tiles.py   ← Step 2b: PMTiles for the frontend
                     └── data/graph/lausanne_drive.pmtiles

make copy                    ← Step 3: copy outputs to their destinations
    ├── lausanne_drive.graphml  →  ../../backend/data/lausanne.graphml
    ├── lausanne_drive.geojson  →  ../../backend/data/lausanne.geojson
    └── lausanne_drive.pmtiles  →  ../../frontend/public/geodata/lausanne_drive.pmtiles
```

The backend loads `lausanne.graphml` at startup for routing and serves
`lausanne.geojson` as a static file for the frontend's Deck.gl layer.
The frontend also loads `lausanne_drive.pmtiles` directly as a vector tile
layer for interactive edge highlighting.

## The whole country

The scenario workbench used to run on Lausanne only. It now runs on any circle
the user draws in Switzerland, so the backend needs the country. A country
graph is about a million edges: too big to hold as a routing graph, so it is
written as a **graph store**, two parquet files cut in about 5 km grid cells.
The backend reads only the cells under the circle, which takes milliseconds.

```
switzerland-latest.osm.pbf (Geofabrik, ~520 MB)
    │
    ▼
build_swiss_graph.py         ← osmium filter, then tile by tile:
    │                          osmnx + speeds + elevation
    │
    └── ../../backend/data/swiss_graph/
             ├── nodes.parquet    one row group per cell
             ├── edges.parquet    one row group per cell
             ├── index.json       the grid and the counts per cell
             └── density.json     counts on a 1 km grid, for the picker
                      │
                      ├── generate_graph_tiles.py --store
                      │       └── ../../frontend/public/geodata/swiss_drive.pmtiles
                      │
                      └── make swiss-copy
                              └── ../../frontend/public/geodata/swiss_graph_density.json
```

```bash
make pbf-download          # once, ~520 MB from Geofabrik
make swiss-all             # elevation + store + tiles + density, about an hour
```

**The graph is built tile by tile.** osmnx cannot hold the country at once: fed
the national XML it grows past 20 GB and the kernel kills it. So the country is
cut in 4 by 3 tiles and each one is built on its own, on a rectangle a bit
larger than the piece it keeps. The margin matters, osmnx merges chains of
degree-2 nodes into one edge and a chain cut at a boundary would give a street
that stops in the middle of nowhere. A node belongs to exactly one tile and an
edge to the tile of its start node, so nothing is written twice or lost. On a
seam that cuts through a test circle the result differs from a single build by
one street out of 2959.

The densest tile (Zurich to St. Gallen) peaks around 5 GB and takes 95 seconds.
Each tile is cached in the work directory, so a run that dies picks up where it
stopped. On a machine with less memory, cut smaller tiles:

```bash
make swiss-store SWISS_TILES=6x5
```

Try it on a region first, it takes a minute:

```bash
make swiss-store SWISS_BBOX=6.4,46.4,6.9,46.7
```

`density.json` has its own grid, five times finer than the store's. The store
cells are 5 km because that is a good parquet row group, but the picker sums
them under a 3 km circle and assumes each cell is evenly filled. A town is not
spread evenly over 25 km2, so at 5 km the picker read 20 to 40 percent low and
said "too sparse" over towns the server accepts. At 1 km it lands within 3% of
the server everywhere we checked. The file is 527 kB for the country.

Elevation comes from swissALTIRegio, the national model swisstopo publishes as
one cloud optimised GeoTIFF. `make dem` does not fetch the 10 GB file: it reads
the 40 m overview the file already carries and writes a 360 MB local raster in
about 30 seconds. 40 m is the right scale for the slope of a street. DHM25 is
retired and its old URL now serves the 200 m model, which is too coarse.

Lausanne keeps its own GraphML: it is the default area, it has the finer
swissALTI3D elevation, and nothing about it changes.

The store is not committed. In production it is baked into the backend image
or downloaded at startup, and the two frontend files go to the CDN with
`make upload-frontend-geodata` from the repo root.

## Prerequisites

**Python environment** — install [uv](https://docs.astral.sh/uv/):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**tippecanoe** — converts GeoJSON to PMTiles:
```bash
# macOS
brew install tippecanoe

# Ubuntu / Debian
sudo apt-get install -y tippecanoe

# From source
git clone https://github.com/felt/tippecanoe.git
cd tippecanoe && make -j && sudo make install
```

Python packages are managed via `pyproject.toml` and installed automatically
by `uv run`.

## Quick Start

```bash
# From this directory:
cd processing/traffic-analysis

# One command — downloads OSM data, generates tiles, copies to the app:
make all

# To also include Swiss elevation data (adds ~2 GB download, enables grade data):
make elevation   # download rasters first
make all         # then generate and copy to the app
```

After `make all` the backend and frontend are ready to run.

## Step-by-step

### Step 0 (optional) — Download Swiss ALTI3D elevation rasters

```bash
make elevation
```

Downloads `.tif` raster tiles listed in `list_raster_elevation_lausanne.csv`
from swisstopo into `data/elevation/`.  This step is optional but adds node
elevations and edge grades to the graph, which the CO₂ model uses.

> Tip: skip elevation on first run to get a working backend faster, then
> re-run with `rm data/graph/lausanne_drive.graphml && make all` once you
> have the rasters.

### Step 1 — Build the network graph

```bash
make network
```

Runs `lausanne_network.py`, which:

1. Downloads the OSM `drive` network within the Lausanne hull polygon
2. Adds edge speeds (`speed_kph`) and travel times (`travel_time`) via OSMnx
3. If elevation rasters are present, adds node elevations (Swiss ALTI3D) and
   edge grades (rise / run)
4. Saves the result to `data/graph/lausanne_drive.graphml`
5. Exports `lausanne_drive_nodes.gpkg` and `lausanne_drive_edges.gpkg` for QGIS

The script is **idempotent**: if `lausanne_drive.graphml` already exists it
loads from disk instead of re-downloading.  Delete the file to force a fresh
download.

**CLI options:**

| Flag | Description |
|---|---|
| `--output PATH` | Override the GraphML output path |
| `--no-elevation` | Skip elevation enrichment (fast, no rasters needed) |
| `--no-gpkg` | Skip GeoPackage export |

```bash
# Quick test — no elevation
uv run python lausanne_network.py --no-elevation

# Custom output path
uv run python lausanne_network.py --output /tmp/test_graph.graphml
```

### Step 2 — Generate GeoJSON and PMTiles

```bash
make geojson   # → data/graph/lausanne_drive.geojson
make tiles     # → data/graph/lausanne_drive.pmtiles
```

Both targets run `generate_graph_tiles.py`.  Each edge in the output carries:
`u`, `v`, `name`, `highway`, `speed_kph`, `length`, `travel_time`.

The PMTiles vector tile layer is named `graph_edges` (zoom levels 6–20).

### Step 3 — Copy to the app

```bash
make copy
```

Copies the three output files to where the backend and frontend expect them:

| Source | Destination |
|---|---|
| `data/graph/lausanne_drive.graphml` | `backend/data/lausanne.graphml` |
| `data/graph/lausanne_drive.geojson` | `backend/data/lausanne.geojson` |
| `data/graph/lausanne_drive.pmtiles` | `frontend/public/geodata/lausanne_drive.pmtiles` |

## All Makefile targets

| Target | Description |
|---|---|
| `make all` | `network` → `tiles` → `copy` |
| `make elevation` | Download Swiss ALTI3D rasters |
| `make network` | Build `lausanne_drive.graphml` |
| `make geojson` | Build `lausanne_drive.geojson` |
| `make tiles` | Build `lausanne_drive.pmtiles` |
| `make copy` | Copy outputs to backend/ and frontend/ |
| `make clean` | Remove generated GeoJSON and PMTiles |
| `make clean-all` | Also remove copied files from app folders |

## File reference

```
processing/traffic-analysis/
├── lausanne_network.py              Step 1: OSM download + elevation enrichment
├── generate_graph_tiles.py          Step 2: GraphML → GeoJSON / PMTiles
├── download_elevation_data.py       Step 0: Swiss ALTI3D raster downloader
├── Makefile                         Pipeline automation
├── pyproject.toml                   Python dependencies
├── list_raster_elevation_lausanne.csv  Elevation tile URLs
├── data/
│   ├── graph/
│   │   ├── lausanne_drive.graphml   Enriched road network (pipeline output)
│   │   ├── lausanne_drive.geojson   Edge geometry (pipeline output)
│   │   ├── lausanne_drive.pmtiles   Vector tiles  (pipeline output)
│   │   ├── lausanne_drive_nodes.gpkg
│   │   └── lausanne_drive_edges.gpkg
│   └── elevation/
│       └── *.tif                    Swiss ALTI3D rasters (downloaded)
└── traffic_analysis.py              Exploratory PoC (requires external data)
```

## Checking a store

Two scripts in `backend/scripts/` read a store, neither is part of the pipeline:

```bash
cd ../../backend
# Cut the Lausanne circle out of the country store and compare it with the
# GraphML the backend loads today: road types, road length, extra streets.
uv run python scripts/lausanne_parity.py data/swiss_graph data/lausanne.graphml
# Write a store from a single GraphML, without the country build.
uv run python scripts/graphml_to_store.py data/lausanne.graphml data/one_city
```

## Troubleshooting

**`tippecanoe: command not found`**
Install tippecanoe (see Prerequisites above).

**`Graph file not found`**
Run from inside `processing/traffic-analysis/`.  The GraphML path is relative
to the current directory.

**`No elevation rasters found`**
Run `make elevation` before `make network`, or use `--no-elevation` to skip.

**Permission denied on `make copy`**
Check that `../../backend/data/` and `../../frontend/public/geodata/` are
writable.  From the repo root: `ls -la backend/data frontend/public/geodata`.
