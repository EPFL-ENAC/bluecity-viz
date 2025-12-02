import { fetchEdgeGeometries, type EdgeGeometry, type Route } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore, type ModificationAction } from '@/stores/trafficAnalysis'
import { PathStyleExtension } from '@deck.gl/extensions'
import { TripsLayer } from '@deck.gl/geo-layers'
import { GeoJsonLayer, PathLayer } from '@deck.gl/layers'
import type { Ref } from 'vue'
import { ref, shallowRef } from 'vue'

// Colors for different modification types
const MODIFICATION_COLORS: Record<ModificationAction, [number, number, number, number]> = {
  remove: [0, 0, 0, 180], // Black for removed
  speed50: [220, 38, 38, 200], // Red for 10 km/h
  speed30: [251, 146, 60, 200], // Orange for 30 km/h
  speed10: [250, 204, 21, 200] // Yellow for 50 km/h
}

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
  updateModifiedEdges: () => void
  visualizeEdgeUsage: (newUsage: EdgeUsageStats[]) => void
  clearRoutes: () => void
  handleClick: (info: any) => void
  setEdgeClickCallback: (callback: (u: number, v: number, name?: string) => void) => void
}

/**
 * Composable for managing traffic analysis visualization using Deck.gl
 */
export function useDeckGLTrafficAnalysis(): DeckGLTrafficAnalysisReturn {
  // Use shallowRef for large arrays to avoid deep reactivity overhead
  const layers = shallowRef<any[]>([])
  const edgeGeometries = shallowRef<EdgeGeometry[]>([])
  const edgeMap = shallowRef<Map<string, EdgeGeometry>>(new Map())
  let edgeClickCallback: ((u: number, v: number, name?: string) => void) | null = null

  // Animation state for TripsLayer
  const animationTime = ref(0)
  const animationLoop = ref<number | null>(null)
  const trailLength = 40 // seconds (longer trail for better visibility)
  const loopLength = ref<number>(1000)

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

      // Always load edge geometries fresh (don't cache in store)
      const edges = await fetchEdgeGeometries()
      edgeGeometries.value = edges
      edgeGeometries.value.forEach((edge) => {
        edgeMap.value.set(`${edge.u}-${edge.v}`, edge)
      })

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
   * Update modified edges visualization with colors based on modification type
   */
  function updateModifiedEdges(): void {
    if (edgeGeometries.value.length === 0 || !baseLayer) return

    const modifications = trafficStore.edgeModifications

    // Group edges by modification type
    const modifiedEdgeData: Array<EdgeGeometry & { action: ModificationAction }> = []

    modifications.forEach((mod, key) => {
      const edge = edgeMap.value.get(key)
      if (edge) {
        modifiedEdgeData.push({ ...edge, action: mod.action })
      }
    })

    if (modifiedEdgeData.length === 0) {
      // Keep only base and route layers
      const routeLayers = layers.value.filter((l) => l.id.startsWith('traffic-routes'))
      layers.value = [baseLayer, ...routeLayers]
      return
    }

    // Create layer for modified edges with color based on action
    const modifiedLayer = new PathLayer({
      id: 'traffic-modified-edges',
      data: modifiedEdgeData,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: (d: EdgeGeometry & { action: ModificationAction }) => MODIFICATION_COLORS[d.action],
      getWidth: 12,
      widthUnits: 'pixels',
      getDashArray: (d: EdgeGeometry & { action: ModificationAction }) =>
        d.action === 'remove' ? [8, 4] : [0, 0], // Dashed for removed, solid for speed limits
      dashJustified: true,
      dashGapPickable: true,
      pickable: true,
      extensions: [new PathStyleExtension({ dash: true })]
    })

    // Keep route layers if they exist
    const routeLayers = layers.value.filter((l) => l.id.startsWith('traffic-routes'))

    // Modified edges on top
    layers.value = [baseLayer, ...routeLayers, modifiedLayer]
  }

  /**
   * Visualize edge usage statistics using delta frequency for color coding
   */
  function visualizeEdgeUsage(newUsage: EdgeUsageStats[]): void {
    clearRoutes()

    console.log('[DEBUG] visualizeEdgeUsage called')
    console.log('[DEBUG] newUsage length:', newUsage.length)
    console.log('[DEBUG] First 3 newUsage entries:', newUsage.slice(0, 3))

    // Use new usage stats (which include delta_count and co2_per_use)
    const edgesWithStats = newUsage
      .map((stat) => {
        const edge = edgeMap.value.get(`${stat.u}-${stat.v}`)
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

    // Sort edges by frequency (ascending) so larger edges are drawn last
    edgesWithStats.sort((a, b) => a.frequency - b.frequency)

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

    // Handle routes visualization separately with TripsLayer
    if (activeMode === 'routes') {
      visualizeRoutes()
      return
    }

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
    // Stop animation if running
    if (animationLoop.value !== null) {
      cancelAnimationFrame(animationLoop.value)
      animationLoop.value = null
    }
    animationTime.value = 0

    // Keep only the base graph edges and removed edges layers
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')
    layers.value = [baseLayer, removedLayer].filter(Boolean)
  }

  /**
   * Visualize routes as animated trips using TripsLayer
   */
  function visualizeRoutes(): void {
    const routes = trafficStore.routes
    if (!routes || routes.length === 0) return

    console.log(`[DEBUG] Visualizing ${routes.length} routes with TripsLayer`)
    let maxTimeTravel = 0

    // Prepare trips data for TripsLayer
    const trips = routes.map((route: Route, index: number) => {
      // Convert path (list of node IDs) to list of edges
      const nodeIds = route.path
      if (nodeIds.length < 2) return null

      // Build edges from consecutive node pairs
      const edges: Array<{ u: number; v: number }> = []
      for (let i = 0; i < nodeIds.length - 1; i++) {
        edges.push({ u: nodeIds[i], v: nodeIds[i + 1] })
      }

      // Aggregate coordinates and timestamps from all edges
      const coords: number[][] = []
      const timestamps: number[] = []
      let accumulatedTime = 0

      // Add time offset for visual staggering
      const timeOffset = (index % 20) * 20
      const randomOffsetWidth = 0.0005 * (Math.random() - 0.5) // Small random offset to avoid exact overlaps
      const randomOffsetHeight = 0.0005 * (Math.random() - 0.5) // Small random offset to avoid exact overlaps

      for (const edge of edges) {
        const edgeData = edgeMap.value.get(`${edge.u}-${edge.v}`)
        if (!edgeData) continue

        const edgeCoords = edgeData.coordinates
        const edgeTravelTime = edgeData.travel_time || 10 // Default 10s if not specified
        const numPoints = edgeCoords.length

        // For each coordinate in this edge, calculate its timestamp
        for (let i = 0; i < numPoints; i++) {
          // Skip first point of subsequent edges to avoid duplicates
          if (coords.length > 0 && i === 0) continue

          coords.push([edgeCoords[i][0] + randomOffsetWidth, edgeCoords[i][1] + randomOffsetHeight])
          // Timestamp increases proportionally within the edge
          const pointTime = accumulatedTime + (i / Math.max(1, numPoints - 1)) * edgeTravelTime
          timestamps.push(timeOffset + pointTime)
        }

        accumulatedTime += edgeTravelTime
      }

      if (coords.length === 0) return null

      // Vary colors using a vibrant palette for visual multiplicity
      const colorVariants = [
        [255, 107, 107], // Coral Red
        [78, 205, 196], // Turquoise
        [255, 195, 113], // Warm Yellow
        [162, 155, 254], // Soft Purple
        [255, 121, 198] // Hot Pink
      ]
      const color = colorVariants[index % colorVariants.length]

      // Vary width slightly (4-8 pixels)
      const width = 4 + (index % 5)

      maxTimeTravel = Math.max(maxTimeTravel, accumulatedTime)

      return {
        path: coords,
        timestamps: timestamps,
        color: color,
        width: width
      }
    })

    loopLength.value = maxTimeTravel

    console.log(
      `[DEBUG] Prepared ${trips.length} trips for visualization with animation time ${loopLength.value}`
    )
    if (trips.length > 0) {
      const firstTrip = trips[0] as any
      console.log(
        `[DEBUG] First trip: ${
          firstTrip.path.length
        } coords, timestamps range: ${firstTrip.timestamps[0].toFixed(1)} - ${firstTrip.timestamps[
          firstTrip.timestamps.length - 1
        ].toFixed(1)}`
      )
    }

    // Create TripsLayer
    const tripsLayer = new TripsLayer({
      id: 'traffic-routes-trips',
      data: trips,
      getPath: (d: any) => d.path,
      getTimestamps: (d: any) => d.timestamps,
      getColor: (d: any) => d.color,
      getWidth: (d: any) => d.width,
      opacity: 0.7,
      widthMinPixels: 4,
      jointRounded: true,
      capRounded: true,
      trailLength: trailLength,
      currentTime: animationTime.value,
      shadowEnabled: false
    })

    // Update layers
    const removedLayer = layers.value.find((l) => l.id === 'traffic-removed-edges')
    layers.value = [baseLayer, tripsLayer, ...(removedLayer ? [removedLayer] : [])].filter(Boolean)

    // Start animation loop
    startAnimation()
  }

  /**
   * Start the animation loop for TripsLayer
   */
  function startAnimation(): void {
    // Stop existing animation if any
    if (animationLoop.value !== null) {
      cancelAnimationFrame(animationLoop.value)
    }

    const startTime = Date.now()
    const animate = () => {
      const elapsed = (Date.now() - startTime) / 1000 // seconds
      animationTime.value = (elapsed * 40) % loopLength.value // Speed up by 40x for balanced movement

      // Update the trips layer with new time by recreating it
      const tripsLayerIndex = layers.value.findIndex((l) => l.id === 'traffic-routes-trips')
      if (tripsLayerIndex !== -1) {
        const oldLayer = layers.value[tripsLayerIndex]
        // Create new layer with updated currentTime
        const newLayer = oldLayer.clone({ currentTime: animationTime.value })
        layers.value = [
          ...layers.value.slice(0, tripsLayerIndex),
          newLayer,
          ...layers.value.slice(tripsLayerIndex + 1)
        ]
      }

      animationLoop.value = requestAnimationFrame(animate)
    }

    animationLoop.value = requestAnimationFrame(animate)
  }

  /**
   * Handle click events on edges
   */
  function handleClick(info: any): void {
    if (!info.object || !edgeClickCallback) return

    // Handle both GeoJSON features and direct edge objects
    const clickedEdge = info.object.properties || info.object
    if (clickedEdge.u === undefined || clickedEdge.v === undefined) return

    // Get edge name
    const edgeName = clickedEdge.name || `Edge ${clickedEdge.u}→${clickedEdge.v}`

    // Call callback with edge info including name
    edgeClickCallback(clickedEdge.u, clickedEdge.v, edgeName)

    // Also explicitly look for the reverse edge (u-v becomes v-u)
    const reverseEdge = edgeGeometries.value.find(
      (edge) => edge.u === clickedEdge.v && edge.v === clickedEdge.u
    )

    if (reverseEdge) {
      const reverseName = reverseEdge.name || `Edge ${reverseEdge.u}→${reverseEdge.v}`
      edgeClickCallback(reverseEdge.u!, reverseEdge.v!, reverseName)
    }
  }

  /**
   * Set callback for edge clicks
   */
  function setEdgeClickCallback(callback: (u: number, v: number, name?: string) => void): void {
    edgeClickCallback = callback
  }

  return {
    layers,
    loadGraphEdges,
    updateModifiedEdges,
    visualizeEdgeUsage,
    clearRoutes,
    handleClick,
    setEdgeClickCallback
  }
}
