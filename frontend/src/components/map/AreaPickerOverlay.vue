<script setup lang="ts">
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { swissNetworkLayer } from '@/config/toolLayers'
import { useThemeStore } from '@/stores/theme'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  AREA_FILL_LAYER,
  AREA_SOURCE,
  areaFeatures,
  areaLayerIds,
  areaLayers,
  emptyArea
} from '@/utils/areaCircle'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { BEFORE_LAYER, setData } from '@/utils/bluecityGraph'
import { GRAPH_COLORS, WATER_LAYERS } from '@/utils/epflBasemap'
import type { LayerSpecification, Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { computed, inject, onMounted, onUnmounted, watch, type Ref } from 'vue'

// The circle on the map while the user picks an area. Mounted only in pick
// mode, so the component lifecycle is the show and hide.

const trafficStore = useTrafficAnalysisStore()
const themeStore = useThemeStore()
const { canUse, checkNow, invalidate, stopChecking } = useAreaFeedback()

const mapComponentRef = inject<Ref<{ map?: MapLibreMap } | undefined>>('mapRef')
const map = computed(() => mapComponentRef?.value?.map)
const colors = computed(() => GRAPH_COLORS[themeStore.isDark ? 'dark' : 'light'])

// The whole country, so the user sees where they can go.
const SWITZERLAND: [[number, number], [number, number]] = [
  [5.9, 45.8],
  [10.6, 47.9]
]
// The dock covers the right of the map, same padding as useGraphOverlay.focus.
const DOCK_PADDING = { top: 80, bottom: 80, left: 80, right: 420 }

let mountedOn: MapLibreMap | null = null
let waiting: MapLibreMap | null = null
let dragging = false
// Where the button went down, to tell a click from the end of a drag.
let downAt: { x: number; y: number } | null = null
// the colour the network carries, so a drag does not set the same one again
let painted = ''
let savedCamera: { center: [number, number]; zoom: number } | null = null

function draw(): void {
  const current = map.value
  const circle = trafficStore.draftArea
  if (!current || mountedOn !== current || !circle) return
  // One setData for the mask, the ring and the handle: the drag costs three
  // features, the country network on the map below is never touched.
  setData(current, AREA_SOURCE, areaFeatures(circle, canUse.value))
  paintNetwork(current)
}

/** The streets inside the circle are the answer, so they carry its colour. */
function paintNetwork(current: MapLibreMap): void {
  if (!current.getLayer(swissNetworkLayer.layer.id)) return
  const tint = canUse.value ? colors.value.accent : colors.value.grey
  if (tint === painted) return
  painted = tint
  current.setPaintProperty(swissNetworkLayer.layer.id, 'line-color', tint)
}

/**
 * MapLibre refuses addSource and addLayer until the style JSON is parsed, and
 * it has no flag for that, so try and retry on the next event.
 */
function mount(): void {
  const current = map.value
  if (!current) return
  try {
    if (!current.getSource(AREA_SOURCE)) {
      current.addSource(AREA_SOURCE, { type: 'geojson', data: emptyArea() as never })
    }
    // Under the names, so the user can still read where they are outside the
    // circle. The network goes first, the mask covers it, the ring sits on top.
    const under = current.getLayer(BEFORE_LAYER) ? BEFORE_LAYER : undefined
    showSwissNetwork(current, true)
    for (const layer of areaLayers(colors.value)) {
      if (current.getLayer(layer.id)) current.removeLayer(layer.id)
      current.addLayer(layer, under)
    }
    showWater(current)
  } catch {
    retryLater(current)
    return
  }
  mountedOn = current
  painted = ''
  draw()
}

function retryLater(current: MapLibreMap): void {
  if (waiting === current) return
  waiting = current
  const again = () => {
    current.off('style.load', again)
    current.off('idle', again)
    waiting = null
    mount()
  }
  current.on('style.load', again)
  current.on('idle', again)
}

/** Show the country network, so the user sees where the tool has streets. */
function showSwissNetwork(current: MapLibreMap, visible: boolean): void {
  try {
    if (visible) {
      if (!current.getSource(swissNetworkLayer.sourceId)) {
        current.addSource(swissNetworkLayer.sourceId, swissNetworkLayer.source)
      }
      if (!current.getLayer(swissNetworkLayer.layer.id)) {
        const under = current.getLayer(BEFORE_LAYER) ? BEFORE_LAYER : undefined
        current.addLayer(swissNetworkLayer.layer, under)
      }
      current.setLayoutProperty(swissNetworkLayer.layer.id, 'visibility', 'visible')
    } else if (current.getLayer(swissNetworkLayer.layer.id)) {
      current.setLayoutProperty(swissNetworkLayer.layer.id, 'visibility', 'none')
    }
  } catch (error) {
    // The picker works without the backdrop, so a missing file is not an error.
    console.warn('Could not show the Swiss network', error)
  }
}

/** The id a copy of a basemap water layer takes above the mask. */
function echoId(id: string): string {
  return `${id}-over-area`
}

/**
 * Draw the lakes and the rivers again, on top of the mask.
 *
 * The mask hides the whole basemap, not only the streets, and a blank country
 * is hard to read. Water is the one thing safe to put back: no street runs
 * inside a lake, so the copy hides nothing inside the circle either.
 */
function showWater(current: MapLibreMap): void {
  const style = current.getStyle()
  for (const id of WATER_LAYERS) {
    const source = style.layers.find((layer) => layer.id === id)
    if (!source) continue
    const copy = { ...source, id: echoId(id) } as LayerSpecification
    if (current.getLayer(copy.id)) current.removeLayer(copy.id)
    current.addLayer(copy, AREA_FILL_LAYER)
  }
}

function hideWater(current: MapLibreMap): void {
  for (const id of WATER_LAYERS) {
    if (current.getLayer(echoId(id))) current.removeLayer(echoId(id))
  }
}

function fitCircle(current: MapLibreMap, circle: { lon: number; lat: number; radiusM: number }) {
  const dLat = circle.radiusM / mPerDegLat
  const dLon = circle.radiusM / Math.max(mPerDegLon(circle.lat), 1)
  current.fitBounds(
    [
      [circle.lon - dLon, circle.lat - dLat],
      [circle.lon + dLon, circle.lat + dLat]
    ],
    { padding: DOCK_PADDING, duration: 600 }
  )
}

function overCircle(current: MapLibreMap, event: MapMouseEvent): boolean {
  if (!current.getLayer(AREA_FILL_LAYER)) return false
  return current.queryRenderedFeatures(event.point, { layers: [AREA_FILL_LAYER] }).length > 0
}

function onMouseDown(event: MapMouseEvent): void {
  const current = map.value
  if (!current) return
  downAt = { x: event.point.x, y: event.point.y }
  if (!overCircle(current, event)) return
  event.preventDefault()
  dragging = true
  current.dragPan.disable()
  current.getCanvas().style.cursor = 'grabbing'
}

function onMouseMove(event: MapMouseEvent): void {
  const current = map.value
  if (!current) return
  if (!dragging) {
    current.getCanvas().style.cursor = overCircle(current, event) ? 'grab' : ''
    return
  }
  trafficStore.moveDraft(event.lngLat.lng, event.lngLat.lat)
  invalidate()
}

function onMouseUp(): void {
  const current = map.value
  if (!dragging || !current) return
  dragging = false
  current.dragPan.enable()
  current.getCanvas().style.cursor = 'grab'
  // Same circle means the same key, and checkNow answers from what it has.
  checkNow()
}

/**
 * A click away from the circle moves it there, so no long drag is needed.
 *
 * A drag ends with a click too, and MapLibre does not always send it, so a
 * flag set during the drag would stay on and eat the next real click. The
 * distance from the button going down says it: a click does not move.
 */
function onClick(event: MapMouseEvent): void {
  const from = downAt
  downAt = null
  if (from) {
    const dx = event.point.x - from.x
    const dy = event.point.y - from.y
    if (dx * dx + dy * dy > 9) return
  }
  trafficStore.moveDraft(event.lngLat.lng, event.lngLat.lat)
  invalidate()
  checkNow()
}

watch([() => trafficStore.draftArea, canUse], draw, { deep: true })

// The radius slider moves the circle without a drag, check that one too.
watch(
  () => trafficStore.draftArea?.radiusM,
  (radius, previous) => {
    if (radius === undefined || previous === undefined) return
    invalidate()
    checkNow()
  }
)

watch(colors, () => {
  if (mountedOn) mount()
})

watch(map, (current, previous) => {
  if (previous) detach(previous)
  if (current) attach(current)
})

function attach(current: MapLibreMap): void {
  const centre = current.getCenter()
  savedCamera = { center: [centre.lng, centre.lat], zoom: current.getZoom() }
  current.on('mousedown', onMouseDown)
  current.on('mousemove', onMouseMove)
  current.on('mouseup', onMouseUp)
  current.on('click', onClick)
  current.on('style.load', mount)
  mount()
  current.fitBounds(SWITZERLAND, { padding: DOCK_PADDING, duration: 600 })
  checkNow()
}

function detach(current: MapLibreMap): void {
  downAt = null
  current.off('mousedown', onMouseDown)
  current.off('mousemove', onMouseMove)
  current.off('mouseup', onMouseUp)
  current.off('click', onClick)
  current.off('style.load', mount)
  current.dragPan.enable()
  current.getCanvas().style.cursor = ''
  hideWater(current)
  for (const id of areaLayerIds()) {
    if (current.getLayer(id)) current.removeLayer(id)
  }
  showSwissNetwork(current, false)
  mountedOn = null

  // Confirmed: look at the area. Cancelled: back where we were.
  if (trafficStore.area) fitCircle(current, trafficStore.area)
  else if (savedCamera) {
    current.easeTo({ center: savedCamera.center, zoom: savedCamera.zoom, duration: 600 })
  }
  savedCamera = null
}

onMounted(() => {
  const current = map.value
  if (current) attach(current)
})

onUnmounted(() => {
  stopChecking()
  const current = map.value
  if (current) detach(current)
})
</script>

<template><span /></template>
