import { streetTotals, type StreetTotals } from '@/composables/useResultStates'
import {
  ApiError,
  areaKey,
  createArea,
  DEFAULT_AREA_ID,
  fetchAreaLimits,
  fetchBaseline,
  fetchGraphInfo,
  type AreaInfo,
  type AreaLimits,
  type AreaSelection,
  type ImpactStatistics
} from '@/services/trafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { rgb } from 'd3-color'
import { scaleDiverging, scaleDivergingSymlog, scaleSequential } from 'd3-scale'
import { interpolateSpectral, interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { computed, markRaw, ref, shallowRef } from 'vue'

// Where the picker opens when the scenario has no area yet, and how big the
// circle starts. The map centre wins when the caller knows it.
const DEFAULT_CENTRE = { lon: 6.6323, lat: 46.5197 }
const DEFAULT_RADIUS_M = 3000

type ColorScale = ((value: number) => string) | null
type LegendMode =
  | 'none'
  | 'frequency'
  | 'delta'
  | 'delta_relative'
  | 'co2'
  | 'co2_delta'
  | 'betweenness'
  | 'betweenness_delta'

/** The visualization modes, 'none' included. */
export type VisualizationMode = LegendMode
/** The modes that have a color scale. */
type ScaledMode = Exclude<VisualizationMode, 'none'>

export interface NodePair {
  origin: number
  destination: number
}

export interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  delta_frequency?: number
  co2_per_km?: number
  betweenness_centrality?: number
  delta_betweenness?: number
}

/** What getBaseline gives back: the rows and the count the server really used. */
export interface BaselineResult {
  odPairs: number
  rows: EdgeUsageStats[]
}

/** A color scale with the range it covers. */
interface ModeScale {
  scale: (value: number) => string
  min: number
  max: number
}

type ModeScales = Record<ScaledMode, ModeScale | null>

function emptyScales(): ModeScales {
  return {
    frequency: null,
    delta: null,
    delta_relative: null,
    co2: null,
    co2_delta: null,
    betweenness: null,
    betweenness_delta: null
  }
}

// Fixed CO₂/km scale — matches the grade-relative model range (g CO₂/km).
// Fallback upper bound used only when all CO2 values are zero.
const CO2_KM_MAX = 350

// CO2 delta: fixed ±6 domain prevents sub-g/km changes from saturating the scale
const CO2_DELTA_CLAMP = 6

/** 98th-percentile max — prevents a few outlier edges (zero-length stubs, roundabout loops)
 *  with astronomical CO2/km from blowing up the color scale. */
function robustMax(values: number[], percentile = 0.98, fallback = 1): number {
  const pos = values.filter((v) => v > 0)
  if (pos.length === 0) return fallback
  const sorted = [...pos].sort((a, b) => a - b)
  const idx = Math.min(Math.floor(sorted.length * percentile), sorted.length - 1)
  return sorted[idx]
}

export const useTrafficAnalysisStore = defineStore('trafficAnalysis', () => {
  // State
  const isOpen = ref(false)
  const isLoading = ref(false)
  const isCalculating = ref(false)
  const isRestoring = ref(false)
  const nodePairs = shallowRef<NodePair[]>([])
  const originalEdgeUsage = shallowRef<EdgeUsageStats[]>([])
  const newEdgeUsage = shallowRef<EdgeUsageStats[]>([])
  // shallow: nothing reads a single field reactively, and setEdgeUsage always
  // replaces the whole object
  const impactStatistics = shallowRef<ImpactStatistics | null>(null)
  const useCongestionModel = ref<boolean>(false)
  const congestionIterations = ref<number>(1)
  const elasticDemand = ref<boolean>(false)
  const filterBusRoutes = ref<boolean>(false)
  // How many OD pairs to route. null means the server default.
  const odPairs = ref<number | null>(null)

  // The area the workbench runs on. null means the default city, which is
  // what every investigation saved before this feature has.
  const area = ref<AreaSelection | null>(null)
  // Derived, never persisted: what the server told us about that area.
  const areaId = ref<string | null>(null)
  const areaInfo = shallowRef<AreaInfo | null>(null)
  const isBuildingArea = ref(false)
  const areaError = shallowRef<{ code?: string; message: string } | null>(null)

  /**
   * The name of the network the map has to show.
   *
   * The circle says it, not the server: the id the server mints for a circle
   * is this same string, so the two can never disagree. `areaId` answers
   * another question, "has the server built it", and is null until it has.
   */
  const graphKey = computed(() => areaKey(area.value))

  // The picker. UI only, nothing here is saved: the circle being dragged, and
  // the rules the server applies to it.
  const pickMode = ref(false)
  const draftArea = ref<AreaSelection | null>(null)
  const areaLimits = shallowRef<AreaLimits | null>(null)

  // Filled once from /graph-info: the server default, the most it accepts, and
  // the count the "full" choice sends (the set really sampled at startup).
  const odPairsDefault = ref<number | null>(null)
  const odPairsMax = ref<number | null>(null)
  const odPairsFull = ref<number | null>(null)

  // The count that produced the results on screen.
  const resultOdPairs = ref<number | null>(null)

  // The baseline never changes while the server runs, so one fetch per count is
  // enough. Not reactive, nothing renders from it. Inside the setup so a fresh
  // pinia (the tests, a reload) starts with an empty cache.
  const baselineCache = new Map<string, EdgeUsageStats[]>()
  const baselinePending = new Map<string, Promise<BaselineResult>>()
  const graphInfoPromises = new Map<string, Promise<void>>()
  let areaPromise: Promise<string | null> | null = null

  // Visualization state. Only the active scale is reactive; the per-mode scales
  // live in a plain object because switching mode only reads one of them.
  const legendMode = ref<LegendMode>('none')
  const colorScale = ref<ColorScale>(null)
  const minValue = ref<number>(0)
  const maxValue = ref<number>(0)
  const activeVisualization = ref<VisualizationMode>('none') // User-selected visualization

  let scales: ModeScales = emptyScales()

  // getColor is called once per edge on every recolor, so the d3 scale output
  // (a css string) is parsed once per distinct color, not once per edge.
  // The returned arrays are shared, callers must not change them.
  let colorCacheScale: ColorScale = null
  let colorCache = new Map<string, [number, number, number]>()

  // The scenario the results on screen were computed with. A result is stale
  // when the scenario moved since, and the tool says so instead of quietly
  // answering an old question.
  const resultScenarioHash = ref<string | null>(null)

  const hasCalculatedRoutes = computed(() => originalEdgeUsage.value.length > 0)

  /**
   * The result per street, both directions summed. The map colours from it and
   * the dock lists from it, so the sum runs once per result, not once per view.
   */
  const resultTotals = computed<StreetTotals[]>(() => {
    const streets = useScenarioStore().streets
    if (newEdgeUsage.value.length === 0 || streets.size === 0) return []
    return streetTotals(newEdgeUsage.value, streets)
  })

  /**
   * True when the graph was edited after this result was computed. The result
   * stays on the map, faded, until it is run again.
   */
  const isStale = computed(() => {
    if (!hasCalculatedRoutes.value) return false
    const scenario = useScenarioStore()
    return resultScenarioHash.value !== scenario.hash
  })

  // Available visualization modes based on calculated data
  const availableVisualizations = computed(() => {
    const modes: Array<{
      value: Exclude<VisualizationMode, 'none'>
      label: string
    }> = []
    if (hasCalculatedRoutes.value) {
      modes.push({ value: 'frequency', label: 'Edge Usage Frequency' })
    }
    const hasCO2 = newEdgeUsage.value.some(
      (stat) => stat.co2_per_km !== undefined && stat.co2_per_km > 0
    )
    if (hasCO2 && hasCalculatedRoutes.value) {
      modes.push({ value: 'co2', label: 'CO₂ Emissions' })
    }
    const hasDelta = newEdgeUsage.value.some(
      (stat) => stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001
    )
    if (hasDelta) {
      modes.push({ value: 'delta', label: 'Traffic Change (Delta)' })
      modes.push({ value: 'delta_relative', label: 'Traffic Change (Delta) Relative %' })
    }
    if (hasDelta && hasCO2) {
      modes.push({ value: 'co2_delta', label: 'CO₂ Emissions Change' })
    }
    const hasBetweenness = newEdgeUsage.value.some(
      (stat) => stat.betweenness_centrality !== undefined && stat.betweenness_centrality > 0
    )
    if (hasBetweenness && hasCalculatedRoutes.value) {
      modes.push({ value: 'betweenness', label: 'Betweenness Centrality' })
    }
    const hasBCDelta = newEdgeUsage.value.some(
      (stat) => stat.delta_betweenness != null && stat.delta_betweenness !== 0
    )
    if (hasBCDelta) {
      modes.push({ value: 'betweenness_delta', label: 'Betweenness Centrality Change' })
    }
    return modes
  })

  // Actions
  function togglePanel() {
    isOpen.value = !isOpen.value
  }

  function openPanel() {
    isOpen.value = true
  }

  function closePanel() {
    isOpen.value = false
  }

  function setNodePairs(pairs: NodePair[]) {
    nodePairs.value = pairs
  }

  /**
   * Build every color scale from the new usage stats.
   *
   * One pass over the edges collects the min, the max and the flags all seven
   * modes need. The old code walked the array about ten times and used
   * Math.max(...values), which spreads 10k arguments onto the stack.
   */
  function buildScales(usage: EdgeUsageStats[]): ModeScales {
    const built = emptyScales()
    if (usage.length === 0) return built

    let maxFreq = 0.01
    let absDeltaMax = 0.01
    let absRelMax = 0.01
    let maxBC = 0.01
    let absBCDeltaMax = 0.01
    let co2Min = Infinity
    const co2Values: number[] = []
    let hasCO2 = false
    let hasDeltaValues = false
    let hasBetweenness = false
    let hasBCDelta = false

    for (const stat of usage) {
      const frequency = stat.frequency
      if (frequency > maxFreq) maxFreq = frequency

      const co2 = stat.co2_per_km ?? 0
      co2Values.push(co2)
      if (stat.co2_per_km !== undefined && stat.co2_per_km > 0) {
        hasCO2 = true
        if (co2 < co2Min) co2Min = co2
      }

      const deltaCount = stat.delta_count ?? 0
      if (stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001) {
        hasDeltaValues = true
      }
      const absDelta = Math.abs(deltaCount)
      if (absDelta > absDeltaMax) absDeltaMax = absDelta

      const deltaFrequency = stat.delta_frequency ?? 0
      const origFreq = (stat.frequency ?? 0) - deltaFrequency
      const rel = origFreq > 0.0001 ? (deltaFrequency / origFreq) * 100 : 0
      const absRel = Math.abs(rel)
      if (absRel > absRelMax) absRelMax = absRel

      const bc = stat.betweenness_centrality ?? 0
      if (stat.betweenness_centrality !== undefined && stat.betweenness_centrality > 0) {
        hasBetweenness = true
      }
      if (bc > maxBC) maxBC = bc

      const bcDelta = stat.delta_betweenness ?? 0
      if (stat.delta_betweenness != null && stat.delta_betweenness !== 0) {
        hasBCDelta = true
      }
      const absBCDelta = Math.abs(bcDelta)
      if (absBCDelta > absBCDeltaMax) absBCDeltaMax = absBCDelta
    }

    // Frequency is always available once there are routes
    built.frequency = {
      scale: scaleSequential(interpolateViridis).domain([0, maxFreq]),
      min: 0,
      max: maxFreq
    }

    if (hasCO2) {
      const co2Max = robustMax(co2Values, 0.98, CO2_KM_MAX)
      built.co2 = {
        scale: scaleSequential(interpolateViridis).domain([co2Min, co2Max]),
        min: co2Min,
        max: co2Max
      }
    }

    if (hasDeltaValues) {
      // symmetrical around zero, so a gain and a loss of the same size read the same
      built.delta = {
        scale: scaleDiverging(interpolateSpectral).domain([absDeltaMax, 0, -absDeltaMax]),
        min: -absDeltaMax,
        max: absDeltaMax
      }

      if (hasCO2) {
        built.co2_delta = {
          scale: scaleDiverging(interpolateSpectral).domain([CO2_DELTA_CLAMP, 0, -CO2_DELTA_CLAMP]),
          min: -CO2_DELTA_CLAMP,
          max: CO2_DELTA_CLAMP
        }
      }

      // Symlog scale: linear within ±10%, logarithmic beyond — compresses outliers
      // (e.g. +3000%) without hard-capping, keeping small changes visible
      const relScale = (scaleDivergingSymlog() as any)
        .constant(10)
        .domain([absRelMax, 0, -absRelMax])
      built.delta_relative = {
        scale: (v: number) => interpolateSpectral(relScale(v)),
        min: -absRelMax,
        max: absRelMax
      }
    }

    if (hasBetweenness) {
      built.betweenness = {
        scale: scaleSequential(interpolateViridis).domain([0, maxBC]),
        min: 0,
        max: maxBC
      }
    }

    if (hasBCDelta) {
      built.betweenness_delta = {
        scale: scaleDiverging(interpolateSpectral).domain([absBCDeltaMax, 0, -absBCDeltaMax]),
        min: -absBCDeltaMax,
        max: absBCDeltaMax
      }
    }

    return built
  }

  function setEdgeUsage(
    original: EdgeUsageStats[],
    newUsage: EdgeUsageStats[],
    impact?: ImpactStatistics,
    usedOdPairs?: number | null,
    scenarioHash?: string | null
  ) {
    originalEdgeUsage.value = original
    newEdgeUsage.value = newUsage
    impactStatistics.value = impact ? markRaw(impact) : null
    resultOdPairs.value = usedOdPairs ?? null
    if (scenarioHash !== undefined) resultScenarioHash.value = scenarioHash

    scales = buildScales(newUsage)

    if (newUsage.length === 0) {
      updateActiveColorScale()
      return
    }

    // Delta is the interesting view when the routes moved, otherwise frequency
    activeVisualization.value = scales.delta ? 'delta' : 'frequency'

    // A fresh result is what the user asked for, so light the tool zone.
    if (useScenarioStore().activeTab === 'routing') useScenarioStore().mapMode = 'result'

    updateActiveColorScale()
  }

  function clearResults() {
    originalEdgeUsage.value = []
    newEdgeUsage.value = []
    impactStatistics.value = null
    resultOdPairs.value = null
    scales = emptyScales()
    activeVisualization.value = 'none'
    filterBusRoutes.value = false
    resultScenarioHash.value = null
    // Nothing left to read in colour, back to the scenario. Only if the user
    // is looking at this tab, the other tool may still have a result up.
    if (useScenarioStore().activeTab === 'routing') useScenarioStore().mapMode = 'scenario'
    updateActiveColorScale()
  }

  /**
   * Change the OD pair count. Results computed at another count are dropped, so
   * two sizes are never compared on screen.
   *
   * A function and not a watch on odPairs: restoreState sets the count and the
   * results of an investigation in the same tick, and a watcher would run after
   * that and wipe what we just restored.
   */
  function setOdPairs(count: number | null) {
    if (count === odPairs.value) return
    if (hasCalculatedRoutes.value) clearResults()
    odPairs.value = count
  }

  /** Read the OD pair counts of an area from the server, once per area. */
  function loadGraphInfo(): Promise<void> {
    const key = areaId.value ?? DEFAULT_AREA_ID
    let request = graphInfoPromises.get(key)
    if (!request) {
      request = fetchGraphInfo(areaId.value)
        .then((info) => {
          odPairsDefault.value = info.od_pairs_default
          odPairsMax.value = info.od_pairs_max
          // The server clamps to the set it really sampled, so asking for more
          // than that would show one number and give back another.
          odPairsFull.value = Math.min(info.od_pairs_max, info.od_pairs)
        })
        .catch((error) => {
          // let a later call try again
          graphInfoPromises.delete(key)
          throw error
        })
      graphInfoPromises.set(key, request)
    }
    return request
  }

  /**
   * The free-flow usage for a pair count, from the cache or from the server.
   * Keyed by the count the server used, which is what the results carry.
   */
  function getBaseline(count?: number): Promise<BaselineResult> {
    // Every key carries the area: two areas have different numbers for the
    // same pair count.
    const scope = areaId.value ?? DEFAULT_AREA_ID
    if (count !== undefined) {
      const cached = baselineCache.get(`${scope}:${count}`)
      if (cached) return Promise.resolve({ odPairs: count, rows: cached })
    }

    const key = `${scope}:${count ?? 'default'}`
    const inFlight = baselinePending.get(key)
    if (inFlight) return inFlight

    const request = fetchBaseline(count, areaId.value)
      .then((response) => {
        baselineCache.set(`${scope}:${response.od_pairs}`, response.edge_usage)
        baselinePending.delete(key)
        return { odPairs: response.od_pairs, rows: response.edge_usage }
      })
      .catch((error) => {
        // a failed fetch must not stick, the next Calculate tries again
        baselinePending.delete(key)
        throw error
      })

    baselinePending.set(key, request)
    return request
  }

  /** Forget everything cached for one area. */
  function forgetArea(scope: string) {
    for (const key of [...baselineCache.keys()]) {
      if (key.startsWith(`${scope}:`)) baselineCache.delete(key)
    }
    for (const key of [...baselinePending.keys()]) {
      if (key.startsWith(`${scope}:`)) baselinePending.delete(key)
    }
    graphInfoPromises.delete(scope)
  }

  /**
   * Change the area the workbench runs on.
   *
   * The scenario goes with it: a street key names streets of the old graph and
   * means nothing in another area. Both results go too. The stores are read
   * here and not at the top of the file, they need each other.
   */
  function setArea(selection: AreaSelection | null) {
    if (areaKey(selection) === areaKey(area.value)) {
      // Same circle: nothing to rebuild, but the picker may have found a name
      // for an area saved before we had one.
      if (selection && area.value && selection.name !== area.value.name) {
        area.value = { ...area.value, name: selection.name }
      }
      return
    }

    forgetArea(areaId.value ?? DEFAULT_AREA_ID)
    area.value = selection
    areaId.value = null
    areaInfo.value = null
    areaError.value = null
    areaPromise = null
    clearResults()

    const scenario = useScenarioStore()
    scenario.clear()
    scenario.select(null)
    scenario.hover(null)
    scenario.setStreets(new Map())
    // The waste routes are on the old streets too, and only the default city
    // has the waste data, so a drawn area shows the routing tab alone.
    useCVRPStore().clearResult()
    if (selection) scenario.activeTab = 'routing'
  }

  /**
   * Make sure the server has this area, and give back its id.
   *
   * Always a create: the server answers from its own cache when it still has
   * the circle, so an area saved yesterday costs one round trip either way,
   * and the id is minted in one place instead of two.
   */
  function ensureArea(): Promise<string | null> {
    if (!area.value) return Promise.resolve(null)
    if (areaId.value) return Promise.resolve(areaId.value)
    if (areaPromise) return areaPromise

    const selection = area.value
    const wanted = areaKey(selection)

    areaError.value = null
    isBuildingArea.value = true
    const request = createArea(selection)
      .then((info) => {
        // the user may have moved the circle while we were building
        if (areaKey(area.value) !== wanted) return areaId.value
        areaId.value = info.id
        areaInfo.value = info
        return info.id
      })
      .catch((error: unknown) => {
        const failure =
          error instanceof ApiError
            ? { code: error.code, message: error.message }
            : { message: String(error) }
        areaError.value = failure
        areaPromise = null
        throw error
      })
      .finally(() => {
        isBuildingArea.value = false
      })

    areaPromise = request
    return request
  }

  /** Open the picker on the current circle, or on a fresh one. */
  function enterPickMode(fallback?: { lon: number; lat: number }) {
    draftArea.value = area.value
      ? { ...area.value }
      : {
          kind: 'circle',
          lon: fallback?.lon ?? DEFAULT_CENTRE.lon,
          lat: fallback?.lat ?? DEFAULT_CENTRE.lat,
          radiusM: DEFAULT_RADIUS_M
        }
    pickMode.value = true
  }

  /** Close the picker. Confirming makes the draft the area of the scenario. */
  function exitPickMode(confirm: boolean) {
    if (confirm && draftArea.value) setArea({ ...draftArea.value })
    pickMode.value = false
    draftArea.value = null
  }

  /** Back to the city the server loaded at startup. */
  function useDefaultArea() {
    setArea(null)
    pickMode.value = false
    draftArea.value = null
  }

  function moveDraft(lon: number, lat: number) {
    if (draftArea.value) draftArea.value = { ...draftArea.value, lon, lat }
  }

  function setDraftRadius(radiusM: number) {
    if (draftArea.value) draftArea.value = { ...draftArea.value, radiusM }
  }

  /** The place the draft circle sits on, read from the basemap by the picker. */
  function setDraftName(name: string | null) {
    if (!draftArea.value) return
    if ((draftArea.value.name ?? null) === name) return
    const next = { ...draftArea.value }
    if (name) next.name = name
    else delete next.name
    draftArea.value = next
  }

  /** The rules the picker checks, read once from the server. */
  function loadAreaLimits(): Promise<AreaLimits | null> {
    if (areaLimits.value) return Promise.resolve(areaLimits.value)
    return fetchAreaLimits()
      .then((limits) => {
        areaLimits.value = limits
        return limits
      })
      .catch(() => null)
  }

  /** The area is gone from the server: build it again on the next call. */
  function forgetAreaId() {
    forgetArea(areaId.value ?? DEFAULT_AREA_ID)
    areaId.value = null
    areaPromise = null
  }

  function getColor(value: number): [number, number, number] {
    const scale = colorScale.value
    if (!scale) return [136, 136, 136] // Gray fallback

    if (scale !== colorCacheScale) {
      colorCacheScale = scale
      colorCache = new Map()
    }

    const colorStr = scale(value)
    let parsed = colorCache.get(colorStr)
    if (!parsed) {
      const color = rgb(colorStr)
      parsed = [color.r, color.g, color.b]
      colorCache.set(colorStr, parsed)
    }
    return parsed
  }

  function updateActiveColorScale() {
    const mode = activeVisualization.value
    const active = mode === 'none' ? null : scales[mode]

    if (active) {
      colorScale.value = active.scale
      minValue.value = active.min
      maxValue.value = active.max
      legendMode.value = mode
    } else {
      colorScale.value = null
      minValue.value = 0
      maxValue.value = 0
      legendMode.value = 'none'
    }
  }

  function setActiveVisualization(mode: VisualizationMode) {
    activeVisualization.value = mode
    updateActiveColorScale()
  }

  // Batch restore function for investigation switching (avoids multiple reactive updates)
  function restoreState(state: {
    isOpen: boolean
    nodePairs?: Array<{ origin: number; destination: number }>
    originalEdgeUsage?: EdgeUsageStats[]
    newEdgeUsage?: EdgeUsageStats[]
    impactStatistics?: ImpactStatistics | null
    activeVisualization: VisualizationMode
    useCongestionModel?: boolean
    congestionIterations?: number
    elasticDemand?: boolean
    filterBusRoutes?: boolean
    odPairs?: number | null
    resultOdPairs?: number | null
    area?: AreaSelection | null
    resultScenarioHash?: string | null
  }) {
    isRestoring.value = true
    isOpen.value = state.isOpen
    resultScenarioHash.value = state.resultScenarioHash ?? null

    // The area comes first: the scenario and the results below belong to it.
    // setArea would clear them, so we assign instead.
    if (state.area !== undefined) {
      const next = state.area ?? null
      if (areaKey(next) !== areaKey(area.value)) {
        forgetArea(areaId.value ?? DEFAULT_AREA_ID)
        area.value = next
        areaId.value = null
        areaInfo.value = null
        areaError.value = null
        areaPromise = null
      }
    }

    nodePairs.value = state.nodePairs ?? []

    // The routing options are part of the scenario, restore them when they are
    // in the saved state so a caller does not have to set them itself.
    if (state.useCongestionModel !== undefined) useCongestionModel.value = state.useCongestionModel
    if (state.congestionIterations !== undefined)
      congestionIterations.value = state.congestionIterations
    if (state.elasticDemand !== undefined) elasticDemand.value = state.elasticDemand
    if (state.filterBusRoutes !== undefined) filterBusRoutes.value = state.filterBusRoutes
    // assigned, not setOdPairs: the results below belong to this state and
    // setOdPairs would clear them.
    if (state.odPairs !== undefined) odPairs.value = state.odPairs

    const original = state.originalEdgeUsage ?? []
    const restored = state.newEdgeUsage ?? []
    const impact = state.impactStatistics ?? null

    if (restored.length > 0) {
      setEdgeUsage(original, restored, impact ?? undefined, state.resultOdPairs ?? null)
      // setEdgeUsage picks a mode on its own, the saved one wins
      activeVisualization.value = state.activeVisualization
      updateActiveColorScale()
    } else {
      originalEdgeUsage.value = original
      newEdgeUsage.value = restored
      impactStatistics.value = impact ? markRaw(impact) : null
      resultOdPairs.value = null
      scales = emptyScales()
      activeVisualization.value = state.activeVisualization
      updateActiveColorScale()
    }

    isRestoring.value = false
  }

  return {
    // State
    isOpen,
    isLoading,
    isCalculating,
    isRestoring,
    nodePairs,
    originalEdgeUsage,
    newEdgeUsage,
    impactStatistics,
    useCongestionModel,
    congestionIterations,
    elasticDemand,
    filterBusRoutes,
    odPairs,
    odPairsDefault,
    odPairsMax,
    odPairsFull,
    resultOdPairs,
    area,
    areaId,
    areaInfo,
    graphKey,
    isBuildingArea,
    areaError,
    pickMode,
    draftArea,
    areaLimits,

    // Visualization state
    legendMode,
    colorScale,
    minValue,
    maxValue,
    activeVisualization,

    // Computed
    hasCalculatedRoutes,
    resultTotals,
    resultScenarioHash,
    isStale,
    availableVisualizations,

    // Actions
    togglePanel,
    openPanel,
    closePanel,
    setNodePairs,
    setOdPairs,
    loadGraphInfo,
    getBaseline,
    setArea,
    ensureArea,
    forgetAreaId,
    enterPickMode,
    exitPickMode,
    useDefaultArea,
    moveDraft,
    setDraftRadius,
    setDraftName,
    loadAreaLimits,
    setEdgeUsage,
    clearResults,
    getColor,
    setActiveVisualization,
    restoreState
  }
})
