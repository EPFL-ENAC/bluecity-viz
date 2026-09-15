<script setup lang="ts">
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { useCirclePick, type PickMode } from '@/composables/useCirclePick'
import { useMunicipalityPick } from '@/composables/useMunicipalityPick'
import { swissNetworkLayer, swissNetworkStyle } from '@/config/toolLayers'
import { areaKey, type AreaSelection } from '@/services/trafficAnalysis'
import { useApiKeyStore } from '@/stores/apiKey'
import { useThemeStore } from '@/stores/theme'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  AREA_SOURCE,
  areaFeatures,
  areaLayerIds,
  areaLayers,
  clipPathOfRings,
  emptyArea,
  ringOf
} from '@/utils/areaCircle'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { outlineFeatures, outlineRings } from '@/utils/areaOutline'
import { BEFORE_LAYER, setData } from '@/utils/bluecityGraph'
import { cdnRequest } from '@/utils/cdnRequest'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { municipalityBbox } from '@/utils/municipalities'
import { Map as MapLibre, type Map as MapLibreMap } from 'maplibre-gl'
import { computed, inject, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

// The area on the map while the user picks one. Mounted only in pick mode, so
// the component lifecycle is the show and hide.
//
// The shape itself (the ring, the handle, the invisible disc the drag points
// at) lives on the main map. The country network does not: it is drawn by a
// second map on a canvas of its own, on top of the first, that follows the
// same camera and is cut to the shape with a CSS clip-path. A map layer
// cannot be masked on its own, a mask covers everything under it, the basemap
// with it. A canvas can, and the browser does it on the GPU, so the drag
// costs nothing and the basemap stays whole outside the shape.
//
// The pointer depends on the mode: useCirclePick drags a circle,
// useMunicipalityPick clicks communes. One of them is attached at a time.

const trafficStore = useTrafficAnalysisStore()
const themeStore = useThemeStore()
const apiKeyStore = useApiKeyStore()
const { canUse, checkNow, invalidate, stopChecking, communes, lastOutline } = useAreaFeedback()

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
// the colour the network carries, so a drag does not set the same one again
let painted = ''
let savedCamera: { center: [number, number]; zoom: number } | null = null
// The area when the picker opened, to tell a confirm from a cancel.
let savedKey: string | null = null

const circlePick = useCirclePick({ map, invalidate, checkNow })
const municipalityPick = useMunicipalityPick({
  colors,
  canUse,
  communes,
  invalidate,
  checkNow
})
// The mode attached to the map now, null when the picker is not on a map.
let mode: PickMode | null = null

function modeOf(area: AreaSelection | null): PickMode {
  return area?.kind === 'municipalities' ? municipalityPick : circlePick
}

function draw(): void {
  const current = map.value
  const draft = trafficStore.draftArea
  if (!current || !draft) return
  if (mountedOn === current) {
    const features =
      draft.kind === 'circle'
        ? areaFeatures(draft, canUse.value)
        : outlineFeatures(lastOutline.value, canUse.value)
    setData(current, AREA_SOURCE, features)
  }
  clip()
  paintNetwork()
}

/** Cut the network canvas to the shape, in pixels of the current camera. */
function clip(): void {
  const current = map.value
  const box = networkBox.value
  if (!current || !box) return
  const draft = trafficStore.draftArea
  const rings =
    draft?.kind === 'circle'
      ? [ringOf(draft)]
      : draft?.kind === 'municipalities'
        ? outlineRings(lastOutline.value)
        : []
  const pixels = rings.map((ring) =>
    ring.map((point): [number, number] => {
      const pixel = current.project(point)
      return [pixel.x, pixel.y]
    })
  )
  box.style.clipPath = clipPathOfRings(pixels)
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

/**
 * Put the camera on an area. A set of communes is framed from the local index,
 * with `room` times its size around it, and stays put without the index or
 * with no commune yet.
 */
function fitArea(current: MapLibreMap, area: AreaSelection, room = 1) {
  if (area.kind === 'circle') {
    fitCircle(current, area, room)
    return
  }
  const index = communes.value
  const box = index && area.ofsIds.length ? municipalityBbox(area.ofsIds, index) : null
  if (!box) return
  const padLon = ((box[2] - box[0]) * (room - 1)) / 2
  const padLat = ((box[3] - box[1]) * (room - 1)) / 2
  current.fitBounds(
    [
      [box[0] - padLon, box[1] - padLat],
      [box[2] + padLon, box[3] + padLat]
    ],
    { padding: DOCK_PADDING, duration: 600 }
  )
}

watch([() => trafficStore.draftArea, canUse, lastOutline], draw, { deep: true })

// The dock switched between the circle and the communes: swap the pointer,
// and look at the new draft when there is one to look at.
watch(
  () => trafficStore.draftArea?.kind,
  (kind, previous) => {
    const current = map.value
    const draft = trafficStore.draftArea
    if (!current || !mode || !draft || kind === previous) return
    mode.detach(current)
    mode = modeOf(draft)
    mode.attach(current)
    fitArea(current, draft, PICK_ROOM)
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
  current.on('style.load', mount)
  mount()
  mountNetwork(current)
  // Stay where the user is. The country view needs basemap tiles nobody has
  // loaded yet, so it opens on a white map; here the tiles are already there,
  // and the shape only needs room around it.
  const draft = trafficStore.draftArea
  if (draft) fitArea(current, draft, PICK_ROOM)
  mode = modeOf(draft)
  mode.attach(current)
  checkNow()
}

function detach(current: MapLibreMap): void {
  mode?.detach(current)
  mode = null
  current.off('style.load', mount)
  unmountNetwork(current)
  for (const id of areaLayerIds()) {
    if (current.getLayer(id)) current.removeLayer(id)
  }
  mountedOn = null

  // A new area: look at it, its streets are on their way. Same one, or
  // cancelled: back where we were. Going back to the default city moves
  // nothing here, the overlay takes the camera there when it lands.
  const area = trafficStore.area
  if (area && areaKey(area) !== savedKey) fitArea(current, area)
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
