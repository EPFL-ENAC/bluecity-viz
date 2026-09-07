You are in a git worktree (branch feat/od-pairs-ui). Read CLAUDE.md first (ports in
.env.worktree, tmux panes, never push dev/main). You are alone on this branch, no other
session runs at the same time, so no file is off limits. Keep the public names other
files import (store members, composable exports) unless you update every caller.

Context: the six perf branches are landed. The backend (perf/backend-routing) now routes a
set of origin-destination (OD) pairs sampled once at startup. Every frequency, delta,
CO2 and betweenness value comes from that set. The pair count is a per-request choice
and the sets are nested (the N-pair set is the first N of the full set), so results at
two sizes are consistent, the bigger one just has more trips.

What the backend offers today (read backend/app/api/v1/routes.py and
backend/app/models/route.py, do not change them):
- POST /api/v1/routes/recalculate takes `od_pairs: int | null` (null = server default,
  above the max = 422 with the max in the message) and `include_baseline: bool` (default
  true, sends `original_edge_usage`; false skips it). The response has `od_pairs`, the
  count really used. `congestion_iterations` is capped at 3.
- GET /api/v1/routes/baseline?od_pairs=N returns the free-flow usage for N pairs with an
  ETag and Cache-Control: no-cache, and answers 304 on If-None-Match. The browser does the
  conditional request by itself when fetch() is used normally.
- GET /api/v1/routes/graph-info reports `od_pairs` (sampled), `od_pairs_default` (20,000)
  and `od_pairs_max` (76,400).

Measured by that session, one removed edge: congestion 3 iterations 0.60 s at 20,000
pairs, 2.50 s at 76,400. Compared with the full set, 20,000 pairs gives a 0.96
correlation of edge frequency and 85 of the 100 busiest edges in common; about 760 small
streets show no traffic instead of a low value.

The frontend still sends the old request (services/trafficAnalysis.ts:103-125): no
`od_pairs`, baseline included in every response (half the payload), and the dock has no
way to pick the count.

What to do:
1. Service (services/trafficAnalysis.ts): add `fetchBaseline(odPairs?: number)` for GET
   /baseline and `fetchGraphInfo()`. `recalculateRoutes` takes `odPairs` in its options,
   sends `od_pairs` and `include_baseline: false`, and its return type makes
   `original_edge_usage` optional. Keep `resample_destinations`, it is still a field.
2. Store (stores/trafficAnalysis.ts): `odPairs: number | null` (null = server default)
   as an analysis INPUT next to useCongestionModel / congestionIterations / elasticDemand;
   `odPairsDefault` and `odPairsMax` filled once from /graph-info when the tool opens;
   a baseline cache `Map<number, EdgeUsageStats[]>` keyed by the count really used;
   `resultOdPairs` stored with the results. `setEdgeUsage` keeps its signature: the dock
   fetches the baseline (from the cache or GET /baseline) and passes it as `original`.
   When `odPairs` changes while results exist, clear the results (clearResults) so two
   sizes are never compared on screen. Keep the names LegendMap reads (isOpen,
   activeVisualization, colorScale, minValue, maxValue, getColor) and the ones the layers
   store restores.
3. Dock (components/dock/TrafficDock.vue): a "Trips" control with two options, built
   from components/ui (BcSeg): "20,000 (default)" and "76,400 (full)", numbers from
   graph-info, not hard-coded. Under "full", a short warning in .bc-micro style, plain
   words: about 4x slower, and compared with the default 85 of the 100 busiest roads are
   the same (frequency correlation 0.96). The iterations slider is already capped at 3.
   Show the count used next to the results (resultOdPairs).
4. Persistence (stores/layers/types.ts, persistence.ts, trafficResultsCache.ts,
   investigationManagement.ts): `odPairs` is an input of the traffic analysis, persist it
   with the other inputs, bump the schema version, migrate old entries (missing = null).
   Results are not persisted (that was the perf/state-persistence decision), so a restore
   shows the modifications and the chosen count, and the user clicks Calculate again.
5. Tests: the service builds the right request body and query; the store clears results
   when the count changes and caches one baseline per count; the migration keeps old
   investigations loading.

Do not touch: config/**, the MapLibre side of LegendMap.vue, backend/**.

Acceptance (browser at http://localhost:$FRONTEND_PORT/, Network tab open):
- Calculate at the default: one GET /baseline?od_pairs=20000 the first time, then a 304
  on reload, and the POST /recalculate answer is under 1 MB (baseline not included).
- Switch to full: the warning shows, the previous result disappears, Calculate fetches
  /baseline?od_pairs=76400 once and the results say 76,400.
- Reload restores the modifications and the chosen count, with no results.
- pnpm run type-check, type-check:test, lint:check, test:unit green.

Small conventional commits (feat:/refactor:/test:). Push the branch. Finish with the
frontend URL and the payload sizes before and after.
