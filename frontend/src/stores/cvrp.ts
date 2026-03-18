import { scaleSequential } from 'd3-scale'
import { interpolateViridis } from 'd3-scale-chromatic'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { solveCVRP, fetchCVRPCentroids } from '@/services/cvrp'
import type { CVRPSolveResponse } from '@/services/cvrp'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'

// Up to 15 distinct vehicle colors (HSL hue-spaced)
const VEHICLE_COLORS: [number, number, number, number][] = Array.from({ length: 15 }, (_, i) => {
  const hue = (i * 360) / 15
  // Convert HSL to RGB approximately (saturation 70%, lightness 50%)
  const h = hue / 360
  const s = 0.7
  const l = 0.5
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  const hue2rgb = (t: number) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }
  const r = Math.round(hue2rgb(h + 1 / 3) * 255)
  const g = Math.round(hue2rgb(h) * 255)
  const b = Math.round(hue2rgb(h - 1 / 3) * 255)
  return [r, g, b, 200] as [number, number, number, number]
})

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

  // Results
  const lastResult = ref<CVRPSolveResponse | null>(null)
  const centroids = ref<GeoJSON.FeatureCollection | null>(null)

  // Edge load color scale (Viridis, domain set from 98th percentile of loads)
  const edgeLoadColorScale = ref<((v: number) => string) | null>(null)
  const edgeLoadMax = ref(0)

  const hasResult = computed(() => lastResult.value !== null)

  function getEdgeLoadColor(load: number): [number, number, number, number] {
    if (!edgeLoadColorScale.value || edgeLoadMax.value === 0) return [100, 100, 100, 180]
    const hex = edgeLoadColorScale.value(load)
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return [r, g, b, 220]
  }

  function setResult(result: CVRPSolveResponse) {
    lastResult.value = result

    // Build edge load color scale
    if (result.edge_loads.length > 0) {
      const loads = result.edge_loads.map((e) => e.load).sort((a, b) => a - b)
      const p98Index = Math.floor(loads.length * 0.98)
      const maxLoad = loads[Math.min(p98Index, loads.length - 1)] || 1
      edgeLoadMax.value = maxLoad
      edgeLoadColorScale.value = scaleSequential(interpolateViridis).domain([0, maxLoad])
    }
  }

  function clearResult() {
    lastResult.value = null
    edgeLoadColorScale.value = null
    edgeLoadMax.value = 0
  }

  async function solve() {
    const trafficStore = useTrafficAnalysisStore()
    isSolving.value = true
    try {
      const response = await solveCVRP({
        waste_type: wasteType.value,
        n_vehicles: nVehicles.value,
        vehicle_capacity: vehicleCapacity.value,
        max_runtime: maxRuntime.value,
        waste_per_centroid: 10,
        load_unit: loadUnit.value,
        edge_modifications: trafficStore.edgeModificationsArray,
      })
      setResult(response)
    } finally {
      isSolving.value = false
    }
  }

  async function loadCentroids() {
    centroids.value = await fetchCVRPCentroids(wasteType.value)
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
    // Computed
    hasResult,
    // Actions
    solve,
    loadCentroids,
    clearResult,
    togglePanel,
    getEdgeLoadColor,
  }
})
