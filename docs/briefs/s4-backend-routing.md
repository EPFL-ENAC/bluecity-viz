You are in a git worktree (branch perf/backend-routing). Read CLAUDE.md first: ports are in
.env.worktree, the backend pane runs uvicorn --reload, never push dev or main. Another
session (fix/backend-cvrp-quality) edits cvrp_service.py, api/v1/cvrp.py, models/cvrp.py,
main.py, the Dockerfile, the Makefile and backend/tests at the same time. Do not edit those.

## Goal

Make POST /api/v1/routes/recalculate fast and non-blocking, and shrink its payload. Measured
on dev with this graph (4,771 nodes, 10,854 edges): 1.7 s to 2.1 s wall for one removed edge,
2.9 MB JSON; 11 s with use_congestion and 3 iterations; while it runs every other request
(including /health and /docs) waits.

## Verified causes (file:line on dev 100b7c2)

1. app/api/v1/routes.py: every handler is `async def` and calls services that are `async def`
   but never await anything that suspends. CPU work runs on the event loop. One uvicorn
   worker. GraphService uses an asyncio.Lock (graph_service.py:76, used at :360).
   cvrp_service.py:617 copies the graph outside that lock, before its own to_thread.
2. services/sampling/igraph_utils.py:19-28, routing_engine.py:72-77, bpr.py:58 and :209,
   graph_service.py:423: ig.Graph.from_networkx is rebuilt on every routing call and again
   for betweenness, copying all edge attributes (shapely geometry, names, ...). The log shows
   graph_convert about 260-270 ms, twice per request, for about 50 ms of Dijkstra. It also
   writes nx_edge_id on every edge of the shared graph. Parallel edges collapse in
   edge_ig_to_nx (dict keyed by (u, v)).
3. main.py:36 passes count=500 but services/sampling/od_sampler.py:208-212 only validates
   n_pairs; the real size is SamplingConfig n_origins (500) x n_destinations_per_origin (200),
   and sample_od_pairs reuses n_samples for both origins and destinations. Log:
   "[ROUTING] 76400 pairs". Nobody chose 76,400. Changing it changes every frequency / BC /
   CO2 value users see, so it is a product decision: make it a Settings field, report the
   distribution comparison, do not silently change the default.
4. bpr.run_congestion_routing (bpr.py:191-228) re-routes all pairs 1 + n_iterations times;
   apply_congestion_weights scans all edges twice in Python; copy_weight_to_igraph does a
   networkx dict lookup per edge per iteration.
5. graph_service.py:505-508 rebuilds and resends original_edge_usage (6,406 rows, identical
   across requests) every time. No ETag / Cache-Control anywhere. Floats are unrounded.
6. routes.py:187-226 /edge-geometries json.dumps the 4.8 MB payload once to log its size,
   then FastAPI serializes it again; /graph builds 10,854 pydantic models and response_model
   validates them again. Neither is used by the frontend (it loads /geodata/lausanne.geojson).
   /habitat-geojson IS used and rescans all edges per request.
7. Caches: clear_route_cache does not clear _route_edge_index (graph_service.py:574-576);
   route_cache is unbounded; restore_edge_modifications recomputes _edge_co2_cache from
   free-flow co2_g so after one speed modification those edges permanently lose their
   congested CO2 value (graph_helpers.py:298-310 vs bpr.py:101-129).
8. graph_service.py:451-458 pops duration_bc from every edge in a finally block: a symptom of
   routing weights being written into the shared networkx graph.

## What to do, in this order, measuring with curl after each step (numbers in the commit messages)

a. Non-blocking: heavy handlers become plain `def` (FastAPI threadpool) or wrap the sync work
   in anyio.to_thread.run_sync; replace asyncio.Lock with a threading.RLock exposed as
   `GraphService.lock`; remove the fake async chain in services. Keep
   `initialize_default_routes` callable with `await` from main.py (thin async wrapper), since
   main.py belongs to the other session. Verify /health answers in < 20 ms while a
   congestion recalculate runs.
b. Persistent igraph mirror: build the igraph topology once at startup (no attribute copy),
   keep an edge index (igraph edge id <-> (u, v, key)), and per request only assign a weight
   vector. Edge removal = weight +inf (or 1e12), no rebuild. Congested weights go to the
   mirror, never to the networkx graph. Delete the duration_bc cleanup loop and the nx_edge_id
   writes. Handle parallel edges by igraph edge id. Keep the function signatures that
   cvrp_service.py calls (apply_edge_modifications(graph, {}, {}, mods) and
   sampling/igraph_utils.networkx_to_igraph_with_indices) working.
c. Make n_pairs real in od_sampler / SamplingConfig (n_origins = ceil(n_pairs /
   n_destinations_per_origin), no double use of n_samples), add an OD_PAIRS setting whose
   default reproduces today's 76,400, log the real number, expose it in /graph-info. Then run
   the comparison (76,400 vs 20,000 vs 10,000: correlation of per-edge frequency, top-100
   edges overlap) and put the table in the PR so the domain owner can pick.
d. Baseline: compute baseline edge usage once at startup; GET /api/v1/routes/baseline with
   ETag + Cache-Control and 304 on If-None-Match; add `include_baseline: bool = True` to
   RecalculateRequest (default True keeps the current frontend working), skip building
   original_edge_usage when False. Round frequency to 6 decimals, co2 / bc to 2, coordinates
   to 6. While in models/route.py, also make `action` a Literal["remove", "modify"], require
   speed_kph when action is modify, and add max_length to the modification list (the other
   backend session will not touch models/route.py).
e. Serialization: add orjson (pyproject + `uv lock`; the other session lands first and also
   touches uv.lock, so re-run `uv lock` after `git merge origin/dev`), ORJSONResponse for the
   bulk endpoints, no response_model on them. Cache /habitat-geojson and /edge-geometries
   payloads at startup with ETag. Remove the double json.dumps and the print() calls in hot
   paths. Mark /graph and /edge-geometries deprecated in their docstrings.
f. Congestion: vectorized weight updates on the mirror; MSA averaging so 2 iterations
   converge; cap congestion_iterations at 3 in the model.
g. Cache bugs: clear _route_edge_index in clear_route_cache, bound route_cache (small LRU),
   snapshot _edge_co2_cache values on modify / restore instead of recomputing.
h. Logging: demote per-request [TIMING] / [ROUTING] lines to DEBUG and add a Server-Timing
   header on /recalculate with the phase timings. Leave logging setup in main.py alone.
i. After the CVRP session has landed (you will be told), wrap the graph copy in
   cvrp_service.solve with `with self._graph_service.lock:` (3 lines, coordinate in the PR).

## You own

backend/app/api/v1/routes.py, services/graph_service.py, routing_engine.py, bpr.py,
graph_helpers.py, impact_calculator.py, co2_calculator.py, services/sampling/**,
models/route.py, RESEARCH_SAMPLING.md, pyproject.toml + uv.lock (orjson only, after merging
origin/dev).

## Do not touch

services/cvrp_service.py (except step i), api/v1/cvrp.py, models/cvrp.py, main.py,
Dockerfile, Makefile, .github/**, backend/tests/** (the other session creates them; add your
own tests under backend/tests/test_routing_*.py only after merging origin/dev), frontend/**.
Keep ruff clean on the files you touch: `uv run ruff check --no-fix app`. Do not reformat
files you did not change.

## Acceptance (curl against http://127.0.0.1:$BACKEND_PORT, results in the PR description)

- POST /recalculate with one removed edge, no congestion: < 700 ms wall; < 1.3 MB with
  include_baseline=false, < 2 MB with the default.
- use_congestion with 3 iterations: < 4 s at the current OD count.
- GET /health < 20 ms while a recalculate is in flight (two curls in parallel).
- GET /baseline returns an ETag; repeat with If-None-Match gives 304.
- 5 concurrent /recalculate with different modifications, then one with none:
  impact_statistics.affected_routes == 0 (no graph corruption).
- Second identical recalculate does not grow memory (route_cache bounded).
- `uv run python test_with_data.py` still passes; ruff clean on touched files.

Commit in small conventional commits (perf:/fix:). Push the branch (never dev). Run
`git merge origin/dev` when told another branch landed. Finish with
http://127.0.0.1:$BACKEND_PORT/docs and a before/after table.
