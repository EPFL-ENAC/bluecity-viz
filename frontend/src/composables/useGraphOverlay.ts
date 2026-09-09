import { useMapView } from '@/composables/useMapView'
import { valueOf } from '@/composables/useResultStates'
import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { streetKey, useScenarioStore, type ScenarioDir } from '@/stores/scenario'
import { useThemeStore } from '@/stores/theme'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  AREA_RING_LAYER,
  AREA_SOURCE,
  areaFeatures,
  areaRingLayer,
  emptyArea
} from '@/utils/areaCircle'
import {
  addGraphImages,
  applyCvrp,
  applyCvrpHover,
  applyModifications,
  BADGE_SOURCE,
  BEFORE_LAYER,
  buildGraphLayers,
  CVRP_POINT_SOURCE,
  CVRP_SOURCE,
  drawFor,
  emptyBadges,
  emptyPointer,
  emptyPoints,
  GRAPH_SOURCE,
  graphLayerIds,
  idFilter,
  POINTER_SOURCE,
  setData,
  setGraphEdges,
  setPointer,
  type CvrpRouteRef,
  type PointerFeature,
  type PointerRole
} from '@/utils/bluecityGraph'
import { pointFeatures, routeFeatures } from '@/utils/cvrpSource'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { buildGraphSource, pickLane, type GraphSource } from '@/utils/graphSource'
import type { FeatureCollection } from 'geojson'
import { LngLatBounds, type Map as MapLibreMap, type MapMouseEvent } from 'maplibre-gl'
import { computed, watch, type Ref } from 'vue'

/** The layers the pointer can hit. */
const PICK_LAYERS = ['bc-graph-one', 'bc-graph-two', 'bc-lanes']

/** The dock hides this much of the map on the right (--bc-dock-w). */
const DOCK_WIDTH = 340

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
  // One place says what the map draws: the lit zone of the dock.
  const { shown } = useMapView()

  /** Ink treatment of the modifications: they recede once colour is on. */
  const inkMode = computed<'scenario' | 'result'>(() => (shown.value ? 'result' : 'scenario'))

  const colors = computed(() => (themeStore.isDark ? GRAPH_COLORS.dark : GRAPH_COLORS.light))

  // The ids we last wrote a state on, so we can clear exactly those.
  let hoverIds: number[] = []
  let selectedIds: number[] = []
  let ghostIds: number[] = []
  // the streets currently carrying a result colour
  let resultIds: number[] = []
  // the route features on the map, and the vehicle the pointer is on
  let routeRefs: CvrpRouteRef[] = []
  let hoveredRoute: number | null = null
  // what the pointer source draws right now
  let hoverFeatures: PointerFeature[] = []
  let selectionFeatures: PointerFeature[] = []
  // Which map instance carries our layers, so a new map remounts instead of
  // writing feature state into a style that no longer holds the source.
  let mountedOn: MapLibreMap | null = null
  // Which network is on the map. addSource only runs once, so an area change
  // has to push the new features into the source that is already there.
  let mountedGraph: GraphSource | null = null
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

  /**
   * The edges under the pointer, copied onto the small pointer source.
   *
   * `lane` is 0 for a whole street, so the accent sits on the centre line, and
   * 1 for one direction, so it sits on that lane.
   */
  function pointerFeatures(ids: number[], role: PointerRole, lane: number): PointerFeature[] {
    const features = graph.value?.collection.features
    if (!features) return []
    const out: PointerFeature[] = []
    for (const id of ids) {
      const feature = features[id]
      if (!feature) continue
      out.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: feature.geometry.coordinates },
        properties: { role, side: Number(feature.properties.side) || 1, lane }
      })
    }
    return out
  }

  /** One setData for the whole pointer: hover, selection and ghost together. */
  function drawPointer(map: MapLibreMap): void {
    setPointer(map, [...hoverFeatures, ...selectionFeatures])
  }

  /**
   * Put the source, the images and the layers on the map.
   *
   * The network and the style arrive in either order, so this is called from
   * both sides and simply waits when the style is not ready yet.
   */
  /**
   * The circle of the area being studied, kept on the map.
   *
   * It says how big the area is, so it is drawn as soon as the area is known,
   * without waiting for its streets: it only needs the map. Under the graph,
   * so the streets and the result colours stay on top of it.
   */
  function drawArea(): void {
    const map = mapRef.value
    if (!map || !scenarioStore.isOpen || trafficStore.pickMode) return

    const area = trafficStore.area
    try {
      if (!map.getSource(AREA_SOURCE)) {
        map.addSource(AREA_SOURCE, {
          type: 'geojson',
          data: emptyArea() as unknown as FeatureCollection
        })
      }
      if (!map.getLayer(AREA_RING_LAYER)) {
        const under = map.getLayer('bc-graph-one')
          ? 'bc-graph-one'
          : map.getLayer(BEFORE_LAYER)
            ? BEFORE_LAYER
            : undefined
        map.addLayer(areaRingLayer(colors.value), under)
      }
      // The default city is not a circle the user drew, so it has no ring.
      setData(map, AREA_SOURCE, area ? areaFeatures(area, true) : emptyArea())
    } catch {
      retryLater(map)
    }
  }

  /**
   * Send the camera to the network that just landed, when it is off screen.
   *
   * The circle and its streets always change together now, but the camera
   * does not: an investigation opens where the map was left, which can be
   * another city. The ring would then sit outside the view, over an empty
   * map. When the network is already in sight nothing moves, so opening the
   * workbench, or confirming an area the picker has just framed, is still.
   */
  function frameGraph(source: GraphSource): void {
    const map = mapRef.value
    if (!map) return
    const [[west, south], [east, north]] = source.bounds
    if (west === east && south === north) return

    const view = map.getBounds()
    const seen =
      east >= view.getWest() &&
      west <= view.getEast() &&
      north >= view.getSouth() &&
      south <= view.getNorth()
    if (seen) return

    map.fitBounds(source.bounds, {
      padding: { top: 80, bottom: 80, left: 80, right: 80 + DOCK_WIDTH },
      maxZoom: 16,
      duration: 600
    })
  }

  function mount(): void {
    const map = mapRef.value
    if (!map) return
    // The workbench owns the graph, the scenario and the results. With it
    // closed the map goes back to the basemap and the datasets, as it was
    // before the workbench was ever opened.
    if (!scenarioStore.isOpen) return
    // Picking an area shows the whole country, the city under it is noise.
    if (trafficStore.pickMode) return

    drawArea()

    const source = graph.value
    if (!source) return

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
      } else if (mountedGraph !== source) {
        // Another area: same source, other streets. The feature ids belong to
        // the old network, so the states that name them go too.
        setGraphEdges(map, source.collection)
        resultIds = []
        hoverIds = []
      }
      if (!map.getSource(BADGE_SOURCE)) {
        map.addSource(BADGE_SOURCE, {
          type: 'geojson',
          data: emptyBadges() as unknown as FeatureCollection
        })
      }
      if (!map.getSource(POINTER_SOURCE)) {
        map.addSource(POINTER_SOURCE, {
          type: 'geojson',
          data: emptyPointer() as unknown as FeatureCollection
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
      for (const layer of buildGraphLayers({ colors: colors.value, mode: inkMode.value })) {
        if (map.getLayer(layer.id)) map.removeLayer(layer.id)
        map.addLayer(layer, before)
      }
    } catch {
      // mount() is idempotent, a half-added overlay is fixed by the retry.
      retryLater(map)
      return
    }

    const landed = mountedGraph !== source
    mountedOn = map
    mountedGraph = source
    if (landed) frameGraph(source)
    redraw()
    drawPointer(map)
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
    for (const id of [...graphLayerIds(), AREA_RING_LAYER]) {
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

    applyModifications(map, draw, inkMode.value)
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
    const show = shown.value === 'routing' && mode !== 'none'

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

  /** New route lines mean the old pointer state points at nothing. */
  function setRoutes(map: MapLibreMap, routes: { features: CvrpRouteRef[] }): void {
    map.removeFeatureState({ source: CVRP_SOURCE })
    routeRefs = routes.features
    hoveredRoute = null
  }

  function applyRoutes(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    const result = cvrpStore.lastResult
    const show = shown.value === 'cvrp' && !!result

    const points = cvrpStore.showCentroids
      ? pointFeatures(cvrpStore.centroids, result?.n_missing_clients ?? 0)
      : []

    if (!show || !result) {
      setRoutes(map, EMPTY)
      applyCvrp(map, points.length ? { routes: EMPTY, points, mode: 'routes', stale: false } : null)
      return
    }

    if (cvrpStore.visualizationMode === 'heatmap') {
      setRoutes(map, EMPTY)
      applyCvrp(map, { routes: EMPTY, points, mode: 'routes', stale: false })
      applyLoads()
      return
    }

    const routes = routeFeatures(result.route_segments, result.n_routes)
    setRoutes(map, routes)
    applyCvrp(map, { routes, points, mode: 'routes', stale: cvrpStore.isStale })
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
    // The pointer runs on every frame, the state only changes when the vehicle
    // under it does.
    if (routeId === hoveredRoute) return
    hoveredRoute = routeId
    applyCvrpHover(map, routeId, routeRefs)
  }

  function setDataFilter(map: MapLibreMap, ids: number[]): void {
    const filter = idFilter(ids)
    if (map.getLayer('bc-data')) map.setFilter('bc-data', filter)
    if (map.getLayer('bc-data-casing')) map.setFilter('bc-data-casing', filter)
  }

  function applyHover(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    const hovered = scenarioStore.hovered
    hoverIds = hovered ? idsFor(hovered.key, hovered.dir) : []
    // one lane hovered: offset onto it. Both: stay on the centre line.
    hoverFeatures = hovered
      ? pointerFeatures(hoverIds, 'hover', hovered.dir === 'both' ? 0 : 1)
      : []
    drawPointer(map)
  }

  function applySelection(): void {
    const map = mapRef.value
    if (!map || mountedOn !== map) return

    selectedIds = []
    ghostIds = []
    selectionFeatures = []

    const selected = scenarioStore.selected
    if (!selected) {
      drawPointer(map)
      return
    }

    selectedIds = idsFor(selected.key, selected.dir)
    const lane = selected.dir === 'both' ? 0 : 1
    selectionFeatures = pointerFeatures(selectedIds, 'selected', lane)

    // With one lane selected, the other shows a dotted ghost so the user sees
    // which direction is left out.
    if (selected.dir !== 'both') {
      const other = selected.dir === 'fwd' ? 'bwd' : 'fwd'
      ghostIds = idsFor(selected.key, other)
      selectionFeatures.push(...pointerFeatures(ghostIds, 'ghost', 1))
    }

    drawPointer(map)
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

      // The workbench owns the graph. With it closed the map is a picture:
      // nothing to point at, and the card would offer a click that does
      // nothing. Same while the user picks an area: the circle owns the
      // pointer then, and its grab cursor must not be wiped here.
      if (!scenarioStore.isOpen || trafficStore.pickMode) {
        onMouseOut()
        const idle = mapRef.value
        if (idle && !trafficStore.pickMode) idle.getCanvas().style.cursor = ''
        return
      }

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
      if (map) map.getCanvas().style.cursor = hit && scenarioStore.isOpen ? 'pointer' : ''
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
    // The graph is always editable while the workbench is open, there is no
    // mode to turn on first. Picking an area is the exception: a click moves
    // the circle, it never touches a street.
    if (!scenarioStore.isOpen || trafficStore.pickMode) return
    const hit = hitAt(event)

    if (!hit) {
      // clicking empty map drops the selection and closes the popover
      scenarioStore.select(null)
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
    if (event.key === 'Escape' && scenarioStore.selected) scenarioStore.select(null)
  }

  /**
   * Moving the map drops the selection.
   *
   * The popover sits at fixed screen pixels, so a pan or a zoom would leave it
   * pointing at the wrong street.
   */
  function onMoveStart(): void {
    if (scenarioStore.selected) scenarioStore.select(null)
  }

  /**
   * Fit the camera on some streets, keeping them clear of the dock.
   *
   * The dock covers the right of the canvas, so the right padding carries its
   * width on top of the normal margin.
   */
  function focus(keys: string[]): void {
    const map = mapRef.value
    const source = graph.value
    if (!map || !source || keys.length === 0) return

    const bounds = new LngLatBounds()
    let any = false
    for (const key of keys) {
      const street = source.streets.get(key)
      const id = street?.fwdId ?? street?.bwdId
      if (id === undefined) continue
      const feature = source.collection.features[id]
      if (!feature) continue
      for (const point of feature.geometry.coordinates) {
        bounds.extend(point)
        any = true
      }
    }
    if (!any) return

    map.fitBounds(bounds, {
      padding: { top: 80, bottom: 80, left: 80, right: 80 + DOCK_WIDTH },
      maxZoom: 16,
      duration: 600
    })
  }

  function attach(map: MapLibreMap): void {
    // Shift-click picks one lane, so the shift-drag box zoom has to go: it eats
    // the mousedown and MapLibre never fires the click.
    map.boxZoom.disable()
    map.on('mousemove', onMouseMove)
    map.on('mouseout', onMouseOut)
    map.on('click', onClick)
    map.on('movestart', onMoveStart)
    // style.load fires on every setStyle, which drops our layers with it
    map.on('style.load', mount)
    window.addEventListener('keydown', onKeyDown)
  }

  function detach(map: MapLibreMap): void {
    map.boxZoom.enable()
    map.off('mousemove', onMouseMove)
    map.off('mouseout', onMouseOut)
    map.off('click', onClick)
    map.off('movestart', onMoveStart)
    map.off('style.load', mount)
    window.removeEventListener('keydown', onKeyDown)
  }

  // Mount as soon as both the map and the network are there, in either order.
  watch([mapRef, graph], () => mount(), { immediate: true })

  // Closing the workbench takes the whole overlay off the map, the scenario
  // ink and the badges with it. The sources stay, so opening again does not
  // re-fetch the 6 MB network.
  watch(
    () => scenarioStore.isOpen,
    (open) => {
      if (open) {
        mount()
        return
      }
      // Drop what the pointer was on, or reopening would draw a stale accent
      // line until the mouse moves.
      hoverFeatures = []
      selectionFeatures = []
      unmount()
    },
    { immediate: true }
  )

  // Picking an area takes the city off the map, confirming puts the new one on.
  watch(
    () => trafficStore.pickMode,
    (picking) => {
      if (picking) {
        hoverFeatures = []
        selectionFeatures = []
        unmount()
      } else {
        mount()
      }
    }
  )

  watch(() => trafficStore.area, drawArea)
  watch(() => scenarioStore.edgeModifications, redraw)
  // Only a change of ink treatment needs the layers rebuilt, not every switch
  // of the lit zone.
  watch(inkMode, () => {
    unmount()
    mount()
  })
  // Registered before the CVRP one on purpose: both write the same result
  // colours, so on a tab switch this one clears them before applyLoads writes.
  watch(
    () => [
      trafficStore.resultTotals,
      trafficStore.activeVisualization,
      trafficStore.filterBusRoutes,
      trafficStore.isStale,
      shown.value
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
      shown.value
    ],
    applyRoutes
  )
  watch(() => scenarioStore.hovered, applyHover)
  watch(() => scenarioStore.selected, applySelection)
  watch(colors, () => {
    unmount()
    mount()
  })

  return {
    mount,
    unmount,
    redraw,
    applyResult,
    applyRoutes,
    hoverRoute,
    focus,
    attach,
    detach,
    hitAt
  }
}

/** Build the source once the network is loaded. */
export function graphSourceFrom(edges: EdgeGeometry[]): GraphSource | null {
  if (edges.length === 0) return null
  return buildGraphSource(edges)
}
