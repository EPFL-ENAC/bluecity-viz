import type { CVRPSolveResponse } from '@/services/cvrp'
import { fetchCVRPCentroids, solveCVRP } from '@/services/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { scaleSequential } from 'd3-scale'
import { interpolateViridis } from 'd3-scale-chromatic'
import type { FeatureCollection } from 'geojson'
import { defineStore } from 'pinia'
import { computed, markRaw, ref, shallowRef } from 'vue'

// Okabe-Ito palette: colour-blind safe, and the data-viz palette of the
// EPFL design system. 8 colours, reused past the 8th vehicle.
const VEHICLE_COLORS: [number, number, number, number][] = [
  [0, 114, 178, 200], // #0072B2 blue
  [230, 159, 0, 200], // #E69F00 orange
  [0, 158, 115, 200], // #009E73 green
  [213, 94, 0, 200], // #D55E00 vermillion
  [86, 180, 233, 200], // #56B4E9 sky blue
  [204, 121, 167, 200], // #CC79A7 purple
  [240, 228, 66, 200], // #F0E442 yellow
  [0, 0, 0, 200] // #000000 black
]

export function getVehicleColor(routeId: number): [number, number, number, number] {
  return VEHICLE_COLORS[routeId % VEHICLE_COLORS.length]
}

export const useCVRPStore = defineStore('cvrp', () => {
  // Panel state
  const isOpen = ref(false)
  const isSolving = ref(false)
  const showCentroids = ref(false)

  // Solver configuration
  const wasteType = ref<'DI' | 'DV' | 'PC' | 'VE'>('DI')
  const nVehicles = ref(5)
  const vehicleCapacity = ref(5000)
  const maxRuntime = ref(10)
  const loadUnit = ref<'kg' | 'kg_m'>('kg')

  // Visualization mode
  const visualizationMode = ref<'routes' | 'heatmap'>('routes')

  // Results. Shallow: a deep reactive proxy on thousands of coordinates costs
  // more than building the GeoJSON the map reads.
  const lastResult = shallowRef<CVRPSolveResponse | null>(null)
  const centroids = shallowRef<FeatureCollection | null>(null)

  // Edge load color scale (Viridis, domain set from 98th percentile of loads)
  const edgeLoadColorScale = ref<((v: number) => string) | null>(null)
  const edgeLoadMax = ref(0)

  const hasResult = computed(() => lastResult.value !== null)

  // The scenario this solution was found on. When the graph is edited after,
  // the routes no longer answer the question on screen.
  const resultScenarioHash = ref<string | null>(null)

  const isStale = computed(() => {
    if (!hasResult.value) return false
    return resultScenarioHash.value !== useScenarioStore().hash
  })

  function getEdgeLoadColor(load: number): [number, number, number, number] {
    if (!edgeLoadColorScale.value || edgeLoadMax.value === 0) return [100, 100, 100, 180]
    const hex = edgeLoadColorScale.value(load)
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return [r, g, b, 220]
  }

  function setResult(result: CVRPSolveResponse) {
    lastResult.value = markRaw(result)

    // Build edge load color scale
    if (result.edge_loads.length > 0) {
      const loads = result.edge_loads.map((e) => e.load).sort((a, b) => a - b)
      const p98Index = Math.floor(loads.length * 0.98)
      const maxLoad = loads[Math.min(p98Index, loads.length - 1)] || 1
      edgeLoadMax.value = maxLoad
      edgeLoadColorScale.value = scaleSequential(interpolateViridis).domain([0, maxLoad])
    }

    // A fresh solution is what the user asked for, so light the tool zone.
    if (useScenarioStore().activeTab === 'cvrp') useScenarioStore().mapMode = 'result'
  }

  function clearResult() {
    // Only when this tab is the one on the map: routing may still show a result.
    if (lastResult.value && useScenarioStore().activeTab === 'cvrp') {
      useScenarioStore().mapMode = 'scenario'
    }
    lastResult.value = null
    edgeLoadColorScale.value = null
    edgeLoadMax.value = 0
    resultScenarioHash.value = null
  }

  async function solve() {
    const scenarioStore = useScenarioStore()
    isSolving.value = true
    try {
      const response = await solveCVRP({
        waste_type: wasteType.value,
        n_vehicles: nVehicles.value,
        vehicle_capacity: vehicleCapacity.value,
        max_runtime: maxRuntime.value,
        waste_per_centroid: 10,
        load_unit: loadUnit.value,
        edge_modifications: scenarioStore.wire
      })
      setResult(response)
      resultScenarioHash.value = scenarioStore.hash
    } finally {
      isSolving.value = false
    }
  }

  async function loadCentroids() {
    centroids.value = markRaw(await fetchCVRPCentroids(wasteType.value))
    showCentroids.value = true
  }

  function togglePanel() {
    isOpen.value = !isOpen.value
  }

  return {
    // State
    isOpen,
    isSolving,
    showCentroids,
    wasteType,
    nVehicles,
    vehicleCapacity,
    maxRuntime,
    loadUnit,
    visualizationMode,
    lastResult,
    centroids,
    edgeLoadMax,
    resultScenarioHash,
    // Computed
    hasResult,
    isStale,
    // Actions
    solve,
    loadCentroids,
    clearResult,
    togglePanel,
    getEdgeLoadColor
  }
})
