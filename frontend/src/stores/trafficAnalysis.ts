import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { rgb } from 'd3-color'
import { scaleDiverging, scaleSequential } from 'd3-scale'
import { interpolateRdBu, interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

type ColorScale = ((value: number) => string) | null
type LegendMode = 'none' | 'frequency' | 'delta'

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
  delta_count?: number
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

  // Visualization state
  const legendMode = ref<LegendMode>('none')
  const colorScale = ref<ColorScale>(null)
  const minValue = ref<number>(0)
  const maxValue = ref<number>(0)

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

  function setEdgeUsage(original: EdgeUsageStats[], newUsage: EdgeUsageStats[]) {
    originalEdgeUsage.value = original
    newEdgeUsage.value = newUsage

    // Calculate color scale based on usage data
    if (newUsage.length === 0) {
      legendMode.value = 'none'
      colorScale.value = null
      return
    }

    // Check if we have delta values (recalculated routes)
    const hasDeltaValues = newUsage.some(
      (stat) => stat.delta_count !== undefined && Math.abs(stat.delta_count) > 0.001
    )

    if (hasDeltaValues) {
      // Delta mode: diverging scale
      const minDelta = Math.min(...newUsage.map((d) => d.delta_count ?? 0), -1)
      const maxDelta = Math.max(...newUsage.map((d) => d.delta_count ?? 0), 1)
      minValue.value = minDelta
      maxValue.value = maxDelta
      legendMode.value = 'delta'
      colorScale.value = scaleDiverging(interpolateRdBu).domain([maxDelta, 0, minDelta])
    } else {
      // Frequency mode: sequential scale
      const maxFreq = Math.max(...newUsage.map((d) => d.frequency), 0.01)
      minValue.value = 0
      maxValue.value = maxFreq
      legendMode.value = 'frequency'
      colorScale.value = scaleSequential(interpolateViridis).domain([0, maxFreq])
    }
  }

  function clearResults() {
    originalEdgeUsage.value = []
    newEdgeUsage.value = []
    legendMode.value = 'none'
    colorScale.value = null
    minValue.value = 0
    maxValue.value = 0
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

  return {
    // State
    isOpen,
    isLoading,
    isCalculating,
    removedEdges,
    nodePairs,
    originalEdgeUsage,
    newEdgeUsage,

    // Visualization state
    legendMode,
    colorScale,
    minValue,
    maxValue,

    // Computed
    removedEdgesArray,
    removedEdgesForDisplay,
    removedEdgesCount,
    hasCalculatedRoutes,

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
    getColor
  }
})
