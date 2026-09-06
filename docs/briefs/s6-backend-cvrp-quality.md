You are in a git worktree (branch fix/backend-cvrp-quality). Read CLAUDE.md first: ports are
in .env.worktree, the backend pane runs uvicorn --reload, never push dev or main. Another
session (perf/backend-routing) rewrites graph_service.py, routing_engine.py, bpr.py,
graph_helpers.py, impact_calculator.py, sampling/*, models/route.py and routes.py at the
same time. Do not edit those. Your area: CVRP, main.py, tests, container, API hygiene.

## Verified facts (file:line on dev 100b7c2)

1. Correctness bug: app/services/cvrp_service.py:164 `unique_ig_nodes = list(set(...))` has
   arbitrary order, and _create_cvrp_model (:208-213) indexes od_distance positionally
   against m.locations, which is built as [depot] + clients in node_df row order. The
   distance matrix given to the solver does not match the locations. Also :167-169
   inaccessible_indices holds POSITIONS but :200 tests a node_ig VALUE against it. Fixing
   this changes the solver's results (for the better); the rendered routes use a separate,
   correctly ordered loc_to_ig at :326-329.
2. :208-213 m.add_edge in a Python double loop over ~1,269 locations = 1.6 M calls per
   solve. pyvrp can take a full matrix. :353-355 and :383-385 call get_shortest_paths AND a
   redundant g_ig.distances() per segment. :617 graph.copy() runs on the event loop before
   asyncio.to_thread (:632), and outside the routing lock. :51 a private
   _networkx_to_igraph_with_indices duplicates sampling/igraph_utils.py and calls
   ox.graph_to_gdfs just to get an index.
3. backend/cvrp_refactored.py is 1,286 dead lines. Also dead: models/route.Edge (leave it,
   other session owns the file), CO2Calculator.calculate_route_co2 (leave), Settings.geojson_path
   (yours, config.py). List the dead code you cannot delete in the PR.
4. No tests run anywhere: test_api.py / test_with_data.py / test_cvrp.py / test_co2.py /
   test_node_sampling.py are __main__ scripts that need a running server and the 11 MB
   graph; test_api.py posts a removed `edges_to_remove` field and asserts nothing.
   backend/Makefile lint/format call flake8 and black, which are not installed.
5. main.py:84-90 CORS allow_origins=["*"] with allow_credentials=True. No auth on the backend
   (stores/apiKey.ts only decorates the CDN URL). models/cvrp.py waste_type is a bare str
   though WASTE_TYPES is a fixed tuple. 7 copies of `except Exception -> HTTPException(500,
   str(e))` leak internals (5 in routes.py, not yours); cvrp.py:35-38 already has the better
   typed pattern.
6. Dockerfile: no .dockerignore (COPY . . brings notebooks, __pycache__, a local .venv if
   present), `uv sync` without --no-dev, the uv binary copied into the final image, runs as
   root, no HEALTHCHECK. .python-version and Dockerfile say 3.11, ruff target-version says
   py312. config.py uses the pydantic v1 `class Config`. pytest / httpx live in
   [project.optional-dependencies].dev, so `uv sync` does not install them.

## What to do

- CVRP alignment: build the ordered node list as [depot] + clients in exactly the order used
  for m.locations, compute distances on that order, track inaccessible clients by position.
  Regression test on a 5-node synthetic graph asserting model distance(i, j) ==
  g.distances(node_i, node_j) for all pairs, plus a seeded solve for determinism. Then the
  matrix constructor instead of add_edge, drop the redundant distances() calls, move
  graph.copy() inside the thread, reuse sampling/igraph_utils (import, do not modify).
- Tests: backend/tests/ with pytest, a conftest that builds a 20-node synthetic MultiDiGraph
  (length, speed_kph, travel_time, geometry) and a TestClient on the app with that graph
  injected. Add an app.state / dependency provider in main.py and cvrp.py so services can be
  swapped; for routes.py do NOT edit it: inject by setting the module-level `graph_service`
  attribute from the fixture (monkeypatch), the other session keeps that name. Cover /health,
  /cvrp/centroids validation, the alignment regression, CO2Calculator (read-only use),
  models/cvrp validation. Move the old __main__ scripts to backend/scripts/ using
  $BACKEND_PORT, or delete test_api.py (it tests a removed field). Move pytest / httpx to
  [dependency-groups].dev so `uv sync` installs them; commit uv.lock (you land before the
  routing session, which re-locks after you).
- Makefile: lint / format / test -> ruff check --no-fix, ruff format --check, pytest. Do not
  edit .github/** (the frontend tooling session owns the whole workflow file and already
  puts ruff + pytest in the backend job).
- API hygiene in your files: cors_origins Settings field (list, default the local dev
  origins), waste_type as Literal of WASTE_TYPES, one app-level exception handler in main.py
  that logs the traceback and returns a generic 500, optional X-API-Key dependency controlled
  by a setting (empty = disabled), pydantic v2 model_config in config.py, logging
  dictConfig in main.py (uvicorn-friendly). Keep `await graph_service.initialize_default_routes(...)`
  in main.py as is.
- Container: backend/.dockerignore (.venv, *.ipynb, __pycache__, cvrp_refactored.py, tests),
  `uv sync --frozen --no-dev`, no uv binary in the final stage, non-root user, HEALTHCHECK on
  /health, one Python version everywhere (3.12 unless something breaks).
- Delete cvrp_refactored.py.

## You own

backend/app/services/cvrp_service.py, api/v1/cvrp.py, models/cvrp.py, main.py, config.py,
backend/tests/** (new), backend/scripts/** (new), backend/Makefile, backend/Dockerfile,
backend/.dockerignore, backend/pyproject.toml + uv.lock (dev group), .python-version,
cvrp_refactored.py (delete), the old test_*.py scripts.

## Do not touch

services/graph_service.py, routing_engine.py, bpr.py, graph_helpers.py, impact_calculator.py,
co2_calculator.py, sampling/**, models/route.py, api/v1/routes.py, .github/**, frontend/**.
Do not reformat files you did not change (ruff format only on your files).

## Acceptance

- `uv run pytest` green in < 60 s without lausanne.graphml; the alignment regression fails
  on the old code and passes on the new.
- POST /api/v1/cvrp/solve on the real data (http://127.0.0.1:$BACKEND_PORT): total_distance_m
  within 1 % of the sum of the rendered segments; solve time before/after in the PR.
- `grep -rn cvrp_refactored backend` empty; `uv run ruff check --no-fix app` and
  `uv run ruff format --check app` clean on your files.
- `docker build backend/` works, `docker run --rm <img> id -u` != 0, image smaller than
  before (both sizes in the PR); a forced 500 returns JSON without a traceback.

Small conventional commits (fix:/test:/ci:/build:). Push the branch (never dev). Finish with
http://127.0.0.1:$BACKEND_PORT/docs and the before/after numbers.
