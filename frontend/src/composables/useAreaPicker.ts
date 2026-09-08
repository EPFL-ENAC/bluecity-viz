import { swissNetworkLayer } from '@/config/toolLayers'
import {
  ApiError,
  previewArea,
  type AreaPreview,
  type AreaSelection
} from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  estimateCircle,
  insideCoverage,
  loadDensity,
  mPerDegLon as mPerDegLonOf,
  type Density,
  type DensityEstimate
} from '@/utils/areaDensity'
import { ScatterplotLayer } from '@deck.gl/layers'
import type { Map as MapLibre } from 'maplibre-gl'
import {
  computed,
  effectScope,
  getCurrentInstance,
  inject,
  shallowRef,
  watch,
  type EffectScope,
  type Ref
} from 'vue'

// Blue City blue, the only accent in the design system.
const BLUE: [number, number, number] = [5, 0, 225]

// The whole country, so the user sees where they can go.
const SWITZERLAND: [[number, number], [number, number]] = [
  [5.9, 45.8],
  [10.6, 47.9]
]
// The dock covers the right of the map.
const DOCK_PADDING = { top: 40, bottom: 40, left: 40, right: 380 }

export type AreaStatus =
  | 'ok'
  | 'too_sparse'
  | 'too_large'
  | 'disconnected'
  | 'outside_coverage'
  /** this server has no Swiss network, so it runs on its own city only */
  | 'unavailable'

export interface AreaFeedback {
  status: AreaStatus
  /** counts under the circle, from the local file or from the server */
  estimate: DensityEstimate | null
  /** set once the server has answered for this exact circle */
  exact: AreaPreview | null
}

/** Fallbacks, used until GET /areas/limits answers. */
const FALLBACK_LIMITS = {
  min_nodes: 1000,
  max_nodes: 10000,
  max_edges: 20000,
  min_radius_m: 500,
  max_radius_m: 10000
}

// Module scope: the panel and the map layer both call this, and they must see
// the same circle and the same answer.
const density = shallowRef<Density | null>(null)
const exact = shallowRef<AreaPreview | null>(null)
const isChecking = shallowRef(false)
const unavailable = shallowRef(false)

// The circle the exact answer describes, so a stale answer is never shown.
let checkedKey = ''
let checkTimer: ReturnType<typeof setTimeout> | null = null
let mapRef: Ref<{ map?: MapLibre }> | undefined
let shared: ReturnType<typeof build> | null = null
// Its own scope: the panel that builds it can unmount (the user switches
// tool) and the watchers must stay alive for the map layer.
let scope: EffectScope | null = null

/**
 * The circle the user drags, and the "can the tool run here" answer.
 *
 * Two sources, on purpose. The local density file gives an answer on every
 * pointer move with no network at all. POST /areas/preview gives the exact
 * counts and the connectivity, but only when the drag stops.
 */
export function useAreaPicker() {
  // inject only works during setup, and the map is the same for everyone
  if (!mapRef && getCurrentInstance()) {
    mapRef = inject<Ref<{ map?: MapLibre }>>('mapRef')
  }
  if (!shared) {
    scope = effectScope(true)
    shared = scope.run(build) as ReturnType<typeof build>
  }
  return shared
}

function build() {
  const trafficStore = useTrafficAnalysisStore()

  loadDensity().then((data) => {
    density.value = data
  })
  trafficStore.loadAreaLimits()

  const limits = computed(() => trafficStore.areaLimits ?? FALLBACK_LIMITS)

  const estimate = computed<DensityEstimate | null>(() => {
    const circle = trafficStore.draftArea
    if (!circle || !density.value) return null
    return estimateCircle(density.value, circle.lon, circle.lat, circle.radiusM)
  })

  /** What the panel shows: the server answer when we have it, else the file. */
  const feedback = computed<AreaFeedback>(() => {
    const circle = trafficStore.draftArea
    if (!circle) return { status: 'ok', estimate: null, exact: null }
    if (unavailable.value) return { status: 'unavailable', estimate: null, exact: null }

    const coverageBbox = trafficStore.areaLimits?.coverage_bbox ?? null
    if (!insideCoverage(coverageBbox, circle.lon, circle.lat, circle.radiusM)) {
      return { status: 'outside_coverage', estimate: estimate.value, exact: null }
    }

    const answer = exact.value && checkedKey === keyOf(circle) ? exact.value : null
    if (answer) {
      return {
        status: answer.ok ? 'ok' : ((answer.code ?? 'too_sparse') as AreaStatus),
        estimate: { junctions: answer.junction_count, edges: answer.edge_count },
        exact: answer
      }
    }

    const counts = estimate.value
    if (!counts) return { status: 'ok', estimate: null, exact: null }
    if (counts.junctions < limits.value.min_nodes) {
      return { status: 'too_sparse', estimate: counts, exact: null }
    }
    if (counts.edges > limits.value.max_edges) {
      return { status: 'too_large', estimate: counts, exact: null }
    }
    return { status: 'ok', estimate: counts, exact: null }
  })

  const canUse = computed(() => feedback.value.status === 'ok')

  function keyOf(circle: AreaSelection): string {
    return `${circle.lon.toFixed(4)}_${circle.lat.toFixed(4)}_${Math.round(circle.radiusM)}`
  }

  /** Ask the server for the exact counts. Called when the drag stops. */
  function checkNow(): void {
    const circle = trafficStore.draftArea
    if (!circle) return
    const key = keyOf(circle)
    if (key === checkedKey && exact.value) return

    if (checkTimer) clearTimeout(checkTimer)
    checkTimer = setTimeout(() => {
      isChecking.value = true
      previewArea(circle)
        .then((answer) => {
          checkedKey = key
          exact.value = answer
        })
        .catch((error) => {
          // the local estimate stays on screen, it is enough to keep dragging
          exact.value = null
          if (error instanceof ApiError && error.code === 'no_swiss_graph') {
            unavailable.value = true
          }
        })
        .finally(() => {
          isChecking.value = false
        })
    }, 250)
  }

  /** A drag makes the server answer stale straight away. */
  function invalidate(): void {
    exact.value = null
    checkedKey = ''
  }

  /** Show the country network while the user picks, hide it after. */
  function showSwissNetwork(visible: boolean): void {
    const map = mapRef?.value?.map
    if (!map) return
    try {
      if (visible) {
        if (!map.getSource(swissNetworkLayer.sourceId)) {
          map.addSource(swissNetworkLayer.sourceId, swissNetworkLayer.source)
        }
        if (!map.getLayer(swissNetworkLayer.layer.id)) {
          map.addLayer(swissNetworkLayer.layer)
        }
        map.setLayoutProperty(swissNetworkLayer.layer.id, 'visibility', 'visible')
      } else if (map.getLayer(swissNetworkLayer.layer.id)) {
        map.setLayoutProperty(swissNetworkLayer.layer.id, 'visibility', 'none')
      }
    } catch (error) {
      // The style is still loading, or the file is not deployed. The picker
      // works without the backdrop, so this is not worth an error.
      console.warn('Could not show the Swiss network', error)
    }
  }

  function fitSwitzerland(): void {
    mapRef?.value?.map?.fitBounds(SWITZERLAND, { padding: DOCK_PADDING, duration: 600 })
  }

  function fitCircle(circle: AreaSelection): void {
    const map = mapRef?.value?.map
    if (!map) return
    const dLat = circle.radiusM / 111320
    const dLon = circle.radiusM / Math.max(mPerDegLonOf(circle.lat), 1)
    map.fitBounds(
      [
        [circle.lon - dLon, circle.lat - dLat],
        [circle.lon + dLon, circle.lat + dLat]
      ],
      { padding: DOCK_PADDING, duration: 600 }
    )
  }

  function setDragPan(enabled: boolean): void {
    const map = mapRef?.value?.map
    if (!map) return
    if (enabled) map.dragPan.enable()
    else map.dragPan.disable()
  }

  function moveTo(lon: number, lat: number): void {
    trafficStore.moveDraft(lon, lat)
    invalidate()
  }

  /** The circle and its centre handle, appended to the traffic layers. */
  const layers = computed(() => {
    const circle = trafficStore.draftArea
    if (!trafficStore.pickMode || !circle) return []

    const ok = canUse.value
    const fill: [number, number, number, number] = ok ? [...BLUE, 38] : [200, 30, 30, 38]
    const line: [number, number, number, number] = ok ? [...BLUE, 220] : [200, 30, 30, 220]
    const point = [{ position: [circle.lon, circle.lat] as [number, number] }]

    return [
      new ScatterplotLayer({
        id: 'area-picker-circle',
        data: point,
        pickable: true,
        stroked: true,
        filled: true,
        radiusUnits: 'meters',
        getPosition: (d: { position: [number, number] }) => d.position,
        getRadius: circle.radiusM,
        getFillColor: fill,
        getLineColor: line,
        lineWidthUnits: 'pixels',
        getLineWidth: 1.5,
        updateTriggers: {
          getRadius: circle.radiusM,
          getFillColor: ok,
          getLineColor: ok
        },
        onDragStart: () => setDragPan(false),
        onDrag: (info: any) => {
          if (info?.coordinate) moveTo(info.coordinate[0], info.coordinate[1])
        },
        onDragEnd: () => {
          setDragPan(true)
          checkNow()
        }
      }),
      new ScatterplotLayer({
        id: 'area-picker-handle',
        data: point,
        pickable: false,
        stroked: true,
        filled: true,
        radiusUnits: 'pixels',
        getPosition: (d: { position: [number, number] }) => d.position,
        getRadius: 4,
        getFillColor: [255, 255, 255, 255],
        getLineColor: line,
        lineWidthUnits: 'pixels',
        getLineWidth: 1.5,
        updateTriggers: { getLineColor: ok }
      })
    ]
  })

  /** A click on the map with nothing under it moves the circle there. */
  function handleMapClick(info: any): boolean {
    if (!trafficStore.pickMode || !trafficStore.draftArea) return false
    if (!info?.coordinate) return false
    moveTo(info.coordinate[0], info.coordinate[1])
    checkNow()
    return true
  }

  // The radius slider changes the circle without a drag, check that one too.
  watch(
    () => trafficStore.draftArea?.radiusM,
    (radius, previous) => {
      if (radius === undefined || previous === undefined) return
      invalidate()
      checkNow()
    }
  )

  // The camera before the picker opened, so Cancel puts it back.
  let savedCamera: { center: [number, number]; zoom: number } | null = null

  watch(
    () => trafficStore.pickMode,
    (on) => {
      const map = mapRef?.value?.map
      if (on) {
        if (map) {
          const centre = map.getCenter()
          savedCamera = { center: [centre.lng, centre.lat], zoom: map.getZoom() }
        }
        showSwissNetwork(true)
        fitSwitzerland()
        checkNow()
        return
      }

      invalidate()
      setDragPan(true)
      if (checkTimer) clearTimeout(checkTimer)
      showSwissNetwork(false)

      // Confirmed: look at the area. Cancelled: back where we were.
      if (trafficStore.area) fitCircle(trafficStore.area)
      else if (savedCamera && map) {
        map.easeTo({ center: savedCamera.center, zoom: savedCamera.zoom, duration: 600 })
      }
      savedCamera = null
    }
  )

  return {
    layers,
    feedback,
    canUse,
    isChecking,
    limits,
    handleMapClick,
    checkNow
  }
}

/** Tests only: forget the shared picker so the next call builds a new one. */
export function resetAreaPicker(): void {
  scope?.stop()
  scope = null
  shared = null
  mapRef = undefined
  density.value = null
  exact.value = null
  isChecking.value = false
  unavailable.value = false
  checkedKey = ''
  if (checkTimer) clearTimeout(checkTimer)
  checkTimer = null
}
