import type { EdgeGeometry, ImpactStatistics } from '@/services/trafficAnalysis'
import { rgb } from 'd3-color'
import { scaleDiverging, scaleSequential } from 'd3-scale'
import { interpolateRdBu, interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

type ColorScale = ((value: number) => string) | null
type LegendMode = 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta'

export interface NodePair {
  origin: number
  destination: number
}

export interface RemovedEdgeDisplay {
  u: number
  v: number
  name: string
  isBidirectional: boolean
}

export interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  co2_per_use?: number
}

export const useTrafficAnalysisStore = defineStore('trafficAnalysis', () => {
  // State
  const isOpen = ref(false)
  const isLoading = ref(false)
  const isCalculating = ref(false)
  const removedEdges = ref<Set<string>>(new Set())
  const edgeGeometries = ref<EdgeGeometry[]>([])
  const nodePairs = ref<NodePair[]>([])
  const originalEdgeUsage = ref<EdgeUsageStats[]>([])
  const newEdgeUsage = ref<EdgeUsageStats[]>([])
  const impactStatistics = ref<ImpactStatistics | null>(null)

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
  const activeVisualization = ref<'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta'>('none') // User-selected visualization

  // Computed
  const removedEdgesArray = computed(() => {
    return Array.from(removedEdges.value).map((key) => {
      const [u, v] = key.split('-').map(Number)
      return { u, v }
    })
  })

  const removedEdgesForDisplay = computed(() => {
    const edges = Array.from(removedEdges.value)
    const displayed = new Set<string>()
    const result: RemovedEdgeDisplay[] = []

    edges.forEach((key) => {
      const [u, v] = key.split('-').map(Number)
      const reverseKey = `${v}-${u}`

      // Skip if we've already processed the reverse edge
      if (displayed.has(key)) return

      // Find edge info
      const edge = edgeGeometries.value.find((e) => e.u === u && e.v === v)
      const reverseEdge = edges.includes(reverseKey)

      const name = edge?.name || `Edge ${u}→${v}`

      result.push({
        u,
        v,
        name,
        isBidirectional: reverseEdge
      })

      // Mark both directions as displayed
      displayed.add(key)
      if (reverseEdge) {
        displayed.add(reverseKey)
      }
    })

    return result.sort((a, b) => a.name.localeCompare(b.name))
  })

  const removedEdgesCount = computed(() => {
    // Count unique bidirectional edges (count u-v and v-u as one)
    const edges = Array.from(removedEdges.value)
    const counted = new Set<string>()
    let count = 0

    edges.forEach((key) => {
      if (counted.has(key)) return
      const [u, v] = key.split('-')
      const reverseKey = `${v}-${u}`
      counted.add(key)
      counted.add(reverseKey)
      count++
    })

    return count
  })

  const hasCalculatedRoutes = computed(() => originalEdgeUsage.value.length > 0)

  // Available visualization modes based on calculated data
  const availableVisualizations = computed(() => {
    const modes: Array<{ value: 'frequency' | 'delta' | 'co2' | 'co2_delta'; label: string }> = []
    if (hasCalculatedRoutes.value) {
      modes.push({ value: 'frequency', label: 'Edge Usage Frequency' })
    }
    // Check if we have CO2 data
    const hasCO2 = newEdgeUsage.value.some(
      (stat) => stat.co2_per_use !== undefined && stat.co2_per_use > 0
    )
    if (hasCO2 && hasCalculatedRoutes.value) {
      modes.push({ value: 'co2', label: 'CO₂ Emissions' })
    }
    // Check if we have delta data (recalculated with removed edges)
    const hasDelta = newEdgeUsage.value.some(
      (stat) => stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001
    )
    if (hasDelta) {
      modes.push({ value: 'delta', label: 'Traffic Change (Delta)' })
    }
    if (hasDelta && hasCO2) {
      modes.push({ value: 'co2_delta', label: 'CO₂ Emissions Change' })
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

  function addRemovedEdge(u: number, v: number) {
    const key = `${u}-${v}`
    const newSet = new Set(removedEdges.value)
    newSet.add(key)
    removedEdges.value = newSet
  }

  function removeRemovedEdge(u: number, v: number) {
    const key = `${u}-${v}`
    const newSet = new Set(removedEdges.value)
    newSet.delete(key)
    removedEdges.value = newSet
  }

  function toggleEdge(u: number, v: number) {
    const key = `${u}-${v}`
    const newSet = new Set(removedEdges.value)
    if (newSet.has(key)) {
      newSet.delete(key)
    } else {
      newSet.add(key)
    }
    removedEdges.value = newSet
  }

  function clearRemovedEdges() {
    removedEdges.value = new Set()
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
    const hasCO2 = newUsage.some((stat) => stat.co2_per_use !== undefined && stat.co2_per_use > 0)

    if (hasCO2) {
      // Calculate CO2 total emissions scale (co2_per_use * count)
      const co2Totals = newUsage.map((d) => (d.co2_per_use ?? 0) * d.count)
      const maxCO2 = Math.max(...co2Totals, 1)
      co2MinValue.value = 0
      co2MaxValue.value = maxCO2
      co2ColorScale.value = scaleSequential(interpolateViridis).domain([0, maxCO2])
    }

    // Check if we have delta values (recalculated routes)
    const hasDeltaValues = newUsage.some(
      (stat) => stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001
    )

    if (hasDeltaValues) {
      // Calculate delta scale
      const minDelta = Math.min(...newUsage.map((d) => d.delta_count ?? 0), -1)
      const maxDelta = Math.max(...newUsage.map((d) => d.delta_count ?? 0), 1)
      deltaMinValue.value = minDelta
      deltaMaxValue.value = maxDelta
      deltaColorScale.value = scaleDiverging(interpolateRdBu).domain([maxDelta, 0, minDelta])

      // Calculate CO2 delta scale if we have CO2 data
      if (hasCO2) {
        const co2Deltas = newUsage.map((d) => (d.co2_per_use ?? 0) * (d.delta_count ?? 0))
        const minCO2Delta = Math.min(...co2Deltas, -1)
        const maxCO2Delta = Math.max(...co2Deltas, 1)
        co2DeltaMinValue.value = minCO2Delta
        co2DeltaMaxValue.value = maxCO2Delta
        co2DeltaColorScale.value = scaleDiverging(interpolateRdBu).domain([
          maxCO2Delta,
          0,
          minCO2Delta
        ])
      }

      // Auto-select delta visualization when available
      activeVisualization.value = 'delta'
    } else {
      // Auto-select frequency visualization
      activeVisualization.value = 'frequency'
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
    activeVisualization.value = 'none'
  }

  function setEdgeGeometries(geometries: EdgeGeometry[]) {
    edgeGeometries.value = geometries
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
    } else {
      colorScale.value = null
      minValue.value = 0
      maxValue.value = 0
      legendMode.value = 'none'
    }
  }

  function setActiveVisualization(mode: 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta') {
    activeVisualization.value = mode
    updateActiveColorScale()
  }

  return {
    // State
    isOpen,
    isLoading,
    isCalculating,
    removedEdges,
    nodePairs,
    originalEdgeUsage,
    newEdgeUsage,
    impactStatistics,

    // Visualization state
    legendMode,
    colorScale,
    minValue,
    maxValue,
    activeVisualization,

    // Computed
    removedEdgesArray,
    removedEdgesForDisplay,
    removedEdgesCount,
    hasCalculatedRoutes,
    availableVisualizations,

    // Actions
    togglePanel,
    openPanel,
    closePanel,
    addRemovedEdge,
    removeRemovedEdge,
    toggleEdge,
    clearRemovedEdges,
    setNodePairs,
    setEdgeUsage,
    clearResults,
    setEdgeGeometries,
    getColor,
    setActiveVisualization
  }
})
