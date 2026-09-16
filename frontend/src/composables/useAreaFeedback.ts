import {
  ApiError,
  areaKey,
  previewArea,
  type AreaOutline,
  type AreaPreview,
  type AreaSelection
} from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { estimateCircle, insideCoverage, loadDensity, type Density } from '@/utils/areaDensity'
import { contiguous, loadMunicipalities, type CommuneIndex } from '@/utils/municipalities'
import { computed, shallowRef } from 'vue'

export type AreaStatus =
  | 'ok'
  | 'too_sparse'
  | 'too_large'
  | 'disconnected'
  | 'outside_coverage'
  /** the communes picked do not share a border */
  | 'not_contiguous'
  /** this server has no Swiss network, so it runs on its own city only */
  | 'unavailable'
  /** no commune picked yet */
  | 'empty'
  /** more communes than one request may carry */
  | 'too_many'
  /** communes picked, the server has not answered yet */
  | 'checking'

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
/** Same as max_municipalities in config.py, until GET /areas/limits answers. */
const FALLBACK_MAX_MUNICIPALITIES = 100

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
const communes = shallowRef<CommuneIndex | null>(null)
const exact = shallowRef<AreaPreview | null>(null)
const isChecking = shallowRef(false)
const unavailable = shallowRef(false)
// Only the communes: the server has the network but no boundaries file.
const noMunicipalities = shallowRef(false)
// The last outline the server gave for a set of communes. It stays while the
// next answer is on its way, so the network does not blink off on each click.
const outline = shallowRef<AreaOutline | null>(null)

// The circle the exact answer describes, so a stale answer is never shown.
let checkedKey = ''
let checkTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Can the tool run on the area being picked.
 *
 * Two sources, on purpose. For a circle, the local density file answers on
 * every pointer move with no network at all. For communes, the local index
 * says at once when they do not touch. POST /areas/preview gives the exact
 * counts and the connectivity, when the drag stops or after a click.
 */
export function useAreaFeedback() {
  const trafficStore = useTrafficAnalysisStore()

  void loadDensity().then((data) => {
    density.value = data
  })
  void loadMunicipalities().then((data) => {
    communes.value = data
  })
  void trafficStore.loadAreaLimits()

  const limits = computed(() => trafficStore.areaLimits ?? FALLBACK_LIMITS)

  const estimate = computed<AreaCounts | null>(() => {
    const circle = trafficStore.draftArea
    if (circle?.kind !== 'circle' || !density.value) return null
    return estimateCircle(density.value, circle.lon, circle.lat, circle.radiusM)
  })

  /** What the panel shows: the server answer when we have it, else the file. */
  const feedback = computed<AreaFeedback>(() => {
    const circle = trafficStore.draftArea
    if (!circle) return { status: 'ok', estimate: null, exact: null }
    if (unavailable.value) return { status: 'unavailable', estimate: null, exact: null }
    if (circle.kind === 'municipalities') return municipalityFeedback(circle.ofsIds)

    const coverageBbox = trafficStore.areaLimits?.coverage_bbox ?? null
    if (
      circle.kind === 'circle' &&
      !insideCoverage(coverageBbox, circle.lon, circle.lat, circle.radiusM)
    ) {
      return { status: 'outside_coverage', estimate: estimate.value, exact: null }
    }

    const answer = answerFor(circle)
    if (answer) return answer

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

  /** The server answer for this exact area, or null when it is stale or missing. */
  function answerFor(area: AreaSelection): AreaFeedback | null {
    const answer = exact.value && checkedKey === areaKey(area) ? exact.value : null
    if (!answer) return null
    return {
      status: answer.ok ? 'ok' : ((answer.code ?? 'too_sparse') as AreaStatus),
      estimate: { junctions: answer.junction_count, edges: answer.edge_count },
      exact: answer
    }
  }

  // No local count for communes: never say ok before the server does.
  function municipalityFeedback(ofsIds: number[]): AreaFeedback {
    if (noMunicipalities.value) return { status: 'unavailable', estimate: null, exact: null }
    if (ofsIds.length === 0) return { status: 'empty', estimate: null, exact: null }
    if (tooMany(ofsIds)) return { status: 'too_many', estimate: null, exact: null }
    if (communes.value && !contiguous(ofsIds, communes.value)) {
      return { status: 'not_contiguous', estimate: null, exact: null }
    }
    return (
      answerFor({ kind: 'municipalities', ofsIds }) ?? {
        status: 'checking',
        estimate: null,
        exact: null
      }
    )
  }

  // The server refuses the request past this count, so it is never sent.
  function tooMany(ofsIds: number[]): boolean {
    const max = trafficStore.areaLimits?.max_municipalities ?? FALLBACK_MAX_MUNICIPALITIES
    return ofsIds.length > max
  }

  const canUse = computed(() => feedback.value.status === 'ok')

  /**
   * The outline to cut the network to, while communes are picked. None when
   * the communes do not touch or are too many: the last outline would then
   * draw a ring around another selection than the one on the map.
   */
  const lastOutline = computed<AreaOutline | null>(() => {
    const draft = trafficStore.draftArea
    if (draft?.kind !== 'municipalities' || draft.ofsIds.length === 0) return null
    const status = feedback.value.status
    if (status === 'not_contiguous' || status === 'too_many') return null
    return outline.value
  })

  /** Ask the server for the exact counts. Called when the drag stops. */
  function checkNow(): void {
    const circle: AreaSelection | null = trafficStore.draftArea
    if (!circle) return
    if (circle.kind === 'municipalities') {
      // Nothing to ask: no commune, too many, or the index knows they do not touch.
      if (circle.ofsIds.length === 0) {
        outline.value = null
        return
      }
      if (tooMany(circle.ofsIds)) return
      if (communes.value && !contiguous(circle.ofsIds, communes.value)) return
    }
    const key = areaKey(circle)
    if (key === checkedKey && exact.value) return

    if (checkTimer) clearTimeout(checkTimer)
    checkTimer = setTimeout(() => {
      isChecking.value = true
      previewArea(circle)
        .then((answer) => {
          checkedKey = key
          exact.value = answer
          if (answer.outline) outline.value = answer.outline
        })
        .catch((error) => {
          // the local estimate stays on screen, it is enough to keep dragging
          exact.value = null
          if (error instanceof ApiError && error.code === 'no_swiss_graph') {
            unavailable.value = true
          }
          if (error instanceof ApiError && error.code === 'no_municipalities') {
            noMunicipalities.value = true
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

  return {
    feedback,
    canUse,
    isChecking,
    limits,
    communes,
    lastOutline,
    checkNow,
    invalidate,
    stopChecking
  }
}

/** Tests only: forget the shared answer. */
export function resetAreaFeedback(): void {
  density.value = null
  communes.value = null
  exact.value = null
  outline.value = null
  isChecking.value = false
  unavailable.value = false
  noMunicipalities.value = false
  checkedKey = ''
  if (checkTimer) clearTimeout(checkTimer)
  checkTimer = null
}
