You are in a git worktree (branch perf/maplibre-layers). Read CLAUDE.md first: ports are in
.env.worktree, the tmux panes already run both servers, never push dev or main. Five other
sessions work in parallel on other files; the "You own / do not touch" lists below matter.

## Goal

Make the map load only what is selected, stop the background timers, make theme switches
cheap, and remove the casts and the three-place registry from the layer config without
changing a single rendered color. Measured on dev: 11 different .pmtiles files are fetched
at startup with one dataset active; the map area stays blank until an external fetch returns.

## Verified facts (file:line on dev 100b7c2)

1. components/MapLibreMap.vue:151-155 adds ALL 37 layers on load with one source per layer,
   keyed by the layer id instead of source.id, so layers that share a pmtiles file register
   duplicate sources. No layer spec sets layout.visibility 'none' (zero occurrences in
   config/), so MapLibre requests tiles for everything and syncAllLayersVisibility hides them
   afterwards.
2. :157-178 sourcedata / sourcedataloading handlers call areTilesLoaded() on every tile event
   and start independent, uncancellable setTimeout(..., 1000) chains.
3. :338-374 theme change does a full map.setStyle(), re-adds all 37 sources/layers and re-runs
   visibility for each. styleSpec / traitTheme computeds return new objects each evaluation.
   trait <-> trait-dark are the same engine (buildStyle('contour', theme)) so setPaintProperty
   can do it; trait <-> style/light.json is a different layer set and still needs setStyle,
   but only the visible layers need re-adding.
4. composables/useMapLogic.ts:41 deep-watches selectedLayers (string[]) and
   syncAllLayersVisibility calls setLayerVisibility for all 37 layers on every toggle, each
   doing mapConfig.layers.find(...) (MapLibreMap.vue:250). On first load there is nothing to
   diff against, so the lazy-source logic and the diff must live together (both are yours).
5. config/sp*.ts, correlation.ts, biodiversity.ts: identical preamble, 37 `as LayerSpecification`
   casts, 32 hand-written interpolate ramps. config/mapConfig.ts is a manual three-place
   registry (layers, sources, layerGroups) that can drift. The layers store
   (stores/layers/layerManagement.ts, sourceManagement.ts, index.ts, another session's files)
   depends on the exports mapConfig.layers, mapConfig.sources, layerGroups and on the shapes
   MapLayerConfig { id, label, info, unit, source: { id, label, attribution }, layer }, and
   layer ids / source ids are persisted in localStorage, investigations and share URLs.
6. components/LegendMap.vue:29-120 reverse-parses paint expressions to build legends; it
   throws if a layer has no color paint property, and treats 'case' as categorical without
   handling it. :129-303 is a 175-line 7-branch traffic legend computed that only needs
   mode -> { label, unit, formatter, showZero }.
7. utils/epflBasemap.ts:508 loadTiles() fetches https://tiles.openfreemap.org/planet before
   the map can be created; the map stays blank until it returns.
8. utils/jsonWebMap.ts `Parameters` is only used by an always-empty ref in useMapLogic.ts:16
   and the `parameters.popupLayerIds` prop that is therefore always undefined.
9. ADD_DATASET.md points at a LayerSelector.vue that does not exist and the wrong CDN path.

## What to do

- MapLibreMap.vue: add a source lazily on first activation (dedupe by source.id), add layers
  with layout.visibility 'none' unless selected, hide on deselect. One cancellable timer for
  the loading flag, or map.on('idle') / 'dataloading' with a debounce. Theme switch: for
  trait <-> trait-dark use setPaintProperty on the ink/paper colors; for the setStyle path
  use { diff: true }, guard re-entry, and re-add only the visible layers. Keep every exposed
  method and prop name (setLayerVisibility, the filter functions, the `map` ref,
  callbackLoaded) with the same signature: VisualizationsPanel.vue uses them and another
  session owns that file.
- useMapLogic.ts: drop the deep watch, diff old vs new selection (two Sets), touch only
  changed layers, build a Map<id, layer> once. Delete the empty `parameters` ref, inline or
  drop its type, delete utils/jsonWebMap.ts. Keep the export names (map, center, zoom,
  syncAllLayersVisibility, layersStore, parameters if VisualizationsPanel still reads it:
  check, and if so keep returning an empty object so the template line stays valid).
- Cache the openfreemap tile JSON (localStorage with a 24 h TTL) or create the map with a
  fallback style first so the map area paints immediately.
- Config, scaled down on purpose (no perf value, 37 specs and no tests protecting them):
  first record a vitest snapshot of JSON.stringify(mapConfig.layers), mapConfig.sources and
  layerGroups BEFORE any change. Then add a typed defineLayer() / defineSource() helper that
  removes the `as LayerSpecification` casts, derive mapConfig.layers / sources / layerGroups
  from one array (sources deduped by id), and add an optional `encoding` field
  ({ kind: 'sequential', property, domain, scheme } | { kind: 'categorical', property,
  categories }) that a buildPaint() helper turns into the interpolate / match expression.
  Migrate sp0_migration.ts first (it is active by default), then the others one file at a
  time. The snapshot must stay identical (same ids, same stops, same colors) or the diff must
  be explained in the commit. Keep every exported name and type in config/layerTypes.ts and
  config/mapConfig.ts.
- LegendMap.vue: read `encoding` when present, fall back to expression parsing otherwise; fix
  the null-paint crash and the 'case' branch; table-drive the traffic legend computed (it
  only reads isOpen, activeVisualization, colorScale, minValue, maxValue, getColor from the
  traffic store; those names stay stable). Snapshot the legend output for all 37 layers
  before/after.
- Rewrite ADD_DATASET.md for the real flow (one object in the registry, tippecanoe / S3
  parts are still accurate).

## You own

frontend/src/components/MapLibreMap.vue, composables/useMapLogic.ts, composables/useMapEvents.ts,
config/**, components/LegendMap.vue, utils/legendColor.ts, utils/epflBasemap.ts,
utils/jsonWebMap.ts (delete), ADD_DATASET.md, config/__tests__/* (new).

## Do not touch

composables/useDeckGL*.ts, components/panels/VisualizationsPanel.vue, stores/**,
components/dock/**, package.json, vite/tsconfig, backend/**. `filteredCategories` in the
layers store stays a deep ref that you mutate in place, as today.

## Acceptance (verify yourself)

- Fresh load with the default investigation, Network tab filtered on pmtiles: <= 2 requests
  (was 11); toggling a layer requests only its source. map.getStyle().layers.length equals
  basemap + visible dataset layers.
- After the map is idle, no timer fires every second (temporary console.count in the
  loading check must stop).
- trait <-> trait-dark switch: map.setStyle not called (spy on it), < 100 ms, selected
  layers stay visible.
- Snapshot tests: layer ids, source ids, stops and colors identical before/after;
  `grep -c "as LayerSpecification" src/config` is 0; legend output identical for all layers.
- `npm run type-check`, `npm run lint`, `npx vitest run` green.

Commit in small conventional commits (perf:/refactor:/docs:). Push the branch (never dev).
Run `git merge origin/dev` when told another branch landed. Finish with the frontend URL and
the before/after count of startup network requests.
