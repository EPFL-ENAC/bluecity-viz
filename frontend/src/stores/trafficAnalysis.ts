import type { EdgeModification, ImpactStatistics } from '@/services/trafficAnalysis'
import { rgb } from 'd3-color'
import { scaleDiverging, scaleSequential } from 'd3-scale'
import { interpolateSpectral, interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

type ColorScale = ((value: number) => string) | null
type LegendMode = 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta'
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
  co2_per_use?: number
}

export interface Route {
  origin: number
  destination: number
  path: number[]
  travel_time?: number
  distance?: number
  elevation_gain?: number
  co2_emissions?: number
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
  const routes = shallowRef<Route[]>([]) // Store calculated routes for trips visualization

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
  const activeVisualization = ref<'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta' | 'routes'>(
    'none'
  ) // User-selected visualization

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
      value: 'frequency' | 'delta' | 'co2' | 'co2_delta' | 'routes'
      label: string
    }> = []
    if (hasCalculatedRoutes.value) {
      modes.push({ value: 'frequency', label: 'Edge Usage Frequency' })
    }
    if (routes.value.length > 0) {
      modes.push({ value: 'routes', label: 'Animated Routes' })
    }
    const hasCO2 = newEdgeUsage.value.some(
      (stat) => stat.co2_per_use !== undefined && stat.co2_per_use > 0
    )
    if (hasCO2 && hasCalculatedRoutes.value) {
      modes.push({ value: 'co2', label: 'CO₂ Emissions' })
    }
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
    impact?: ImpactStatistics,
    calculatedRoutes?: Route[]
  ) {
    originalEdgeUsage.value = original
    newEdgeUsage.value = newUsage
    impactStatistics.value = impact || null
    routes.value = calculatedRoutes || []

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

      // Calculate CO2 delta scale if we have CO2 data (symmetrical around zero)
      if (hasCO2) {
        const co2Deltas = newUsage.map((d) => (d.co2_per_use ?? 0) * (d.delta_count ?? 0))
        const absCO2DeltaMax = Math.max(...co2Deltas.map(Math.abs), 0.01)
        co2DeltaMinValue.value = -absCO2DeltaMax
        co2DeltaMaxValue.value = absCO2DeltaMax
        co2DeltaColorScale.value = scaleDiverging(interpolateSpectral).domain([
          absCO2DeltaMax,
          0,
          -absCO2DeltaMax
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

  function setActiveVisualization(
    mode: 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta' | 'routes'
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
    activeVisualization: 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta' | 'routes'
  }) {
    isRestoring.value = true
    isOpen.value = state.isOpen

    // Restore edge modifications
    const modMap = new Map<string, { action: ModificationAction; name: string }>()
    state.edgeModifications.forEach(
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
    routes,

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
