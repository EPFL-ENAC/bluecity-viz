You are in a git worktree (branch perf/state-persistence). Read CLAUDE.md first: ports are in
.env.worktree, the tmux panes already run both servers, never push dev or main. Five other
sessions work in parallel on other files; the "You own / do not touch" lists below matter.

## Goal

Remove the main-thread work that runs on EVERY store change while the traffic tool is open.
Measured on dev: each click (layer toggle, edge click, mode switch) triggers a 136 ms
JSON.stringify of `projects` and a 2.7 MB localStorage write that throws QuotaExceeded
(swallowed). This is the main reason buttons feel slow.

## Verified causes (file:line on dev 100b7c2)

1. frontend/src/stores/layers/index.ts:99-111 getTrafficAnalysisState() does
   JSON.parse(JSON.stringify()) of nodePairs, originalEdgeUsage and newEdgeUsage (10,854 rows
   each). stores/layers/investigationManagement.ts:160 writes the result into
   `investigation.trafficAnalysis` from updateCurrentInvestigation(), which is called from 8
   places in stores/layers/*.ts (every layer toggle, source toggle, addSources, ...). So the
   clone runs on plain layer toggles too, not only on traffic changes.
2. index.ts:230-246 the traffic watcher getter returns a new object literal, so Vue sees a
   change on every re-evaluation, then calls updateCurrentInvestigation() and
   setTimeout(persistState, 100).
3. index.ts:209-226 a deep:true watcher over `projects` (which then holds ~22,000 objects)
   and 6 other refs, again with setTimeout(persistState, 100). That is a delay, not a
   debounce: N mutations = N stringify + N writes.
4. `projects` is a deep ref<Project[]> (index.ts:45). index.ts:22 `layerGroups =
   ref(configLayerGroups)` makes the whole 1,434-line layer config deeply reactive too.
5. components/sidebar/InvestigationSection.vue:11 calls layersStore.initializeInvestigations()
   as a side effect of component setup.
6. stores/trafficAnalysis.ts:492 restoreState() reads state.newEdgeUsage.length unguarded.
   Another session owns that file; you must keep passing arrays (see contract).

## What to do

- Persist only the INPUTS of a traffic analysis in an investigation: edgeModifications (as an
  array), activeVisualization, useCongestionModel, congestionIterations, elasticDemand,
  filterBusRoutes, isOpen. Never persist originalEdgeUsage / newEdgeUsage / nodePairs /
  impactStatistics. After a reload, results are absent until the user clicks "Calculate
  routes" again; the modifications are restored and drawn. If you want to keep results in
  memory while switching investigations in the same session, keep them in a module-level
  `Map<investigationId, markRaw(results)>`, never inside the `projects` ref.
- Bump the schema version in stores/layers/persistence.ts and migrate old localStorage
  entries by dropping the bulk fields (do not crash on the old shape).
- Contract with the traffic store (another session owns stores/trafficAnalysis.ts): keep
  calling `trafficStore.restoreState(state)` with the same TrafficAnalysisState shape and
  ALWAYS pass arrays (`[]` when the bulk fields are absent). Do not rename anything in
  stores/layers/types.ts that other files import; add fields, do not remove.
- Replace both `setTimeout(persistState, 100)` with one real debounce (single timer handle,
  cleared and re-armed, about 300 ms trailing). Flush on `pagehide` / `visibilitychange`.
- The traffic watcher must watch an array of primitives, not an object literal.
- Drop `deep: true` on the persistence watcher; `projects` changes are replacements of small
  objects once the bulk data is gone. If a deep watch is still needed for project renames,
  keep it but on `projects` only and without the bulk data it stays cheap.
- `layerGroups`: `shallowRef` or `markRaw(configLayerGroups)`. `filteredCategories` must STAY
  a deep ref (LegendMap.vue and MapLibreMap.vue mutate it in place); keep filterOutCategories.
- Move initializeInvestigations() out of InvestigationSection.vue into views/HomeView.vue (one
  line in setup, after the stores are available). Only that one line in HomeView.vue.
- Add vitest tests in frontend/src/stores/__tests__/layers.spec.ts: migration drops the bulk
  fields; with vi.useFakeTimers() 10 rapid updateSelectedLayers calls persist once; a
  round-trip keeps edgeModifications / activeVisualization / isOpen.

## You own

frontend/src/stores/layers/** , frontend/src/stores/layers.ts (the 3-line shim, keep it),
frontend/src/components/sidebar/InvestigationSection.vue, frontend/src/views/HomeView.vue
(one line), frontend/src/stores/__tests__/layers.spec.ts (new).

## Do not touch

frontend/src/components/panels/VisualizationsPanel.vue, composables/**, stores/trafficAnalysis.ts,
stores/cvrp.ts, components/MapLibreMap.vue, components/LegendMap.vue, config/**, package.json,
vite/tsconfig, backend/**. If you need a change there, write it in the PR description.

## Acceptance (verify yourself)

Browser at http://localhost:$FRONTEND_PORT/ with the traffic tool open, after one
"Calculate routes":
- `Object.values(localStorage).reduce((s,v)=>s+v.length,0)` < 200 000, and no "Failed to
  save state" warning in the console.
- `performance.now()` around `layersStore.updateSelectedLayers([...])` with results loaded:
  < 2 ms. No long task > 50 ms on a layer toggle or an edge click (PerformanceObserver
  type 'longtask').
- Reload: modifications and layer selection are restored, results recomputed on demand.
- `npm run type-check`, `npm run lint`, `npx vitest run` green.

Commit in small conventional commits (perf:/fix:/refactor:). Push the branch (never dev).
Run `git merge origin/dev` when told another branch landed. Finish by printing the frontend
URL and a before/after table (localStorage size, ms per layer toggle).
