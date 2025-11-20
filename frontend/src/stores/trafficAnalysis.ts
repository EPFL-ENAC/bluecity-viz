import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

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
}

export const useTrafficAnalysisStore = defineStore('trafficAnalysis', () => {
  // State
  const isOpen = ref(false)
  const isLoading = ref(false)
  const isCalculating = ref(false)
  const removedEdges = ref<Set<string>>(new Set())
  const nodePairs = ref<NodePair[]>([])
  const originalEdgeUsage = ref<EdgeUsageStats[]>([])
  const newEdgeUsage = ref<EdgeUsageStats[]>([])

  // Computed
  const removedEdgesArray = computed(() => {
    return Array.from(removedEdges.value).map((key) => {
      const [u, v] = key.split('-').map(Number)
      return { u, v }
    })
  })

  const removedEdgesCount = computed(() => removedEdges.value.size)

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
  }

  function clearResults() {
    originalEdgeUsage.value = []
    newEdgeUsage.value = []
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

    // Computed
    removedEdgesArray,
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
    clearResults
  }
})
