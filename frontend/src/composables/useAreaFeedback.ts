import {
  ApiError,
  areaKey,
  previewArea,
  type AreaPreview,
  type AreaSelection
} from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { estimateCircle, insideCoverage, loadDensity, type Density } from '@/utils/areaDensity'
import { computed, shallowRef } from 'vue'

export type AreaStatus =
  | 'ok'
  | 'too_sparse'
  | 'too_large'
  | 'disconnected'
  | 'outside_coverage'
  /** this server has no Swiss network, so it runs on its own city only */
  | 'unavailable'

export interface AreaCounts {
  /** junctions under the circle, the number the min rule reads */
  junctions: number
  /** streets under the circle, the number the max rule reads */
  edges: number
}

export interface AreaFeedback {
  status: AreaStatus
  /** counts under the circle, from the local file or from the server */
  estimate: AreaCounts | null
  /** set once the server has answered for this exact circle */
  exact: AreaPreview | null
}

/** Fallbacks, used until GET /areas/limits answers. Same as config.py. */
const FALLBACK_LIMITS = {
  min_junctions: 500,
  max_nodes: 10000,
  max_edges: 20000,
  min_radius_m: 500,
  max_radius_m: 10000
}

// The panel and the map overlay both call this and must see the same answer,
// so the state is module scope, not per caller.
const density = shallowRef<Density | null>(null)
const exact = shallowRef<AreaPreview | null>(null)
const isChecking = shallowRef(false)
const unavailable = shallowRef(false)

// The circle the exact answer describes, so a stale answer is never shown.
let checkedKey = ''
let checkTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Can the tool run on the circle being dragged.
 *
 * Two sources, on purpose. The local density file answers on every pointer
 * move with no network at all. POST /areas/preview gives the exact counts and
 * the connectivity, but only when the drag stops.
 */
export function useAreaFeedback() {
  const trafficStore = useTrafficAnalysisStore()

  void loadDensity().then((data) => {
    density.value = data
  })
  void trafficStore.loadAreaLimits()

  const limits = computed(() => trafficStore.areaLimits ?? FALLBACK_LIMITS)

  const estimate = computed<AreaCounts | null>(() => {
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

    const answer = exact.value && checkedKey === areaKey(circle) ? exact.value : null
    if (answer) {
      return {
        status: answer.ok ? 'ok' : ((answer.code ?? 'too_sparse') as AreaStatus),
        estimate: { junctions: answer.junction_count, edges: answer.edge_count },
        exact: answer
      }
    }

    const counts = estimate.value
    if (!counts) return { status: 'ok', estimate: null, exact: null }
    if (counts.junctions < limits.value.min_junctions) {
      return { status: 'too_sparse', estimate: counts, exact: null }
    }
    if (counts.edges > limits.value.max_edges) {
      return { status: 'too_large', estimate: counts, exact: null }
    }
    return { status: 'ok', estimate: counts, exact: null }
  })

  const canUse = computed(() => feedback.value.status === 'ok')

  /** Ask the server for the exact counts. Called when the drag stops. */
  function checkNow(): void {
    const circle: AreaSelection | null = trafficStore.draftArea
    if (!circle) return
    const key = areaKey(circle)
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

  /** A move makes the server answer stale straight away. */
  function invalidate(): void {
    exact.value = null
    checkedKey = ''
  }

  /** Nothing to check any more, the picker is closing. */
  function stopChecking(): void {
    if (checkTimer) clearTimeout(checkTimer)
    checkTimer = null
  }

  return { feedback, canUse, isChecking, limits, checkNow, invalidate, stopChecking }
}

/** Tests only: forget the shared answer. */
export function resetAreaFeedback(): void {
  density.value = null
  exact.value = null
  isChecking.value = false
  unavailable.value = false
  checkedKey = ''
  if (checkTimer) clearTimeout(checkTimer)
  checkTimer = null
}
