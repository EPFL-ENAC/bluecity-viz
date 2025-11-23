import { fetchEdgeGeometries, type EdgeGeometry } from '@/services/trafficAnalysis'
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
        features: edges.map((edge) => ({
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

    // Create/update removed layer with dashed black arrows (more visible)
    const removedLayer = new PathLayer({
      id: 'traffic-removed-edges',
      data: removedEdgeGeometries,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: [0, 0, 0, 255], // Solid black
      getWidth: 6,
      widthUnits: 'pixels',
      getDashArray: [8, 4], // Dashed pattern: 8px line, 4px gap (more visible)
      dashJustified: true,
      pickable: true
    })

    // Keep route layers if they exist
    const routeLayers = layers.value.filter((l) => l.id === 'traffic-routes')

    layers.value = [
      baseLayer,
      ...(removedEdgeGeometries.length > 0 ? [removedLayer] : []),
      ...routeLayers
    ]
  }

  /**
   * Visualize edge usage statistics using delta frequency for color coding
   */
  function visualizeEdgeUsage(originalUsage: EdgeUsageStats[], newUsage: EdgeUsageStats[]): void {
    clearRoutes()

    console.log('[DEBUG] visualizeEdgeUsage called')
    console.log('[DEBUG] newUsage length:', newUsage.length)
    console.log('[DEBUG] First 3 newUsage entries:', newUsage.slice(0, 3))

    // Build lookup map for edges
    const edgeMap = new Map<string, EdgeGeometry>()
    edgeGeometries.value.forEach((edge) => {
      edgeMap.set(`${edge.u}-${edge.v}`, edge)
    })

    // Use new usage stats (which include delta_count)
    const edgesWithStats = newUsage
      .map((stat) => {
        const edge = edgeMap.get(`${stat.u}-${stat.v}`)
        return edge
          ? {
              ...edge,
              frequency: stat.frequency,
              delta_count: stat.delta_count ?? 0 // Use nullish coalescing to default to 0
            }
          : null
      })
      .filter(Boolean) as (EdgeGeometry & { frequency: number; delta_count: number })[]

    console.log('[DEBUG] edgesWithStats length:', edgesWithStats.length)
    console.log(
      '[DEBUG] First 3 edgesWithStats:',
      edgesWithStats.slice(0, 3).map((e) => ({
        u: e.u,
        v: e.v,
        frequency: e.frequency,
        delta_count: e.delta_count
      }))
    )

    // Determine which value to use for coloring
    const hasDeltaValues = trafficStore.legendMode === 'delta'

    // Create outline layer
    const outlineLayer = new PathLayer({
      id: 'traffic-routes-outline',
      data: edgesWithStats,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: [0, 0, 0, 120], // Light dark outline
      getWidth: (d: any) => Math.max(4, Math.min(12, d.frequency * 100 + 4)), // 2px wider than main
      widthUnits: 'pixels',
      widthMinPixels: 4,
      widthMaxPixels: 12,
      pickable: false
    })

    // Create main traffic layer with color from store
    const trafficLayer = new PathLayer({
      id: 'traffic-routes',
      data: edgesWithStats,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: (d: any) => {
        const value = hasDeltaValues ? d.delta_count : d.frequency
        return trafficStore.getColor(value)
      },
      getWidth: (d: any) => Math.max(2, Math.min(10, d.frequency * 100 + 2)),
      widthUnits: 'pixels',
      widthMinPixels: 2,
      widthMaxPixels: 10,
      pickable: true,
      autoHighlight: true
    })

    // Update layers array - preserve base and removed layers
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')
    const preservedLayers = [baseLayer, removedLayer].filter(Boolean)

    layers.value = [...preservedLayers, outlineLayer, trafficLayer]
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
