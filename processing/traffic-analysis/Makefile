.PHONY: help elevation network geojson tiles copy all clean clean-all pbf-download pbf-lausanne \
        dem swiss-store swiss-tiles swiss-copy swiss-all

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GRAPH_DIR          := data/graph
ELEVATION_DIR      := data/elevation
FRONTEND_GEODATA   := ../../frontend/public/geodata
BACKEND_DATA       := ../../backend/data

PBF_CACHE_DIR      := .data/geofabrik
OSM_PBF_SWISS      := $(PBF_CACHE_DIR)/switzerland-latest.osm.pbf
OSM_PBF_ALL        := .data/lausanne-all.osm.pbf
OSM_PBF_FILTERED   := data/lausanne-filtered.osm.pbf

# ---------------------------------------------------------------------------
# Derived file names
# ---------------------------------------------------------------------------

DRIVE_GRAPHML      := $(GRAPH_DIR)/lausanne_drive.graphml
DRIVE_GEOJSON      := $(GRAPH_DIR)/lausanne_drive.geojson

BACKEND_GRAPHML    := $(BACKEND_DATA)/lausanne.graphml
BACKEND_GEOJSON    := $(BACKEND_DATA)/lausanne.geojson

# The whole country, for the "pick any area" feature
SWISS_STORE        := $(BACKEND_DATA)/swiss_graph
SWISS_DEM_DIR      := data/elevation-ch
SWISS_DEM          := $(SWISS_DEM_DIR)/swissaltiregio.tif
SWISS_PMTILES      := $(FRONTEND_GEODATA)/swiss_drive.pmtiles
SWISS_DENSITY      := $(FRONTEND_GEODATA)/swiss_graph_density.json
# A small region to try the pipeline on: minutes instead of an hour.
SWISS_BBOX         :=

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:
	@echo "Traffic Analysis — data pipeline"
	@echo "================================="
	@echo ""
	@echo "Bootstrap (first time):"
	@echo "  make pbf-download   Download Switzerland OSM PBF (~700 MB)"
	@echo "  make pbf-lausanne   Extract & filter Lausanne transit PBF"
	@echo "  make all            Build full graph + tiles"
	@echo ""
	@echo "Individual steps:"
	@echo "  make elevation   Download Swiss ALTI3D elevation rasters (optional)"
	@echo "  make network     Build OSM graph with speeds, elevation & transit enrichment"
	@echo "  make geojson     Convert GraphML → GeoJSON  (backend edge geometry)"
	@echo "  make copy        Copy outputs to backend/ and frontend/"
	@echo ""
	@echo "Whole country (pick any area):"
	@echo "  make dem            Download the national elevation raster (~360 MB, 30 s)"
	@echo "  make swiss-store    Build the country graph store (~1 h, 16 GB of RAM)"
	@echo "  make swiss-tiles    Cut the country network into PMTiles"
	@echo "  make swiss-copy     Copy density.json to the frontend"
	@echo "  make swiss-all      The three above"
	@echo "  Try it small first:  make swiss-store SWISS_BBOX=6.4,46.4,6.9,46.7"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       Remove generated GeoJSON and PMTiles"
	@echo "  make clean-all   Also remove copies in backend/ and frontend/"
	@echo "  make help        Show this message"
	@echo ""
	@echo "Requirements: uv  +  tippecanoe  +  wget  +  osmium"
	@echo "  tippecanoe: brew install tippecanoe  /  https://github.com/felt/tippecanoe"
	@echo "  osmium:     brew install osmium-tool /  apt install osmium-tool"

# ---------------------------------------------------------------------------
# Step 0 (optional) — Download Swiss ALTI3D elevation rasters
# ---------------------------------------------------------------------------

elevation:
	@echo "Downloading Swiss ALTI3D elevation rasters..."
	@mkdir -p $(ELEVATION_DIR)
	uv run python download_elevation_data.py
	@echo "✓ Elevation data saved to $(ELEVATION_DIR)/"

# ---------------------------------------------------------------------------
# Step 0b (optional) — Download and extract Lausanne transit PBF
# ---------------------------------------------------------------------------

pbf-download: ## Download latest OSM PBF file for Switzerland
	@rm -rf $(PBF_CACHE_DIR)
	@mkdir -p $(PBF_CACHE_DIR)
	wget https://download.geofabrik.de/europe/switzerland-latest.osm.pbf -O $(OSM_PBF_SWISS)

pbf-lausanne: ## Extract OSM data for Lausanne area and filter to transit features
	@rm -f $(OSM_PBF_ALL)
	osmium extract -b 6.5,46.5,6.8,46.6 $(OSM_PBF_SWISS) -o $(OSM_PBF_ALL)
	@mkdir -p data
	osmium tags-filter $(OSM_PBF_ALL) --overwrite -o $(OSM_PBF_FILTERED) \
		n/public_transport n/highway=bus_stop n/railway \
		a/public_transport \
		nwr/route=bus,tram,train,subway,trolleybus,light_rail,ferry,monorail \
		r/type=route_master \
		r/public_transport=stop_area
	@echo "✓ Filtered PBF saved to $(OSM_PBF_FILTERED)"

# ---------------------------------------------------------------------------
# Step 1 — Download OSM graph and enrich (speeds, travel times, elevation)
# ---------------------------------------------------------------------------
#
# If $(OSM_PBF_FILTERED) exists, transit enrichment uses it (local, fast).
# Otherwise the enrichment falls back to the Overpass API.
#
# To force a fresh download, delete $(DRIVE_GRAPHML) first:
#   rm data/graph/lausanne_drive.graphml
# ---------------------------------------------------------------------------

# Pass --pbf only when the filtered PBF is present
_PBF_FLAG = $(if $(wildcard $(OSM_PBF_FILTERED)),--pbf $(OSM_PBF_FILTERED),)
_TRANSIT_FLAG = --transit-output $(FRONTEND_GEODATA)

network: $(DRIVE_GRAPHML)

$(DRIVE_GRAPHML): lausanne_network.py
	@echo "Building Lausanne road network..."
	@mkdir -p $(GRAPH_DIR)
	uv run python lausanne_network.py --output $(DRIVE_GRAPHML) $(_PBF_FLAG) $(_TRANSIT_FLAG)
	@echo "✓ Network saved to $(DRIVE_GRAPHML)"

# ---------------------------------------------------------------------------
# Step 2a — GraphML → GeoJSON  (backend edge geometry)
# ---------------------------------------------------------------------------

geojson: $(DRIVE_GEOJSON)

$(DRIVE_GEOJSON): $(DRIVE_GRAPHML) generate_graph_tiles.py
	@echo "Generating GeoJSON from $(DRIVE_GRAPHML)..."
	uv run python generate_graph_tiles.py $(DRIVE_GRAPHML) --geojson $(DRIVE_GEOJSON)
	@echo "✓ GeoJSON saved to $(DRIVE_GEOJSON)"

# ---------------------------------------------------------------------------
# Step 3 — Copy outputs to backend/ and frontend/
# ---------------------------------------------------------------------------

copy: geojson
	@echo "Copying files to backend/ and frontend/..."
	@mkdir -p $(FRONTEND_GEODATA) $(BACKEND_DATA)
	@cp $(DRIVE_GEOJSON)  $(BACKEND_GEOJSON)
	@echo "  ✓ $(BACKEND_GEOJSON)"
	@cp $(DRIVE_GRAPHML)  $(BACKEND_GRAPHML)
	@echo "  ✓ $(BACKEND_GRAPHML)"
	@cp $(DRIVE_GEOJSON)  $(FRONTEND_GEODATA)/lausanne.geojson
	@echo "  ✓ $(FRONTEND_GEODATA)/lausanne.geojson"
	@echo "✓ Copy complete"

# ---------------------------------------------------------------------------
# The whole country — the graph store the backend cuts areas from
# ---------------------------------------------------------------------------
#
# Needs the Geofabrik PBF ('make pbf-download') and, for the slopes, the DHM25
# tiles ('make dem'). The graph step is long and hungry: about an hour and
# 16 GB of RAM for the country. Set SWISS_BBOX to try it on a region first.
# ---------------------------------------------------------------------------

_SWISS_BBOX_FLAG = $(if $(SWISS_BBOX),--bbox $(SWISS_BBOX),)
# Always passed. make expands a wildcard before running anything, so testing
# for the raster here would miss the one 'make dem' is about to download. The
# script reads whatever .tif it finds in the directory, and says so when the
# directory is empty.
_SWISS_DEM_FLAG  = --dem $(SWISS_DEM_DIR)

dem: $(SWISS_DEM) ## Download the national elevation raster (swissALTIRegio at 40 m)

$(SWISS_DEM):
	uv run python download_swiss_dem.py --output $(SWISS_DEM)

swiss-store: ## Build the country graph store the backend reads
	@test -f $(OSM_PBF_SWISS) || (echo "Missing $(OSM_PBF_SWISS). Run 'make pbf-download'." && exit 1)
	@mkdir -p $(BACKEND_DATA)
	uv run python build_swiss_graph.py \
		--pbf $(OSM_PBF_SWISS) \
		--store $(SWISS_STORE) \
		$(_SWISS_DEM_FLAG) $(_SWISS_BBOX_FLAG)
	@echo "✓ Store written to $(SWISS_STORE)"

swiss-tiles: ## Cut the country network into PMTiles for the picker backdrop
	@test -d $(SWISS_STORE) || (echo "Missing $(SWISS_STORE). Run 'make swiss-store'." && exit 1)
	@mkdir -p $(FRONTEND_GEODATA)
	uv run python generate_graph_tiles.py --store $(SWISS_STORE) $(SWISS_PMTILES)
	@echo "✓ $(SWISS_PMTILES)"

swiss-copy: ## The small file the picker sums under the circle
	@test -f $(SWISS_STORE)/density.json || (echo "Missing the store. Run 'make swiss-store'." && exit 1)
	@mkdir -p $(FRONTEND_GEODATA)
	@cp $(SWISS_STORE)/density.json $(SWISS_DENSITY)
	@echo "✓ $(SWISS_DENSITY)"

swiss-all: dem swiss-store swiss-tiles swiss-copy

# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
#
# Elevation is intentionally not included here because it requires a large
# download (~2 GB) that is optional.  Run 'make elevation' separately before
# 'make all' if you want grade data in the graph.
# ---------------------------------------------------------------------------

all: network copy

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

clean:
	@echo "Removing generated files in $(GRAPH_DIR)/..."
	@rm -f $(DRIVE_GEOJSON)
	@echo "✓ Clean complete"

clean-all: clean
	@echo "Removing copied files from backend/ and frontend/..."
	@rm -f $(BACKEND_GEOJSON) $(BACKEND_GRAPHML)
	@echo "✓ All clean"
