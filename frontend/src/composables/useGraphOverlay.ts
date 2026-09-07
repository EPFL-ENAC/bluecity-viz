import type { FeatureCollection } from 'geojson'
import { valueOf } from '@/composables/useResultStates'
import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { streetKey, useScenarioStore, type ScenarioDir } from '@/stores/scenario'
import { useThemeStore } from '@/stores/theme'
import { useCVRPStore } from '@/stores/cvrp'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  addGraphImages,
  applyCvrp,
  applyCvrpHover,
  applyModifications,
  BADGE_SOURCE,
  CVRP_POINT_SOURCE,
  CVRP_SOURCE,
  BEFORE_LAYER,
  buildGraphLayers,
  drawFor,
  emptyBadges,
  emptyPoints,
  GRAPH_SOURCE,
  graphLayerIds,
  idFilter
} from '@/utils/bluecityGraph'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { pointFeatures, routeFeatures } from '@/utils/cvrpSource'
import { buildGraphSource, pickLane, type GraphSource } from '@/utils/graphSource'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { computed, watch, type Ref } from 'vue'

/** The layers the pointer can hit. */
const PICK_LAYERS = ['bc-graph-one', 'bc-graph-two', 'bc-lanes']

/** What the map knows about the vehicle route under the cursor. */
export interface RouteHover {
  route_id: number
  trip_id: number
  load_kg: number
  color: string
}

export interface EdgeHover {
  key: string
  dir: ScenarioDir
  edge: EdgeGeometry
  name: string
  speed?: number
  highway?: string
  oneway: boolean
}

/**
 * The street graph on the map.
 *
 * Everything the overlay draws lives in one GeoJSON source of directed edges.
 * Hover, selection and result colours are feature state, so pointing at a
 * street costs two setFeatureState calls, not a new source.
 */
export function useGraphOverlay(
  mapRef: Ref<MapLibreMap | undefined>,
  graph: Ref<GraphSource | null>,
  callbacks: {
    onHover?: (hover: EdgeHover | null, point: { x: number; y: number }) => void
    onPick?: (key: string, dir: ScenarioDir, point: { x: number; y: number }) => void
    onRoute?: (route: RouteHover | null, point: { x: number; y: number }) => void
  } = {}
) {
  const scenarioStore = useScenarioStore()
  const themeStore = useThemeStore()
  const trafficStore = useTrafficAnalysisStore()
  const cvrpStore = useCVRPStore()

  const colors = computed(() => (themeStore.isDark ? GRAPH_COLORS.dark : GRAPH_COLORS.light))

  // The ids we last wrote a state on, so we can clear exactly those.
  let hoverIds: number[] = []
  let selectedIds: number[] = []
  let ghostIds: number[] = []
  // the streets currently carrying a result colour
  let resultIds: number[] = []
  // Which map instance carries our layers, so a new map remounts instead of
  // writing feature state into a style that no longer holds the source.
  let mountedOn: MapLibreMap | null = null
  // the map we already queued a retry for, so we register the listeners once
  let waiting: MapLibreMap | null = null

  function idsFor(key: string, dir: ScenarioDir): number[] {
    const street = graph.value?.streets.get(key)
    if (!street) return []
    const ids: number[] = []
    if (dir !== 'bwd' && street.fwdId !== undefined) ids.push(street.fwdId)
    if (dir !== 'fwd' && street.bwdId !== undefined) ids.push(street.bwdId)
    return ids
  }

  function setState(map: MapLibreMap, ids: number[], state: Record<string, number>): void {
    for (const id of ids) {
      map.setFeatureState({ source: GRAPH_SOURCE, id }, state)
    }
  }

  /**
   * Put the source, the images and the layers on the map.
   *
   * The network and the style arrive in either order, so this is called from
   * both sides and simply waits when the style is not ready yet.
   */
  function mount(): void {
    const map = mapRef.value
    const source = graph.value
    if (!map || !source) return

    // MapLibre refuses addSource / addLayer until the style JSON is parsed, and
    // it has no public "is the style parsed" flag: isStyleLoaded() also waits
    // for every source, which the basemap tiles keep false for a long time.
    // So try, and retry on the next event if the style was not ready.
    try {
      addGraphImages(map, colors.value)

      if (!map.getSource(GRAPH_SOURCE)) {
        map.addSource(GRAPH_SOURCE, {
          type: 'geojson',
          data: source.collection as unknown as FeatureCollection
        })
      }
      if (!map.getSource(BADGE_SOURCE)) {
        map.addSource(BADGE_SOURCE, {
          type: 'geojson',
          data: emptyBadges() as unknown as FeatureCollection
        })
      }
      for (const id of [CVRP_SOURCE, CVRP_POINT_SOURCE]) {
        if (!map.getSource(id)) {
          map.addSource(id, {
            type: 'geojson',
            data: emptyPoints() as unknown as FeatureCollection
          })
        }
      }

      // Under the street names, so the basemap labels stay readable.
      const before = map.getLayer(BEFORE_LAYER) ? BEFORE_LAYER : undefined
      for (const layer of buildGraphLayers({ colors: colors.value, mode: scenarioStore.mapMode })) {
        if (map.getLayer(layer.id)) map.removeLayer(layer.id)
        map.addLayer(layer, before)
      }
    } catch {
      // mount() is idempotent, a half-added overlay is fixed by the retry.
      retryLater(map)
      return
    }

    mountedOn = map
    redraw()
    applyResult()
    applyRoutes()
  }

  /** Wait for the style to move on, then mount again. */
  function retryLater(map: MapLibreMap): void {
    if (waiting === map) return
    waiting = map

    const again = () => {
      map.off('style.load', again)
      map.off('load', again)
      map.off('sourcedata', again)
      map.off('idle', again)
      waiting = null
      mount()
    }

    map.on('style.load', again)
    map.on('load', again)
    map.on('sourcedata', again)
    map.on('idle', again)
  }

  /** Drop the layers, e.g. before a style swap re-adds them. */
  function unmount(): void {
    const map = mapRef.value
    if (!map) return
    for (const id of graphLayerIds()) {
      if (map.getLayer(id)) map.removeLayer(id)
    }
    mountedOn = null
  }

  function redraw(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map || !graph.value) return
    const draw = drawFor(scenarioStore.edgeModifications, graph.value.streets)

    // the stroke of a one-direction modification rides its own lane
    const lane = new Set(draw.laneIds)
    for (const id of draw.strokeIds) {
      map.setFeatureState({ source: GRAPH_SOURCE, id }, { ml: lane.has(id) ? 1 : 0 })
    }

    applyModifications(map, draw, scenarioStore.mapMode)
  }

  /**
   * Paint the routing result on the graph.
   *
   * One colour per street, on the centreline, both directions summed. The
   * colour rides feature-state, so a mode switch is one pass and the 6 MB
   * source is never touched.
   */
  function applyResult(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map || !graph.value) return

    for (const id of resultIds) {
      map.removeFeatureState({ source: GRAPH_SOURCE, id }, 'c')
    }
    resultIds = []

    const mode = trafficStore.activeVisualization
    const show =
      scenarioStore.mapMode === 'result' && mode !== 'none' && trafficStore.hasCalculatedRoutes

    if (!show) {
      setDataFilter(map, [])
      return
    }

    const onlyBus = trafficStore.filterBusRoutes
    for (const row of trafficStore.resultTotals) {
      if (onlyBus && !row.bus) continue
      const [r, g, b] = trafficStore.getColor(valueOf(row, mode))
      map.setFeatureState({ source: GRAPH_SOURCE, id: row.id }, { c: `rgb(${r},${g},${b})` })
      resultIds.push(row.id)
    }

    setDataFilter(map, resultIds)
    // A stale result answers an old question, so it is shown but faded.
    const opacity = trafficStore.isStale ? 0.4 : 1
    map.setPaintProperty('bc-data', 'line-opacity', opacity)
    map.setPaintProperty('bc-data-casing', 'line-opacity', opacity * 0.9)
  }

  /**
   * The waste collection routes, braided one lane per vehicle.
   *
   * Load mode colours the graph itself instead, so it goes through the same
   * feature-state channel as the routing result.
   */
  const EMPTY = { type: 'FeatureCollection' as const, features: [] }

  function applyRoutes(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    const result = cvrpStore.lastResult
    const show = scenarioStore.mapMode === 'result' && !!result && cvrpStore.isOpen

    const points = cvrpStore.showCentroids
      ? pointFeatures(cvrpStore.centroids, result?.n_missing_clients ?? 0)
      : []

    if (!show || !result) {
      applyCvrp(map, points.length ? { routes: EMPTY, points, mode: 'routes', stale: false } : null)
      return
    }

    if (cvrpStore.visualizationMode === 'heatmap') {
      applyCvrp(map, { routes: EMPTY, points, mode: 'routes', stale: false })
      applyLoads()
      return
    }

    applyCvrp(map, {
      routes: routeFeatures(result.route_segments, result.n_routes),
      points,
      mode: 'routes',
      stale: cvrpStore.isStale
    })
  }

  /** Edge load: viridis on the graph, through the same state as the result. */
  function applyLoads(): void {
    const map = mapRef.value
    const source = graph.value
    if (!map || mountedOn !== map || !source) return

    for (const id of resultIds) map.removeFeatureState({ source: GRAPH_SOURCE, id }, 'c')
    resultIds = []

    const loads = cvrpStore.lastResult?.edge_loads ?? []
    for (const load of loads) {
      const street = source.streets.get(streetKey(load.u, load.v))
      const id = street?.fwdId ?? street?.bwdId
      if (id === undefined) continue
      const [r, g, b] = cvrpStore.getEdgeLoadColor(load.load)
      map.setFeatureState({ source: GRAPH_SOURCE, id }, { c: `rgb(${r},${g},${b})` })
      resultIds.push(id)
    }

    setDataFilter(map, resultIds)
    const opacity = cvrpStore.isStale ? 0.4 : 1
    map.setPaintProperty('bc-data', 'line-opacity', opacity)
    map.setPaintProperty('bc-data-casing', 'line-opacity', opacity * 0.9)
  }

  /** Light one vehicle, dim the rest. */
  function hoverRoute(routeId: number | null): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return
    applyCvrpHover(map, routeId)
  }

  function setDataFilter(map: MapLibreMap, ids: number[]): void {
    const filter = idFilter(ids)
    if (map.getLayer('bc-data')) map.setFilter('bc-data', filter)
    if (map.getLayer('bc-data-casing')) map.setFilter('bc-data-casing', filter)
  }

  function applyHover(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    setState(map, hoverIds, { h: 0, hl: 0 })
    hoverIds = []

    const hovered = scenarioStore.hovered
    if (!hovered) {
      if (map.getLayer('bc-hover')) {
        map.setFilter('bc-hover', ['in', ['id'], ['literal', []]])
        map.setFilter('bc-hover-halo', ['in', ['id'], ['literal', []]])
      }
      return
    }

    hoverIds = idsFor(hovered.key, hovered.dir)
    // one lane hovered: offset onto it. Both: stay on the centre line.
    setState(map, hoverIds, { h: 1, hl: hovered.dir === 'both' ? 0 : 1 })

    if (map.getLayer('bc-hover')) {
      const filter = ['in', ['id'], ['literal', hoverIds]] as never
      map.setFilter('bc-hover', filter)
      map.setFilter('bc-hover-halo', filter)
    }
  }

  function applySelection(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    setState(map, selectedIds, { s: 0, sl: 0 })
    setState(map, ghostIds, { g: 0 })
    selectedIds = []
    ghostIds = []

    const selected = scenarioStore.selected
    const empty = ['in', ['id'], ['literal', []]] as never

    if (!selected) {
      if (map.getLayer('bc-selected')) {
        map.setFilter('bc-selected', empty)
        map.setFilter('bc-selected-ghost', empty)
      }
      return
    }

    selectedIds = idsFor(selected.key, selected.dir)
    setState(map, selectedIds, { s: 1, sl: selected.dir === 'both' ? 0 : 1 })

    // With one lane selected, the other shows a dotted ghost so the user sees
    // which direction is left out.
    if (selected.dir !== 'both') {
      const other = selected.dir === 'fwd' ? 'bwd' : 'fwd'
      ghostIds = idsFor(selected.key, other)
      setState(map, ghostIds, { g: 1 })
    }

    if (map.getLayer('bc-selected')) {
      map.setFilter('bc-selected', ['in', ['id'], ['literal', selectedIds]] as never)
      map.setFilter('bc-selected-ghost', ['in', ['id'], ['literal', ghostIds]] as never)
    }
  }

  /** Which street, and which lane, is under the cursor. */
  function hitAt(event: MapMouseEvent): EdgeHover | null {
    const map = mapRef.value
    const source = graph.value
    if (!map || !source) return null

    const box: [[number, number], [number, number]] = [
      [event.point.x - 4, event.point.y - 4],
      [event.point.x + 4, event.point.y + 4]
    ]
    const hits = map.queryRenderedFeatures(box, {
      layers: PICK_LAYERS.filter((l) => map.getLayer(l))
    })
    if (hits.length === 0) return null

    const hit = hits[0]
    const id = hit.id as number
    const edge = source.edgeById.get(id)
    if (!edge) return null

    const key = streetKey(edge.u, edge.v)
    const street = source.streets.get(key)
    const oneway = street?.oneway ?? true

    // A hit on the lane layer already tells us the direction. Below the split
    // zoom every edge draws on the centre line, so work it out from the side
    // the cursor falls on.
    let dir: ScenarioDir = 'both'
    if (!oneway) {
      dir =
        hit.layer.id === 'bc-lanes'
          ? edge.u <= edge.v
            ? 'fwd'
            : 'bwd'
          : pickLane(
              edge.coordinates,
              [event.point.x, event.point.y],
              (position) => {
                const projected = map.project(position)
                return [projected.x, projected.y]
              },
              edge.u <= edge.v
            )
    }

    return {
      key,
      dir,
      edge,
      name: street?.name || edge.name || `Edge ${edge.u}→${edge.v}`,
      speed: edge.speed_kph,
      highway: edge.highway,
      oneway
    }
  }

  let frame = 0
  function onMouseMove(event: MapMouseEvent): void {
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0

      // A vehicle route sits on top of the graph, so it takes the pointer.
      const route = routeAt(event)
      if (route) {
        hoverRoute(route.route_id)
        scenarioStore.hover(null)
        callbacks.onHover?.(null, { x: event.point.x, y: event.point.y })
        callbacks.onRoute?.(route, { x: event.point.x, y: event.point.y })
        const map = mapRef.value
        if (map) map.getCanvas().style.cursor = 'pointer'
        return
      }
      hoverRoute(null)
      callbacks.onRoute?.(null, { x: event.point.x, y: event.point.y })

      const hit = hitAt(event)
      // Hovering points at the street; the lane only matters once we click.
      scenarioStore.hover(hit ? { key: hit.key, dir: hit.oneway ? 'both' : hit.dir } : null)
      callbacks.onHover?.(hit, { x: event.point.x, y: event.point.y })

      const map = mapRef.value
      if (map) map.getCanvas().style.cursor = hit && scenarioStore.editMode ? 'pointer' : ''
    })
  }

  /** The vehicle route under the cursor, if any. */
  function routeAt(event: MapMouseEvent): RouteHover | null {
    const map = mapRef.value
    if (!map || !map.getLayer('bc-cvrp')) return null

    const box: [[number, number], [number, number]] = [
      [event.point.x - 4, event.point.y - 4],
      [event.point.x + 4, event.point.y + 4]
    ]
    const hits = map.queryRenderedFeatures(box, { layers: ['bc-cvrp'] })
    if (hits.length === 0) return null

    const props = hits[0].properties ?? {}
    return {
      route_id: Number(props.route_id),
      trip_id: Number(props.trip_id),
      load_kg: Number(props.load_kg),
      color: String(props.color)
    }
  }

  function onMouseOut(): void {
    scenarioStore.hover(null)
    hoverRoute(null)
    callbacks.onHover?.(null, { x: 0, y: 0 })
    callbacks.onRoute?.(null, { x: 0, y: 0 })
  }

  function onClick(event: MapMouseEvent): void {
    if (!scenarioStore.editMode) return
    const hit = hitAt(event)

    if (!hit) {
      // clicking empty map leaves edit mode
      scenarioStore.setEditMode(false)
      return
    }

    // Click takes both directions, which is what people mean most of the time.
    // Shift-click takes the single lane under the cursor.
    const shift = (event.originalEvent as MouseEvent).shiftKey
    const dir: ScenarioDir = hit.oneway || !shift ? 'both' : hit.dir

    scenarioStore.select({ key: hit.key, dir })
    callbacks.onPick?.(hit.key, dir, { x: event.point.x, y: event.point.y })
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && scenarioStore.editMode) scenarioStore.setEditMode(false)
  }

  function attach(map: MapLibreMap): void {
    // Shift-click picks one lane, so the shift-drag box zoom has to go: it eats
    // the mousedown and MapLibre never fires the click.
    map.boxZoom.disable()
    map.on('mousemove', onMouseMove)
    map.on('mouseout', onMouseOut)
    map.on('click', onClick)
    // style.load fires on every setStyle, which drops our layers with it
    map.on('style.load', mount)
    window.addEventListener('keydown', onKeyDown)
  }

  function detach(map: MapLibreMap): void {
    map.boxZoom.enable()
    map.off('mousemove', onMouseMove)
    map.off('mouseout', onMouseOut)
    map.off('click', onClick)
    map.off('style.load', mount)
    window.removeEventListener('keydown', onKeyDown)
  }

  // Mount as soon as both the map and the network are there, in either order.
  watch([mapRef, graph], () => mount(), { immediate: true })

  watch(() => scenarioStore.edgeModifications, redraw)
  watch(
    () => scenarioStore.mapMode,
    () => {
      unmount()
      mount()
    }
  )
  watch(
    () => [
      trafficStore.resultTotals,
      trafficStore.activeVisualization,
      trafficStore.filterBusRoutes,
      trafficStore.isStale
    ],
    applyResult
  )
  watch(
    () => [
      cvrpStore.lastResult,
      cvrpStore.visualizationMode,
      cvrpStore.isOpen,
      cvrpStore.isStale,
      cvrpStore.showCentroids,
      cvrpStore.centroids,
      scenarioStore.mapMode
    ],
    applyRoutes
  )
  watch(() => scenarioStore.hovered, applyHover)
  watch(() => scenarioStore.selected, applySelection)
  watch(colors, () => {
    unmount()
    mount()
  })

  return { mount, unmount, redraw, applyResult, applyRoutes, hoverRoute, attach, detach, hitAt }
}

/** Build the source once the network is loaded. */
export function graphSourceFrom(edges: EdgeGeometry[]): GraphSource | null {
  if (edges.length === 0) return null
  return buildGraphSource(edges)
}
