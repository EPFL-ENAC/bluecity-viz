# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

BlueCity Viz is a geospatial urban analytics platform with three main components:
- **Frontend**: Vue 3 + MapLibre + Deck.gl SPA for interactive map visualization
- **Backend**: FastAPI service for traffic network analysis (graph routing, CO₂ estimation, betweenness centrality)
- **Processing**: Python/Jupyter tools for converting raw datasets into PMTiles

## Commands

### Root (from repo root)
```bash
make install        # Install all dependencies (frontend npm + backend/processing uv sync)
make dev            # Start both backend (port 8000) and frontend (port 5173) concurrently
make dev-frontend   # Frontend only
make dev-backend    # Backend only
make build          # Production build (type-check + vite build)
```

### Frontend (from `frontend/`)
```bash
npm run lint        # ESLint with auto-fix
npm run format      # Prettier
npm run type-check  # vue-tsc --noEmit
npm run test:unit   # Vitest
npm run schema      # Regenerate frontend/schema/parameters.schema.json from TypeScript types
```

### Backend (from `backend/`)
```bash
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload  # dev server
uv run python test_with_data.py    # integration test (requires lausanne.graphml)
uv run python test_api.py          # API tests
uv run ruff check app              # lint
uv run ruff format app             # format
```

## Architecture

### Frontend (`frontend/src/`)

**Stores (Pinia)** are the central state hub:
- `stores/trafficAnalysis.ts` — the most complex store; manages edge modifications, OD pair routing results, and all D3 color scales for the 6 visualization modes (frequency, delta, CO₂, CO₂-delta, betweenness, betweenness-delta)
- `stores/layers.ts`, `stores/apiKey.ts`, `stores/theme.ts` — map layer visibility, API key, theme

**Composables** encapsulate map logic:
- `composables/useDeckGLTrafficAnalysis.ts` — creates and updates Deck.gl `PathLayer`/`GeoJsonLayer`/`TextLayer` for traffic analysis overlays; reads from `trafficAnalysis` store to color edges
- `composables/useMapLogic.ts`, `useMapEvents.ts` — MapLibre map setup and event handling

**Services** (`services/trafficAnalysis.ts`) — thin HTTP client wrapping `fetch` calls to the backend `/api/v1/routes/*` endpoints.

**Config** (`config/`) — layer definitions for different SP0x sustainability indicator datasets (SP2 mobility, SP3 nature, SP4 waste, SP6 materials, etc.) served as PMTiles from S3.

**Design system** — the UI follows the "Workbench" design (EPFL design system,
Architecture sub-brand): Suisse Int'l, 1px hairlines, square corners, no shadow,
mono micro-labels, Blue City blue `#0500E1` as the only accent, red only for
delete. `assets/tokens.css` holds the `--bc-*` tokens plus the shared classes
(`.bc-micro`, `.bc-row`, `.bc-check`, `.bc-btn`, `.bc-seg`) and the dark block,
applied through `data-theme="dark"` on `<html>`. `plugins/vuetify.ts` re-themes
the few Vuetify components still used (`workbench` / `workbench-dark`). Build new
UI from `components/ui/` (`BcIcon`, `BcRow`, `BcSeg`, `BcSlider`, `BcDialogCard`),
not from raw `v-card` / `v-checkbox`.

**Layout**: one page, 360px sidebar on the left, map full-bleed, 340px analysis
dock on the right when a tool is open. There is no app bar and no drawer.

**Components** worth knowing:
- `views/HomeView.vue` — the shell: sidebar (header + four sections) and the map stage
- `components/sidebar/` — `InvestigationSection` (project tree, rename, share, delete),
  `DatasetsSection`, `LayersSection`, `ToolsSection`
- `components/panels/VisualizationsPanel.vue` — the map stage; mounts the map, the
  Deck.gl overlay, the tooltips and the dock
- `components/dock/` — `TrafficDock.vue` and `CvrpDock.vue`, one per analytics tool
- `MapLibreMap.vue` + `DeckGLOverlay.vue` — the main map canvas, Deck.gl renders on top of MapLibre
- `LegendMap.vue`, `ImpactStatistics.vue` — result display
- `components/dialogs/` — add sources, share, delete

**Basemap**: `utils/epflBasemap.ts` builds the EPFL "Trait" ink-on-paper style
(OpenFreeMap vector tiles, canvas textures). `stores/theme.ts` offers `trait`,
`trait-dark`, `style/light.json` and `style/none.json`; `isDark` drives both the
UI theme and the map ink. The UI follows the basemap.

### Backend (`backend/app/`)

The backend loads a **GraphML road network** (Lausanne) at startup via osmnx, then:
1. Pre-generates 500 research-sampled OD pairs (betweenness-centrality-weighted, lognormal distance distribution)
2. Serves routing and impact analysis via `/api/v1/routes/`

**Service layer** is modular:
- `services/graph_service.py` — orchestrator; holds all in-memory caches (`_edge_co2_cache`, `_edge_bc_cache`, `_route_edge_index`)
- `services/routing_engine.py` — igraph one-to-many Dijkstra (much faster than NetworkX for bulk routing)
- `services/bpr.py` — Bureau of Public Roads congestion model + betweenness centrality computation
- `services/co2_calculator.py` — grade-aware CO₂/km model
- `services/graph_helpers.py` — edge modification apply/restore, usage stats aggregation, graph serialization
- `services/impact_calculator.py` — computes summary statistics comparing before/after routing
- `services/node_sampling_service.py` + `services/sampling/` — research-based OD pair generation

**Key API endpoints** (`/api/v1/routes/`):
- `GET /graph` — full graph for Deck.gl visualization
- `GET /edge-geometries` — edge coordinates + travel time (GZip compressed)
- `POST /recalculate` — apply edge modifications (remove/speed-limit) and re-route all OD pairs, returning per-edge usage stats with delta, CO₂/km, and betweenness centrality

### Data Flow for Traffic Analysis

1. User clicks edges on map → `useDeckGLTrafficAnalysis` calls `cycleEdgeModification` on the store
2. User triggers recalculate → `MapControlsPanel` calls backend `POST /recalculate` with the modification list
3. Backend applies modifications, re-routes with igraph Dijkstra (optionally with BPR congestion), computes CO₂ and BC
4. Response `EdgeUsageStats[]` is stored in `trafficAnalysis` store → D3 color scales are recomputed
5. `useDeckGLTrafficAnalysis` reacts to store changes and rebuilds Deck.gl layers

### Processing (`processing/`)

Python notebooks and scripts using GeoPandas/uv for converting raw datasets (shapefiles, CSV) into PMTiles for S3 hosting. Managed with `uv sync` and run via Jupyter (`make notebook` from root).

## Configuration

Backend settings are in `backend/app/config.py` (pydantic-settings, reads `.env`):
- `GRAPH_PATH` — path to GraphML file (default: `data/lausanne.graphml`)
- `GEOJSON_PATH` — path to GeoJSON (default: `data/lausanne.geojson`)

The frontend always calls the backend on a relative `/api/v1/...` path. In dev,
`frontend/vite.config.ts` proxies `/api` and `/data` to `127.0.0.1:$BACKEND_PORT`,
so each checkout talks to its own backend.

## Dev servers and worktrees

Every checkout (the main one and each git worktree under `.claude/worktrees/<branch>`)
gets its own tmux session `bluecity-viz/<branch>` with one `dev` window of four titled
panes: `claude` (the left half, focused on attach), `backend`, `frontend` and
`shell` stacked on the right (`scripts/tmux-dev.sh`, or `make tmux-dev-all`;
`make go BRANCH=feat/x` creates the worktree and attaches, `wt create` alone
starts it detached through `.wt.toml`). Full guide: `docs/worktree-env/`.

- **Know where you are**: you are in a worktree exactly when `.env.worktree`
  exists at the repo root (same thing, your path contains `.claude/worktrees/`).
  The tmux panes, the claude one included, start with that file exported, so
  `echo $WT_BRANCH $BACKEND_PORT $FRONTEND_PORT` orients you instantly. In a
  shell without them, run `set -a; . .env.worktree; set +a` first.
- **Ports**: a worktree's `.env.worktree` holds its `BACKEND_PORT` /
  `FRONTEND_PORT` (hashed from `<repo>/<branch>`, 18xxx/19xxx, stepping past a
  pair another worktree holds); the main checkout uses 8000/5173. Read them
  from that file, never guess, and never start a second server on a port that
  is already served.
  `scripts/wt-open.sh [frontend|backend]` prints and opens the URL.
- **Reuse before starting**: the tmux session already runs both servers in its
  `backend` and `frontend` panes. If you must start one yourself,
  `set -a; . .env.worktree; set +a` first so uvicorn and vite pick the
  worktree's values.
- **Finish** a frontend or backend change by printing its URL:
  `http://localhost:$FRONTEND_PORT/` or `http://127.0.0.1:$BACKEND_PORT/docs`.
- **Checking your work**: read-only `curl` against your own `localhost` /
  `127.0.0.1` ports is pre-allowed in the common forms (bare, `-s`, `-sS`,
  `-fsS`, `-i`, `-I`), so hit your servers freely; write forms still prompt. The
  backend and frontend panes mirror their output to `.wt-logs/backend.log` and
  `.wt-logs/frontend.log` in the checkout root. When a server is down or
  misbehaving, read those (the tmux socket is outside your sandbox, so `tmux`
  commands will fail, the log files are the supported path).

### Working in a worktree, rules

- **You own exactly one branch**: the worktree's. Commit and push to it freely.
  Never push `dev` or `main`, never push another branch, never force-push.
  `scripts/git-push-guard.sh` refuses it in git itself (installed as the shared
  `pre-push` hook), and the session's deny rules refuse it before that. Landing
  into `dev` is a human's job, from the main checkout, with `scripts/wt-land.sh`.
- **Dev data is shared, not copied**: `frontend/public/geodata` and the
  `backend/data/*.csv` centroids are symlinks to the main checkout (they are
  gitignored and big). Read them, do not rewrite them in place.
- **`processing/`** is not installed in a worktree. Run `cd processing && uv sync`
  by hand if a task needs it.
- **Network**: read the web freely. Anything that writes outward
  (`curl -X POST`, `gh pr create`, and so on) or runs downloaded code
  (`curl … | sh`, `npx -y …`) prompts the user by design. Do not work around a
  prompt.

## Kubernetes Deployment

Kubernetes manifests are located in `dev/enack8s-app-config/epfl-bluecity/` (symlink to external repo).
Contains all YAML files for deployment configuration (Helm charts, K8s resources, etc.).

## Commit Convention

Follows [Conventional Commits](https://conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, etc.) — enforced via `commitlint.config.js`.
