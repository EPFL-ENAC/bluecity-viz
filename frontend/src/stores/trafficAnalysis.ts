import type { EdgeModification, ImpactStatistics } from '@/services/trafficAnalysis'
import { rgb } from 'd3-color'
import { scaleDiverging, scaleDivergingSymlog, scaleSequential } from 'd3-scale'
import { interpolateSpectral, interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

type ColorScale = ((value: number) => string) | null
type LegendMode = 'none' | 'frequency' | 'delta' | 'delta_relative' | 'co2' | 'co2_delta' | 'betweenness' | 'betweenness_delta'
export type ModificationAction = 'remove' | 'speed50' | 'speed30' | 'speed10'

// Cycle order for edge modification actions
export const MODIFICATION_CYCLE: (ModificationAction | null)[] = [
  'remove',
  'speed50',
  'speed30',
  'speed10',
  null
]

export interface NodePair {
  origin: number
  destination: number
}

export interface EdgeModificationDisplay {
  u: number
  v: number
  name: string
  action: ModificationAction
  isBidirectional: boolean
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


// Fixed CO₂/km scale — matches the grade-relative model range (g CO₂/km).
// Fallback upper bound used only when all CO2 values are zero.
const CO2_KM_MAX = 350

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
  // Map of edge key -> { action, name }
  const edgeModifications = ref<Map<string, { action: ModificationAction; name: string }>>(
    new Map()
  )
  const nodePairs = shallowRef<NodePair[]>([])
  const originalEdgeUsage = shallowRef<EdgeUsageStats[]>([])
  const newEdgeUsage = shallowRef<EdgeUsageStats[]>([])
  const impactStatistics = ref<ImpactStatistics | null>(null)
  const useCongestionModel = ref<boolean>(false)
  const congestionIterations = ref<number>(1)
  const elasticDemand = ref<boolean>(false)
  const filterBusRoutes = ref<boolean>(false)
  // Visualization state
  const legendMode = ref<LegendMode>('none')
  const colorScale = ref<ColorScale>(null)
  const frequencyColorScale = ref<ColorScale>(null)
  const deltaColorScale = ref<ColorScale>(null)
  const co2ColorScale = ref<ColorScale>(null)
  const co2DeltaColorScale = ref<ColorScale>(null)
  const minValue = ref<number>(0)
  const maxValue = ref<number>(0)
  const frequencyMinValue = ref<number>(0)
  const frequencyMaxValue = ref<number>(0)
  const deltaMinValue = ref<number>(0)
  const deltaMaxValue = ref<number>(0)
  const co2MinValue = ref<number>(0)
  const co2MaxValue = ref<number>(0)
  const co2DeltaMinValue = ref<number>(0)
  const co2DeltaMaxValue = ref<number>(0)
  const bcColorScale = ref<ColorScale>(null)
  const bcDeltaColorScale = ref<ColorScale>(null)
  const bcMinValue = ref<number>(0)
  const bcMaxValue = ref<number>(0)
  const bcDeltaMinValue = ref<number>(0)
  const bcDeltaMaxValue = ref<number>(0)
  const deltaRelativeColorScale = ref<ColorScale>(null)
  const deltaRelativeMinValue = ref<number>(0)
  const deltaRelativeMaxValue = ref<number>(0)
  const activeVisualization = ref<
    'none' | 'frequency' | 'delta' | 'delta_relative' | 'co2' | 'co2_delta' | 'betweenness' | 'betweenness_delta'
  >('none') // User-selected visualization

  // Computed: convert edgeModifications to API format
  const edgeModificationsArray = computed(() => {
    const result: EdgeModification[] = []
    edgeModifications.value.forEach((mod, key) => {
      const [u, v] = key.split('-').map(Number)
      if (mod.action === 'remove') {
        result.push({ u, v, action: 'remove' })
      } else {
        const speed = mod.action === 'speed10' ? 10 : mod.action === 'speed30' ? 30 : 50
        result.push({ u, v, action: 'modify', speed_kph: speed })
      }
    })
    return result
  })

  const edgeModificationsForDisplay = computed(() => {
    const entries = Array.from(edgeModifications.value.entries())
    const displayed = new Set<string>()
    const result: EdgeModificationDisplay[] = []

    entries.forEach(([key, mod]) => {
      if (displayed.has(key)) return

      const [u, v] = key.split('-').map(Number)
      const reverseKey = `${v}-${u}`
      const reverseExists = edgeModifications.value.has(reverseKey)

      result.push({
        u,
        v,
        name: mod.name || `Edge ${u}→${v}`,
        action: mod.action,
        isBidirectional: reverseExists
      })

      displayed.add(key)
      if (reverseExists) displayed.add(reverseKey)
    })

    return result.sort((a, b) => a.name.localeCompare(b.name))
  })

  const edgeModificationsCount = computed(() => {
    const counted = new Set<string>()
    let count = 0
    edgeModifications.value.forEach((_, key) => {
      if (counted.has(key)) return
      const [u, v] = key.split('-')
      counted.add(key)
      counted.add(`${v}-${u}`)
      count++
    })
    return count
  })

  // Helper to get modification for an edge
  function getEdgeModification(u: number, v: number): ModificationAction | null {
    return edgeModifications.value.get(`${u}-${v}`)?.action ?? null
  }

  const hasCalculatedRoutes = computed(() => originalEdgeUsage.value.length > 0)

  // Available visualization modes based on calculated data
  const availableVisualizations = computed(() => {
    const modes: Array<{
      value: 'frequency' | 'delta' | 'delta_relative' | 'co2' | 'co2_delta' | 'betweenness' | 'betweenness_delta'
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

  // Cycle through modification actions: remove → speed10 → speed30 → speed50 → (none)
  function cycleEdgeModification(u: number, v: number, name?: string) {
    const key = `${u}-${v}`
    const current = edgeModifications.value.get(key)
    const currentAction = current?.action ?? null
    const currentIndex = MODIFICATION_CYCLE.indexOf(currentAction)
    const nextAction = MODIFICATION_CYCLE[(currentIndex + 1) % MODIFICATION_CYCLE.length]

    const newMap = new Map(edgeModifications.value)
    if (nextAction === null) {
      newMap.delete(key)
    } else {
      newMap.set(key, { action: nextAction, name: name || current?.name || `Edge ${u}→${v}` })
    }
    edgeModifications.value = newMap
  }

  function removeEdgeModification(u: number, v: number) {
    const newMap = new Map(edgeModifications.value)
    newMap.delete(`${u}-${v}`)
    edgeModifications.value = newMap
  }

  function clearEdgeModifications() {
    edgeModifications.value = new Map()
  }

  function setNodePairs(pairs: NodePair[]) {
    nodePairs.value = pairs
  }

  function setEdgeUsage(
    original: EdgeUsageStats[],
    newUsage: EdgeUsageStats[],
    impact?: ImpactStatistics
  ) {
    originalEdgeUsage.value = original
    newEdgeUsage.value = newUsage
    impactStatistics.value = impact || null

    // Calculate color scale based on usage data
    if (newUsage.length === 0) {
      legendMode.value = 'none'
      colorScale.value = null
      frequencyColorScale.value = null
      deltaColorScale.value = null
      co2ColorScale.value = null
      co2DeltaColorScale.value = null
      return
    }

    // Always calculate frequency scale
    const maxFreq = Math.max(...newUsage.map((d) => d.frequency), 0.01)
    frequencyMinValue.value = 0
    frequencyMaxValue.value = maxFreq
    frequencyColorScale.value = scaleSequential(interpolateViridis).domain([0, maxFreq])

    // Check if we have CO2 data
    const hasCO2 = newUsage.some((stat) => stat.co2_per_km !== undefined && stat.co2_per_km > 0)

    if (hasCO2) {
      const co2Values = newUsage.map((d) => d.co2_per_km ?? 0)
      const co2Min = Math.min(...co2Values.filter((v) => v > 0))
      const co2Max = robustMax(co2Values, 0.98, CO2_KM_MAX)
      co2MinValue.value = co2Min
      co2MaxValue.value = co2Max
      co2ColorScale.value = scaleSequential(interpolateViridis).domain([co2Min, co2Max])
    }

    // Check if we have delta values (recalculated routes)
    const hasDeltaValues = newUsage.some(
      (stat) => stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001
    )

    if (hasDeltaValues) {
      // Calculate delta scale (symmetrical around zero)
      const deltaValues = newUsage.map((d) => d.delta_count ?? 0)
      const absDeltaMax = Math.max(...deltaValues.map(Math.abs), 0.01)
      deltaMinValue.value = -absDeltaMax
      deltaMaxValue.value = absDeltaMax
      deltaColorScale.value = scaleDiverging(interpolateSpectral).domain([
        absDeltaMax,
        0,
        -absDeltaMax
      ])

      // CO2 delta: fixed ±6 domain prevents sub-g/km changes from saturating the scale
      if (hasCO2) {
        const CO2_DELTA_CLAMP = 6
        co2DeltaMinValue.value = -CO2_DELTA_CLAMP
        co2DeltaMaxValue.value = CO2_DELTA_CLAMP
        co2DeltaColorScale.value = scaleDiverging(interpolateSpectral).domain([
          CO2_DELTA_CLAMP,
          0,
          -CO2_DELTA_CLAMP
        ])
      }

      // Delta relative: (delta_frequency / original_frequency) * 100
      const relValues = newUsage.map((d) => {
        const origFreq = (d.frequency ?? 0) - (d.delta_frequency ?? 0)
        return origFreq > 0.0001 ? ((d.delta_frequency ?? 0) / origFreq) * 100 : 0
      })
      // Symlog scale: linear within ±10%, logarithmic beyond — compresses outliers
      // (e.g. +3000%) without hard-capping, keeping small changes visible
      const absRelMax = Math.max(...relValues.map(Math.abs), 0.01)
      deltaRelativeMinValue.value = -absRelMax
      deltaRelativeMaxValue.value = absRelMax
      const relScale = (scaleDivergingSymlog() as any).constant(10).domain([absRelMax, 0, -absRelMax])
      deltaRelativeColorScale.value = (v: number) => interpolateSpectral(relScale(v))

      // Auto-select delta visualization when available
      activeVisualization.value = 'delta'
    } else {
      // Auto-select frequency visualization
      activeVisualization.value = 'frequency'
    }

    // Calculate betweenness centrality scale
    const hasBetweenness = newUsage.some(
      (stat) => stat.betweenness_centrality !== undefined && stat.betweenness_centrality > 0
    )
    if (hasBetweenness) {
      const bcValues = newUsage.map((d) => d.betweenness_centrality ?? 0)
      const maxBC = Math.max(...bcValues, 0.01)
      bcMinValue.value = 0
      bcMaxValue.value = maxBC
      bcColorScale.value = scaleSequential(interpolateViridis).domain([0, maxBC])
    }

    const hasBCDelta = newUsage.some(
      (stat) => stat.delta_betweenness != null && stat.delta_betweenness !== 0
    )
    if (hasBCDelta) {
      const bcDeltas = newUsage.map((d) => d.delta_betweenness ?? 0)
      const absBCDeltaMax = Math.max(...bcDeltas.map(Math.abs), 0.01)
      bcDeltaMinValue.value = -absBCDeltaMax
      bcDeltaMaxValue.value = absBCDeltaMax
      bcDeltaColorScale.value = scaleDiverging(interpolateSpectral).domain([
        absBCDeltaMax,
        0,
        -absBCDeltaMax
      ])
    }

    // Update active color scale based on selection
    updateActiveColorScale()
  }

  function clearResults() {
    originalEdgeUsage.value = []
    newEdgeUsage.value = []
    impactStatistics.value = null
    legendMode.value = 'none'
    colorScale.value = null
    frequencyColorScale.value = null
    deltaColorScale.value = null
    co2ColorScale.value = null
    co2DeltaColorScale.value = null
    deltaRelativeColorScale.value = null
    deltaRelativeMinValue.value = 0
    deltaRelativeMaxValue.value = 0
    minValue.value = 0
    maxValue.value = 0
    frequencyMinValue.value = 0
    frequencyMaxValue.value = 0
    deltaMinValue.value = 0
    deltaMaxValue.value = 0
    co2MinValue.value = 0
    co2MaxValue.value = 0
    co2DeltaMinValue.value = 0
    co2DeltaMaxValue.value = 0
    bcColorScale.value = null
    bcDeltaColorScale.value = null
    bcMinValue.value = 0
    bcMaxValue.value = 0
    bcDeltaMinValue.value = 0
    bcDeltaMaxValue.value = 0
    activeVisualization.value = 'none'
    filterBusRoutes.value = false
  }

  function getColor(value: number): [number, number, number] {
    if (!colorScale.value) return [136, 136, 136] // Gray fallback
    const colorStr = colorScale.value(value)
    const color = rgb(colorStr)
    return [color.r, color.g, color.b]
  }

  function updateActiveColorScale() {
    if (activeVisualization.value === 'frequency' && frequencyColorScale.value) {
      colorScale.value = frequencyColorScale.value
      minValue.value = frequencyMinValue.value
      maxValue.value = frequencyMaxValue.value
      legendMode.value = 'frequency'
    } else if (activeVisualization.value === 'delta' && deltaColorScale.value) {
      colorScale.value = deltaColorScale.value
      minValue.value = deltaMinValue.value
      maxValue.value = deltaMaxValue.value
      legendMode.value = 'delta'
    } else if (activeVisualization.value === 'delta_relative' && deltaRelativeColorScale.value) {
      colorScale.value = deltaRelativeColorScale.value
      minValue.value = deltaRelativeMinValue.value
      maxValue.value = deltaRelativeMaxValue.value
      legendMode.value = 'delta_relative'
    } else if (activeVisualization.value === 'co2' && co2ColorScale.value) {
      colorScale.value = co2ColorScale.value
      minValue.value = co2MinValue.value
      maxValue.value = co2MaxValue.value
      legendMode.value = 'co2'
    } else if (activeVisualization.value === 'co2_delta' && co2DeltaColorScale.value) {
      colorScale.value = co2DeltaColorScale.value
      minValue.value = co2DeltaMinValue.value
      maxValue.value = co2DeltaMaxValue.value
      legendMode.value = 'co2_delta'
    } else if (activeVisualization.value === 'betweenness' && bcColorScale.value) {
      colorScale.value = bcColorScale.value
      minValue.value = bcMinValue.value
      maxValue.value = bcMaxValue.value
      legendMode.value = 'betweenness'
    } else if (activeVisualization.value === 'betweenness_delta' && bcDeltaColorScale.value) {
      colorScale.value = bcDeltaColorScale.value
      minValue.value = bcDeltaMinValue.value
      maxValue.value = bcDeltaMaxValue.value
      legendMode.value = 'betweenness_delta'
    } else {
      colorScale.value = null
      minValue.value = 0
      maxValue.value = 0
      legendMode.value = 'none'
    }
  }

  function setActiveVisualization(
    mode: 'none' | 'frequency' | 'delta' | 'delta_relative' | 'co2' | 'co2_delta' | 'betweenness' | 'betweenness_delta'
  ) {
    activeVisualization.value = mode
    updateActiveColorScale()
  }

  // Batch restore function for investigation switching (avoids multiple reactive updates)
  function restoreState(state: {
    isOpen: boolean
    edgeModifications: Array<{ u: number; v: number; action: string; name?: string }>
    nodePairs: Array<{ origin: number; destination: number }>
    originalEdgeUsage: EdgeUsageStats[]
    newEdgeUsage: EdgeUsageStats[]
    impactStatistics: any | null
    activeVisualization: 'none' | 'frequency' | 'delta' | 'delta_relative' | 'co2' | 'co2_delta' | 'betweenness' | 'betweenness_delta'
  }) {
    isRestoring.value = true
    isOpen.value = state.isOpen

    // Restore edge modifications
    const modMap = new Map<string, { action: ModificationAction; name: string }>()
    ;(state.edgeModifications ?? []).forEach(
      (edge: { u: number; v: number; action: string; name?: string }) => {
        const key = `${edge.u}-${edge.v}`
        modMap.set(key, {
          action: (edge.action as ModificationAction) || 'remove',
          name: edge.name || `Edge ${edge.u}→${edge.v}`
        })
      }
    )
    edgeModifications.value = modMap

    nodePairs.value = state.nodePairs

    if (state.newEdgeUsage.length > 0) {
      setEdgeUsage(state.originalEdgeUsage, state.newEdgeUsage, state.impactStatistics || undefined)
      activeVisualization.value = state.activeVisualization
      updateActiveColorScale()
    } else {
      originalEdgeUsage.value = state.originalEdgeUsage
      newEdgeUsage.value = state.newEdgeUsage
      impactStatistics.value = state.impactStatistics
      activeVisualization.value = state.activeVisualization
    }

    isRestoring.value = false
  }

  return {
    // State
    isOpen,
    isLoading,
    isCalculating,
    isRestoring,
    edgeModifications,
    nodePairs,
    originalEdgeUsage,
    newEdgeUsage,
    impactStatistics,
    useCongestionModel,
    congestionIterations,
    elasticDemand,
    filterBusRoutes,

    // Visualization state
    legendMode,
    colorScale,
    minValue,
    maxValue,
    activeVisualization,

    // Computed
    edgeModificationsArray,
    edgeModificationsForDisplay,
    edgeModificationsCount,
    hasCalculatedRoutes,
    availableVisualizations,

    // Actions
    togglePanel,
    openPanel,
    closePanel,
    cycleEdgeModification,
    removeEdgeModification,
    clearEdgeModifications,
    getEdgeModification,
    setNodePairs,
    setEdgeUsage,
    clearResults,
    getColor,
    setActiveVisualization,
    restoreState
  }
})
