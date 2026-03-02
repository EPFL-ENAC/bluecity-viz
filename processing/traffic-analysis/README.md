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
