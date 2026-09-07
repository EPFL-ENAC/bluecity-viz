You are in a git worktree (branch perf/deck-rendering). Read CLAUDE.md first: ports are in
.env.worktree, the tmux panes already run both servers, never push dev or main. Five other
sessions work in parallel on other files; the "You own / do not touch" lists below matter.

## Goal

Make hovering and redrawing the road network cheap, stop loading the 6 MB GeoJSON when no
tool is open, and simplify the traffic store. Measured on dev: 60 pointermove events cost
1.7 s (28 ms each) on the main thread; every "Calculate routes" and every edge click rebuilds
all deck.gl layers from scratch; opening the traffic tool is a 240 ms long task.

## Verified causes (file:line on dev 100b7c2)

1. composables/useDeckGLTrafficAnalysis.ts:246-255 the base GeoJsonLayer (10,854 features)
   is pickable + autoHighlight; :588-633 handleHover writes a new reactive tooltipData object
   on EVERY move (info.x / info.y change constantly), so EdgeTooltip.vue re-renders at pointer
   rate. components/DeckGLOverlay.vue:25 uses interleaved: true, so each deck redraw also
   repaints MapLibre.
2. :507-538 getColor does a 7-way branch + trafficStore.getColor(value) per feature: a d3
   scale, a CSS string, then d3 rgb() parses it back, all through a Pinia proxy. No
   updateTriggers anywhere. visualizeEdgeUsage re-spreads and re-sorts 10,854 objects each time.
3. :297-341 updateModifiedEdges recomputes hull paths for all modified edges on every click,
   createHullPaths runs twice per edge, and 4 layers (2 TextLayers) are recreated.
4. :575-577 handleClick does edgeGeometries.value.find(...) O(n) for the reverse edge while
   edgeMap (:191) already has it.
5. :204 the baseLayer instance is cached and re-passed across renders. deck layers are
   immutable descriptors: keep the props and build `new GeoJsonLayer(props)` per render, the
   stable id makes deck reuse the GPU buffers. :217-243 also holds three copies of the
   geometry (edgeGeometries, edgeMap, a GeoJSON FeatureCollection); a PathLayer over
   EdgeGeometry[] with getPath: d => d.coordinates removes one.
6. components/panels/VisualizationsPanel.vue:158 calls deckGLTraffic.loadGraphEdges() on
   mount, unconditionally, so the 6 MB lausanne.geojson is fetched on every page load even
   with no tool open. The isOpen watchers (:77-100) already load it on demand.
7. composables/useDeckGLCVRP.ts:458-557 `layers` is a computed that reads hoveredRouteId and
   its onHover writes hoveredRouteId, so every hover rebuilds ALL CVRP layers including new
   centroidData / heatmapData arrays (deck re-uploads everything). stores/cvrp.ts:43-44
   lastResult and centroids are deep refs; deck reads path_coordinates through Proxies.
8. stores/trafficAnalysis.ts:80-107 has 21 parallel refs for per-mode color scales;
   updateActiveColorScale (:413-455) and clearResults (:373-404) are long if/else chains;
   setEdgeUsage (:255-371) does about 10 passes with Math.max(...spread). None of the 21 refs
   is exported (the store returns legendMode, colorScale, minValue, maxValue, getColor), so
   the refactor is invisible to consumers.
9. services/trafficAnalysis.ts fetchEdgeGeometries has 6 console.time calls and builds an
   intermediate array that the composable converts again.

## What to do

- VisualizationsPanel.vue: move the deck.gl part (composables, combinedLayers, the deck
  watchers at :77-156, the DeckGLOverlay + tooltips in the template) into a new child
  component, e.g. components/panels/DeckAnalysisLayer.vue, mounted with
  defineAsyncComponent and only rendered when `trafficStore.isOpen || cvrpStore.isOpen`.
  That is the real lazy-load of the deck.gl stack (another session adds manualChunks in
  vite.config.ts, do not edit it). Remove the unconditional loadGraphEdges on mount. Keep the
  MapLibreMap usage, the `:callback-loaded` prop and the `useMapLogic()` call exactly as they
  are (another session owns useMapLogic.ts and MapLibreMap.vue).
- Hover: throttle to one handling per animation frame; keep x/y out of reactive state and
  position the tooltip with a direct style transform; update reactive tooltip content only
  when the hovered edge key changes. Remove autoHighlight from the 10,854-feature base layer
  (a small highlight layer for the one hovered edge if the effect is wanted). Try
  interleaved: false, keep it only if it measurably helps and the stacking is acceptable.
- Colors: precompute per (mode, scale) a Uint8Array and pass a binary attribute
  (getColor: { value, size: 3 }), or at minimum hoist the field selector and the scale out of
  the accessor, memoize rgb() per scale output, and add updateTriggers keyed on
  [activeVisualization, scaleVersion]. Stable layer ids. Do not create a new `data` array
  when only the mode changes.
- Reverse edge via edgeMap. Memoize hull paths per edge key, compute once for hull and caps.
  Keep the modified-edge layers stable with updateTriggers.
- Move pure geometry (getPathMidpoint, computeOffsetPath, createHullPaths) to
  frontend/src/utils/geometry.ts with unit tests.
- Split useDeckGLTrafficAnalysis into useGraphEdges (fetch + edgeMap, no console noise),
  buildTrafficLayers (pure data -> layers[]) and useEdgeTooltip. Keep exporting the
  EdgeTooltipData / CVRPTooltipData types (the tooltip components import them).
- CVRP: hoist centroidData / routeStats / heatmapData into computeds that do not read
  hoveredRouteId; only getColor / getWidth + updateTriggers react to hover. lastResult and
  centroids become shallowRef + markRaw (consumers only read them and setResult replaces
  them wholesale). Same for impactStatistics in the traffic store.
- Traffic store: replace the 21 refs by `scales: Record<VisualizationMode, { scale, min, max }>`,
  single-pass min/max/flags in setEdgeUsage, getColor from a memoized lookup. Keep EVERY
  exported name and its type unchanged (another session's LegendMap.vue uses isOpen,
  activeVisualization, colorScale, minValue, maxValue, getColor; the layers store calls
  restoreState(state) and reads originalEdgeUsage / newEdgeUsage / nodePairs /
  impactStatistics / edgeModifications / isOpen / activeVisualization / openPanel; TrafficDock
  uses 16 members). Harden restoreState with `?? []` on the bulk arrays (the layers-store
  session will stop persisting them). Add stores/__tests__/trafficAnalysis.spec.ts: the
  single-pass setEdgeUsage gives the same min/max per mode as a fixture recorded from the
  current code, and `Object.keys(store)` is unchanged.
- Optional, only if time remains: in services/trafficAnalysis.ts + TrafficDock.vue, send
  `include_baseline: false` on /recalculate and, when the response has an empty
  original_edge_usage, fetch it once from GET /api/v1/routes/baseline (memoized promise).
  Works with both the old backend (ignores the field, returns the baseline) and the new one.

## You own

frontend/src/composables/useDeckGLTrafficAnalysis.ts, composables/useDeckGLCVRP.ts,
components/DeckGLOverlay.vue, components/EdgeTooltip.vue, components/CVRPTooltip.vue,
components/panels/VisualizationsPanel.vue (+ the new child component),
stores/trafficAnalysis.ts, stores/cvrp.ts, components/dock/TrafficDock.vue,
components/dock/CvrpDock.vue, components/ImpactStatistics.vue, services/trafficAnalysis.ts,
utils/geometry.ts (new), stores/__tests__/trafficAnalysis.spec.ts (new).

## Do not touch

stores/layers/**, components/MapLibreMap.vue, components/LegendMap.vue, composables/useMapLogic.ts,
composables/useMapEvents.ts, config/**, package.json, vite/tsconfig, backend/**. If the build
breaks because @deck.gl/extensions is not declared (it is imported at line 3 but only resolves
through the unused `deck.gl` meta package, which another session removes), add it to
package.json at the same version as the other @deck.gl packages, nothing else.

## Acceptance (verify yourself)

Browser console at http://localhost:$FRONTEND_PORT/, traffic tool open, one calculation done:
- Dispatching 60 synthetic pointermove events on the map canvas takes < 200 ms total, and a
  Performance recording of a cursor sweep shows no long task.
- setActiveVisualization('co2') then ('delta'): < 50 ms each, and the PathLayer `props.data`
  identity is unchanged (updateTriggers only).
- CVRP: hovering a route keeps the centroid and heatmap layers' `props.data` identical.
- Fresh page load with no tool open: no request for lausanne.geojson in the Network tab.
- `npm run type-check`, `npm run lint`, `npx vitest run` green.

Commit in small conventional commits (perf:/refactor:). Push the branch (never dev). Run
`git merge origin/dev` when told another branch landed. Finish with the frontend URL and a
before/after table (ms per hover event, ms per mode switch, startup requests).
