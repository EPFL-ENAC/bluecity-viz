import {
  fetchEdgeGeometries,
  type EdgeGeometry
} from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { GeoJsonLayer, PathLayer } from '@deck.gl/layers'
import type { Ref } from 'vue'
import { shallowRef } from 'vue'

interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  delta_frequency?: number
}

interface DeckGLTrafficAnalysisReturn {
  layers: Ref<any[]>
  loadGraphEdges: () => Promise<void>
  updateRemovedEdges: (removedEdges: { u: number; v: number }[]) => void
  visualizeEdgeUsage: (originalUsage: EdgeUsageStats[], newUsage: EdgeUsageStats[]) => void
  clearRoutes: () => void
  handleClick: (info: any) => void
  setEdgeClickCallback: (callback: (u: number, v: number) => void) => void
}

/**
 * Composable for managing traffic analysis visualization using Deck.gl
 */
export function useDeckGLTrafficAnalysis(): DeckGLTrafficAnalysisReturn {
  // Use shallowRef for large arrays to avoid deep reactivity overhead
  const layers = shallowRef<any[]>([])
  const edgeGeometries = shallowRef<EdgeGeometry[]>([])
  const removedEdgesSet = shallowRef<Set<string>>(new Set())
  let edgeClickCallback: ((u: number, v: number) => void) | null = null

  // Get store instance
  const trafficStore = useTrafficAnalysisStore()

  // Cache the base layer to avoid recreating it (can be MVTLayer or PathLayer)
  let baseLayer: any = null

  /**
   * Load graph edges as GeoJSON for efficient rendering and interaction
   */
  async function loadGraphEdges(): Promise<void> {
    try {
      console.time('Loading graph edges as GeoJSON')

      // Load all edge geometries at once
      const edges = await fetchEdgeGeometries()
      edgeGeometries.value = edges

      // Populate the store with edge geometries for display purposes
      trafficStore.setEdgeGeometries(edges)

      console.log(`Loaded ${edges.length} edge geometries`)

      // Convert to GeoJSON format for Deck.gl
      const geojsonData: any = {
        type: 'FeatureCollection',
        features: edges.map(edge => ({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: edge.coordinates
          },
          properties: {
            u: edge.u,
            v: edge.v,
            name: edge.name,
            highway: edge.highway,
            travel_time: edge.travel_time,
            length: edge.length
          }
        }))
      }

      // Create single GeoJsonLayer for all edges
      baseLayer = new GeoJsonLayer({
        id: 'traffic-graph-edges',
        data: geojsonData,
        lineWidthMinPixels: 1,
        getLineColor: [136, 136, 136, 153],
        getLineWidth: 2,
        getFillColor: [136, 136, 136, 100],
        pickable: true,
        autoHighlight: true,
        highlightColor: [0, 170, 255, 200]
      })

      console.timeEnd('Loading graph edges as GeoJSON')

      layers.value = [baseLayer]
    } catch (error) {
      console.error('Failed to load graph edges:', error)
    }
  }

  /**
   * Update removed edges visualization
   */
  function updateRemovedEdges(removedEdges: { u: number; v: number }[]): void {
    removedEdgesSet.value = new Set(removedEdges.map((e) => `${e.u}-${e.v}`))

    if (edgeGeometries.value.length === 0 || !baseLayer) return

    // Filter removed edges efficiently (only once)
    const removedEdgeGeometries = edgeGeometries.value.filter((edge) => {
      const key = `${edge.u}-${edge.v}`
      return removedEdgesSet.value.has(key)
    })

    // Create/update removed layer
    const removedLayer = new PathLayer({
      id: 'traffic-removed-edges',
      data: removedEdgeGeometries,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: [255, 0, 0, 230],
      getWidth: 30,
      widthUnits: 'pixels',
      getDashArray: [2, 2],
      dashJustified: true,
      pickable: true
    })

    // Keep route layers if they exist
    const routeLayers = layers.value.filter(
      (l) => l.id === 'traffic-original-routes' || l.id === 'traffic-new-routes'
    )

    layers.value = [
      baseLayer,
      ...(removedEdgeGeometries.length > 0 ? [removedLayer] : []),
      ...routeLayers
    ]
  }

  /**
   * Visualize edge usage statistics using Deck.gl PathLayer
   */
  function visualizeEdgeUsage(originalUsage: EdgeUsageStats[], newUsage: EdgeUsageStats[]): void {
    clearRoutes()

    // Build lookup map for edges
    const edgeMap = new Map<string, EdgeGeometry>()
    edgeGeometries.value.forEach((edge) => {
      edgeMap.set(`${edge.u}-${edge.v}`, edge)
    })

    // Map usage stats to edge geometries with frequency data
    const originalWithFreq = originalUsage
      .map((stat) => {
        const edge = edgeMap.get(`${stat.u}-${stat.v}`)
        return edge ? { ...edge, frequency: stat.frequency } : null
      })
      .filter(Boolean) as (EdgeGeometry & { frequency: number })[]

    const newWithFreq = newUsage
      .map((stat) => {
        const edge = edgeMap.get(`${stat.u}-${stat.v}`)
        return edge ? { ...edge, frequency: stat.frequency } : null
      })
      .filter(Boolean) as (EdgeGeometry & { frequency: number })[]

    // Calculate max frequency for normalization
    const maxOriginalFreq = Math.max(...originalWithFreq.map((d) => d.frequency), 0.01)
    const maxNewFreq =
      newWithFreq.length > 0
        ? Math.max(...newWithFreq.map((d) => d.frequency), 0.01)
        : maxOriginalFreq

    // Normalize frequency to opacity range [20%, 80%] (51 to 204)
    const getOpacity = (frequency: number, maxFreq: number) => {
      const normalized = frequency / maxFreq // 0 to 1
      return Math.round(51 + normalized * 204) // 20% to 100% of 255
    }

    // Create original routes layer (blue)
    const originalLayer = new PathLayer({
      id: 'traffic-original-routes',
      data: originalWithFreq,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: (d: any) => [33, 150, 243, getOpacity(d.frequency, maxOriginalFreq)], // Blue with frequency-based opacity
      getWidth: (d: any) => Math.max(2, Math.min(10, d.frequency * 100 + 2)),
      widthUnits: 'pixels',
      widthMinPixels: 2,
      widthMaxPixels: 10,
      pickable: true,
      autoHighlight: true
    })

    // Create new routes layer (orange) - only if different
    const newLayer =
      newUsage.length > 0 && newUsage.length !== originalUsage.length
        ? new PathLayer({
            id: 'traffic-new-routes',
            data: newWithFreq,
            getPath: (d: EdgeGeometry) => d.coordinates,
            getColor: (d: any) => [255, 152, 0, getOpacity(d.frequency, maxNewFreq)], // Orange with frequency-based opacity
            getWidth: (d: any) => Math.max(2, Math.min(10, d.frequency * 100 + 2)),
            widthUnits: 'pixels',
            widthMinPixels: 2,
            widthMaxPixels: 10,
            pickable: true,
            autoHighlight: true
          })
        : null

    // Update layers array - preserve base and removed layers
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')
    const preservedLayers = [baseLayer, removedLayer].filter(Boolean)

    layers.value = [...preservedLayers, originalLayer, ...(newLayer ? [newLayer] : [])]
  }

  /**
   * Clear all route visualizations
   */
  function clearRoutes(): void {
    // Keep only the base graph edges and removed edges layers
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')
    layers.value = [baseLayer, removedLayer].filter(Boolean)
  }

  /**
   * Handle click events on edges
   */
  function handleClick(info: any): void {
    if (!info.object || !edgeClickCallback) return

    // Get all edges that share the same coordinates as the clicked edge
    const clickedEdge = info.object as EdgeGeometry
    if (clickedEdge.u === undefined || clickedEdge.v === undefined) return

    // Also explicitly look for the reverse edge (u-v becomes v-u)
    const reverseEdge = edgeGeometries.value.find(
      (edge) => edge.u === clickedEdge.v && edge.v === clickedEdge.u
    )
    edgeClickCallback(clickedEdge.u, clickedEdge.v)

    if (reverseEdge) {
      edgeClickCallback(reverseEdge.u!, reverseEdge.v!)
    }
  }

  /**
   * Set callback for edge clicks
   */
  function setEdgeClickCallback(callback: (u: number, v: number) => void): void {
    edgeClickCallback = callback
  }

  return {
    layers,
    loadGraphEdges,
    updateRemovedEdges,
    visualizeEdgeUsage,
    clearRoutes,
    handleClick,
    setEdgeClickCallback
  }
}
