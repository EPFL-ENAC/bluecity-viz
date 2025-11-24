import { fetchEdgeGeometries, type EdgeGeometry } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { PathStyleExtension } from '@deck.gl/extensions'
import { GeoJsonLayer, PathLayer } from '@deck.gl/layers'
import type { Ref } from 'vue'
import { shallowRef } from 'vue'

interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  co2_per_use?: number
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

      // Create single GeoJsonLayer for all edges (always pickable for removal)
      baseLayer = new GeoJsonLayer({
        id: 'traffic-graph-edges',
        data: geojsonData,
        lineWidthMinPixels: 3,
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

    // Create/update removed layer with dashed black lines on top
    const removedLayer = new PathLayer({
      id: 'traffic-removed-edges',
      data: removedEdgeGeometries,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: [0, 0, 0, 255], // Solid black
      getWidth: 15,
      widthUnits: 'pixels',
      getDashArray: [5, 5], // Dashed pattern: 10px line, 5px gap
      dashJustified: true,
      dashGapPickable: true,
      pickable: true,
      extensions: [new PathStyleExtension({ dash: true })]
    })

    // Keep route layers if they exist
    const routeLayers = layers.value.filter((l) => l.id.startsWith('traffic-routes'))

    // Removed edges should be on top of everything
    layers.value = [
      baseLayer,
      ...routeLayers,
      ...(removedEdgeGeometries.length > 0 ? [removedLayer] : [])
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

    // Use new usage stats (which include delta_count and co2_per_use)
    const edgesWithStats = newUsage
      .map((stat) => {
        const edge = edgeMap.get(`${stat.u}-${stat.v}`)
        return edge
          ? {
              ...edge,
              frequency: stat.frequency,
              delta_count: stat.delta_count ?? 0,
              co2_per_use: stat.co2_per_use ?? 0,
              count: stat.count,
              co2_total: (stat.co2_per_use ?? 0) * stat.count,
              co2_delta: (stat.co2_per_use ?? 0) * (stat.delta_count ?? 0)
            }
          : null
      })
      .filter(Boolean) as (EdgeGeometry & {
      frequency: number
      delta_count: number
      co2_per_use: number
      count: number
      co2_total: number
      co2_delta: number
    })[]

    console.log('[DEBUG] edgesWithStats length:', edgesWithStats.length)
    console.log(
      '[DEBUG] First 3 edgesWithStats:',
      edgesWithStats.slice(0, 3).map((e) => ({
        u: e.u,
        v: e.v,
        frequency: e.frequency,
        delta_count: e.delta_count,
        co2_total: e.co2_total,
        co2_delta: e.co2_delta
      }))
    )

    // Determine which value to use for coloring based on active visualization
    const activeMode = trafficStore.activeVisualization

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
        let value: number
        if (activeMode === 'frequency') {
          value = d.frequency
        } else if (activeMode === 'delta') {
          value = d.delta_count
        } else if (activeMode === 'co2') {
          value = d.co2_total
        } else if (activeMode === 'co2_delta') {
          value = d.co2_delta
        } else {
          value = d.frequency
        }
        return trafficStore.getColor(value)
      },
      getWidth: (d: any) => Math.max(2, Math.min(10, d.frequency * 100 + 2)),
      widthUnits: 'pixels',
      widthMinPixels: 2,
      widthMaxPixels: 10,
      pickable: true,
      autoHighlight: true
    })

    // Update layers array - removed edges on top for visibility
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')

    layers.value = [
      baseLayer,
      outlineLayer,
      trafficLayer,
      ...(removedLayer ? [removedLayer] : [])
    ].filter(Boolean)
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

    // Handle both GeoJSON features and direct edge objects
    const clickedEdge = info.object.properties || info.object
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
