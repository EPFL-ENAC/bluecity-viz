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
  areaLayers
} from '@/utils/areaCircle'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
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
let moved = false
let savedCamera: { center: [number, number]; zoom: number } | null = null

function draw(): void {
  const current = map.value
  const circle = trafficStore.draftArea
  if (!current || mountedOn !== current || !circle) return
  const source = current.getSource(AREA_SOURCE)
  if (source && 'setData' in source) {
    ;(source as { setData: (value: unknown) => void }).setData(areaFeatures(circle, canUse.value))
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
      current.addSource(AREA_SOURCE, { type: 'geojson', data: emptyCollection() })
    }
    for (const layer of areaLayers(colors.value)) {
      if (current.getLayer(layer.id)) current.removeLayer(layer.id)
      current.addLayer(layer)
    }
    showSwissNetwork(current, true)
  } catch {
    retryLater(current)
    return
  }
  mountedOn = current
  draw()
}

function emptyCollection() {
  return { type: 'FeatureCollection', features: [] } as never
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
        current.addLayer(swissNetworkLayer.layer)
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
  if (!current || !overCircle(current, event)) return
  event.preventDefault()
  dragging = true
  moved = false
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
  moved = true
  trafficStore.moveDraft(event.lngLat.lng, event.lngLat.lat)
  invalidate()
}

function onMouseUp(): void {
  const current = map.value
  if (!dragging || !current) return
  dragging = false
  current.dragPan.enable()
  current.getCanvas().style.cursor = 'grab'
  if (moved) checkNow()
}

/** A click away from the circle moves it there, so no long drag is needed. */
function onClick(event: MapMouseEvent): void {
  if (moved) {
    moved = false
    return
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
  current.off('mousedown', onMouseDown)
  current.off('mousemove', onMouseMove)
  current.off('mouseup', onMouseUp)
  current.off('click', onClick)
  current.off('style.load', mount)
  current.dragPan.enable()
  current.getCanvas().style.cursor = ''
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
