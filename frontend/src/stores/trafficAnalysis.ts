import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface GraphEdge {
  u: number
  v: number
  geometry: {
    coordinates: number[][]
  }
  name?: string
  highway?: string
  speed_kph?: number
  length?: number
  travel_time?: number
}

export interface NodePair {
  origin: number
  destination: number
}

export interface Route {
  origin: number
  destination: number
  path: number[]
  geometry?: {
    coordinates: number[][]
  }
  travel_time?: number
  distance?: number
}

export interface RouteComparison {
  origin: number
  destination: number
  original_route: Route
  new_route: Route
  removed_edge_on_path?: {
    u: number
    v: number
  }
}

export const useTrafficAnalysisStore = defineStore('trafficAnalysis', () => {
  // State
  const isOpen = ref(false)
  const isLoading = ref(false)
  const graphEdges = ref<GraphEdge[]>([])
  const removedEdges = ref<Set<string>>(new Set())
  const nodePairs = ref<NodePair[]>([])
  const originalRoutes = ref<Route[]>([])
  const newRoutes = ref<Route[]>([])
  const comparisons = ref<RouteComparison[]>([])
  const isCalculating = ref(false)
  const clickMode = ref<'add' | 'remove'>('remove')

  // Computed
  const removedEdgesArray = computed(() => {
    return Array.from(removedEdges.value).map((key) => {
      const [u, v] = key.split('-').map(Number)
      return { u, v }
    })
  })

  const removedEdgesCount = computed(() => removedEdges.value.size)

  const hasCalculatedRoutes = computed(() => comparisons.value.length > 0)

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

  function toggleClickMode() {
    clickMode.value = clickMode.value === 'remove' ? 'add' : 'remove'
  }

  function addRemovedEdge(u: number, v: number) {
    const key = `${u}-${v}`
    removedEdges.value.add(key)
  }

  function removeRemovedEdge(u: number, v: number) {
    const key = `${u}-${v}`
    removedEdges.value.delete(key)
  }

  function toggleEdge(u: number, v: number) {
    const key = `${u}-${v}`
    if (removedEdges.value.has(key)) {
      removedEdges.value.delete(key)
    } else {
      removedEdges.value.add(key)
    }
  }

  function clearRemovedEdges() {
    removedEdges.value.clear()
  }

  function isEdgeRemoved(u: number, v: number): boolean {
    const key = `${u}-${v}`
    return removedEdges.value.has(key)
  }

  function setGraphEdges(edges: GraphEdge[]) {
    graphEdges.value = edges
  }

  function setNodePairs(pairs: NodePair[]) {
    nodePairs.value = pairs
  }

  function setComparisons(newComparisons: RouteComparison[]) {
    comparisons.value = newComparisons
    originalRoutes.value = newComparisons.map((c) => c.original_route)
    newRoutes.value = newComparisons.map((c) => c.new_route)
  }

  function clearResults() {
    comparisons.value = []
    originalRoutes.value = []
    newRoutes.value = []
  }

  return {
    // State
    isOpen,
    isLoading,
    isCalculating,
    clickMode,
    graphEdges,
    removedEdges,
    nodePairs,
    originalRoutes,
    newRoutes,
    comparisons,

    // Computed
    removedEdgesArray,
    removedEdgesCount,
    hasCalculatedRoutes,

    // Actions
    togglePanel,
    openPanel,
    closePanel,
    toggleClickMode,
    addRemovedEdge,
    removeRemovedEdge,
    toggleEdge,
    clearRemovedEdges,
    isEdgeRemoved,
    setGraphEdges,
    setNodePairs,
    setComparisons,
    clearResults
  }
})
