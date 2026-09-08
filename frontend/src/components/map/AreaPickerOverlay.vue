<script setup lang="ts">
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { swissNetworkLayer, swissNetworkStyle } from '@/config/toolLayers'
import { areaKey } from '@/services/trafficAnalysis'
import { useApiKeyStore } from '@/stores/apiKey'
import { useThemeStore } from '@/stores/theme'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  AREA_FILL_LAYER,
  AREA_SOURCE,
  areaFeatures,
  areaLayerIds,
  areaLayers,
  clipPathOf,
  emptyArea,
  ringOf
} from '@/utils/areaCircle'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { BEFORE_LAYER, setData } from '@/utils/bluecityGraph'
import { cdnRequest } from '@/utils/cdnRequest'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { Map as MapLibre, type Map as MapLibreMap, type MapMouseEvent } from 'maplibre-gl'
import { computed, inject, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

// The circle on the map while the user picks an area. Mounted only in pick
// mode, so the component lifecycle is the show and hide.
//
// The circle itself (the ring, the handle, the invisible disc the drag points
// at) lives on the main map. The country network does not: it is drawn by a
// second map on a canvas of its own, on top of the first, that follows the
// same camera and is cut to the circle with a CSS clip-path. A map layer
// cannot be masked on its own, a mask covers everything under it, the basemap
// with it. A canvas can, and the browser does it on the GPU, so the drag
// costs nothing and the basemap stays whole outside the circle.

const trafficStore = useTrafficAnalysisStore()
const themeStore = useThemeStore()
const apiKeyStore = useApiKeyStore()
const { canUse, checkNow, invalidate, stopChecking } = useAreaFeedback()

const mapComponentRef = inject<Ref<{ map?: MapLibreMap } | undefined>>('mapRef')
const map = computed(() => mapComponentRef?.value?.map)
const colors = computed(() => GRAPH_COLORS[themeStore.isDark ? 'dark' : 'light'])

// The dock covers the right of the map, same padding as useGraphOverlay.focus.
const DOCK_PADDING = { top: 80, bottom: 80, left: 80, right: 420 }
// Room around the circle while it is being dragged, in radii. Enough to see
// where to go, close enough that the basemap tiles are the ones already here.
const PICK_ROOM = 2.5

const networkBox = ref<HTMLDivElement | null>(null)
let network: MapLibre | null = null
let mountedOn: MapLibreMap | null = null
let waiting: MapLibreMap | null = null
let dragging = false
// Where the button went down, to tell a click from the end of a drag.
let downAt: { x: number; y: number } | null = null
// the colour the network carries, so a drag does not set the same one again
let painted = ''
let savedCamera: { center: [number, number]; zoom: number } | null = null
// The area when the picker opened, to tell a confirm from a cancel.
let savedKey: string | null = null

function draw(): void {
  const current = map.value
  const circle = trafficStore.draftArea
  if (!current || !circle) return
  if (mountedOn === current) setData(current, AREA_SOURCE, areaFeatures(circle, canUse.value))
  clip()
  paintNetwork()
}

/** Cut the network canvas to the circle, in pixels of the current camera. */
function clip(): void {
  const current = map.value
  const box = networkBox.value
  if (!current || !box) return
  const circle = trafficStore.draftArea
  const points = circle
    ? ringOf(circle).map((point): [number, number] => {
        const pixel = current.project(point)
        return [pixel.x, pixel.y]
      })
    : []
  box.style.clipPath = clipPathOf(points)
}

/** The streets inside the circle are the answer, so they carry its colour. */
function paintNetwork(): void {
  if (!network) return
  const tint = canUse.value ? colors.value.accent : colors.value.grey
  if (tint === painted) return
  try {
    network.setPaintProperty(swissNetworkLayer.layer.id, 'line-color', tint)
    painted = tint
  } catch {
    // the style is not parsed yet, it is inline so that is a matter of ticks
    network.once('style.load', paintNetwork)
  }
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
    // Under the names, so they stay readable over the ring.
    const under = current.getLayer(BEFORE_LAYER) ? BEFORE_LAYER : undefined
    for (const layer of areaLayers(colors.value)) {
      if (current.getLayer(layer.id)) current.removeLayer(layer.id)
      current.addLayer(layer, under)
    }
  } catch {
    retryLater(current)
    return
  }
  mountedOn = current
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

/**
 * The second map, the one that draws the network.
 *
 * Same camera as the main one, no interaction, no controls, and a transparent
 * canvas since its style has no background. The tiles carry the API key the
 * same way the main map sends it.
 */
function mountNetwork(current: MapLibreMap): void {
  const box = networkBox.value
  if (!box || network) return
  network = new MapLibre({
    container: box,
    style: swissNetworkStyle(),
    center: current.getCenter(),
    zoom: current.getZoom(),
    bearing: current.getBearing(),
    pitch: current.getPitch(),
    interactive: false,
    attributionControl: false,
    // Same key on the same CDN as the main map, or the archive never opens.
    transformRequest: cdnRequest(() => apiKeyStore.apiKey)
  })
  painted = ''
  paintNetwork()
  current.on('move', follow)
  follow()
}

/** The main map moved: same camera on the network, and the cut moves with it. */
function follow(): void {
  const current = map.value
  if (!current || !network) return
  network.jumpTo({
    center: current.getCenter(),
    zoom: current.getZoom(),
    bearing: current.getBearing(),
    pitch: current.getPitch()
  })
  clip()
}

function unmountNetwork(current: MapLibreMap): void {
  current.off('move', follow)
  network?.remove()
  network = null
}

/** Put the camera on a circle, with `room` times its radius around it. */
function fitCircle(
  current: MapLibreMap,
  circle: { lon: number; lat: number; radiusM: number },
  room = 1
) {
  const reach = circle.radiusM * room
  const dLat = reach / mPerDegLat
  const dLon = reach / Math.max(mPerDegLon(circle.lat), 1)
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
  painted = ''
  paintNetwork()
})

watch(map, (current, previous) => {
  if (previous) detach(previous)
  if (current) attach(current)
})

function attach(current: MapLibreMap): void {
  const centre = current.getCenter()
  savedCamera = { center: [centre.lng, centre.lat], zoom: current.getZoom() }
  savedKey = areaKey(trafficStore.area)
  current.on('mousedown', onMouseDown)
  current.on('mousemove', onMouseMove)
  current.on('mouseup', onMouseUp)
  current.on('click', onClick)
  current.on('style.load', mount)
  mount()
  mountNetwork(current)
  // Stay where the user is. The country view needs basemap tiles nobody has
  // loaded yet, so it opens on a white map; here the tiles are already there,
  // and the circle only needs room around it to be dragged.
  const draft = trafficStore.draftArea
  if (draft) fitCircle(current, draft, PICK_ROOM)
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
  unmountNetwork(current)
  for (const id of areaLayerIds()) {
    if (current.getLayer(id)) current.removeLayer(id)
  }
  mountedOn = null

  // A new circle: look at it, its streets are on their way. Same one, or
  // cancelled: back where we were. Going back to the default city moves
  // nothing here, the overlay takes the camera there when it lands.
  const area = trafficStore.area
  if (area && areaKey(area) !== savedKey) fitCircle(current, area)
  else if (savedCamera) {
    current.easeTo({ center: savedCamera.center, zoom: savedCamera.zoom, duration: 600 })
  }
  savedCamera = null
  savedKey = null
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

<template>
  <div ref="networkBox" class="area-network" />
</template>

<style scoped>
/* Same box as the map under it, so a pixel of one is a pixel of the other. */
.area-network {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
</style>
