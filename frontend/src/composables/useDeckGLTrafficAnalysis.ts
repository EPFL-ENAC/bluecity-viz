import { fetchEdgeGeometries, type EdgeGeometry, type Route } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore, type ModificationAction } from '@/stores/trafficAnalysis'
import { PathStyleExtension } from '@deck.gl/extensions'
import { TripsLayer } from '@deck.gl/geo-layers'
import { GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers'
import type { Ref } from 'vue'
import { ref, shallowRef } from 'vue'

// Colors for different modification types (matching MapControlsPanel actionColors)
const MODIFICATION_COLORS: Record<ModificationAction, [number, number, number, number]> = {
  remove: [0, 0, 0, 255], // Black for removed (#000000)
  speed50: [220, 38, 38, 255], // Red for 50 km/h (#dc2626)
  speed30: [251, 146, 60, 255], // Orange for 30 km/h (#fb923c)
  speed10: [250, 204, 21, 255] // Yellow for 10 km/h (#facc15)
}

// Speed limit text for each action
const SPEED_LIMIT_TEXT: Record<ModificationAction, string> = {
  remove: '✕',
  speed10: '10',
  speed30: '30',
  speed50: '50'
}

// Helper to get midpoint of a path
function getPathMidpoint(coordinates: number[][]): [number, number] {
  if (coordinates.length === 0) return [0, 0]
  if (coordinates.length === 1) return [coordinates[0][0], coordinates[0][1]]

  // Calculate total length and find midpoint
  let totalLength = 0
  const segmentLengths: number[] = []

  for (let i = 1; i < coordinates.length; i++) {
    const dx = coordinates[i][0] - coordinates[i - 1][0]
    const dy = coordinates[i][1] - coordinates[i - 1][1]
    const len = Math.sqrt(dx * dx + dy * dy)
    segmentLengths.push(len)
    totalLength += len
  }

  const halfLength = totalLength / 2
  let accumulated = 0

  for (let i = 0; i < segmentLengths.length; i++) {
    if (accumulated + segmentLengths[i] >= halfLength) {
      const ratio = (halfLength - accumulated) / segmentLengths[i]
      const x = coordinates[i][0] + ratio * (coordinates[i + 1][0] - coordinates[i][0])
      const y = coordinates[i][1] + ratio * (coordinates[i + 1][1] - coordinates[i][1])
      return [x, y]
    }
    accumulated += segmentLengths[i]
  }

  const last = coordinates[coordinates.length - 1]
  return [last[0], last[1]]
}

// Helper to compute offset path (parallel line at given distance)
// offsetMeters is approximate - we convert to degrees roughly
function computeOffsetPath(coordinates: number[][], offsetMeters: number): number[][] {
  if (coordinates.length < 2) return coordinates

  // Rough conversion: 1 degree ≈ 111,000 meters at equator
  // For latitude ~46° (Lausanne), longitude degree ≈ 77,000 meters
  const metersPerDegreeLat = 111000
  const metersPerDegreeLon = 77000

  const offsetPath: number[][] = []

  for (let i = 0; i < coordinates.length; i++) {
    let nx = 0,
      ny = 0

    if (i === 0) {
      // First point: use direction to next point
      const dx = coordinates[1][0] - coordinates[0][0]
      const dy = coordinates[1][1] - coordinates[0][1]
      const len = Math.sqrt(dx * dx + dy * dy)
      if (len > 0) {
        nx = -dy / len
        ny = dx / len
      }
    } else if (i === coordinates.length - 1) {
      // Last point: use direction from previous point
      const dx = coordinates[i][0] - coordinates[i - 1][0]
      const dy = coordinates[i][1] - coordinates[i - 1][1]
      const len = Math.sqrt(dx * dx + dy * dy)
      if (len > 0) {
        nx = -dy / len
        ny = dx / len
      }
    } else {
      // Middle points: average normals from both segments
      const dx1 = coordinates[i][0] - coordinates[i - 1][0]
      const dy1 = coordinates[i][1] - coordinates[i - 1][1]
      const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1)

      const dx2 = coordinates[i + 1][0] - coordinates[i][0]
      const dy2 = coordinates[i + 1][1] - coordinates[i][1]
      const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2)

      if (len1 > 0 && len2 > 0) {
        const nx1 = -dy1 / len1
        const ny1 = dx1 / len1
        const nx2 = -dy2 / len2
        const ny2 = dx2 / len2
        nx = (nx1 + nx2) / 2
        ny = (ny1 + ny2) / 2
        // Normalize
        const nlen = Math.sqrt(nx * nx + ny * ny)
        if (nlen > 0) {
          nx /= nlen
          ny /= nlen
        }
      }
    }

    // Apply offset in degrees
    const offsetLon = (offsetMeters / metersPerDegreeLon) * nx
    const offsetLat = (offsetMeters / metersPerDegreeLat) * ny

    offsetPath.push([coordinates[i][0] + offsetLon, coordinates[i][1] + offsetLat])
  }

  return offsetPath
}

// Create hull outline paths (left and right offset + end caps)
function createHullPaths(coordinates: number[][], widthMeters: number): number[][][] {
  const halfWidth = widthMeters / 2
  const leftPath = computeOffsetPath(coordinates, halfWidth)
  const rightPath = computeOffsetPath(coordinates, -halfWidth)

  // Return as separate paths for the two sides
  return [leftPath, rightPath]
}

interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  co2_per_use?: number
}

// Tooltip data structure
export interface EdgeTooltipData {
  x: number
  y: number
  name: string
  highway?: string
  length?: number
  travel_time?: number
  speed_kph?: number
  // Route calculation stats (when available)
  frequency?: number
  count?: number
  delta_count?: number
  co2_per_use?: number
  co2_total?: number
  co2_delta?: number
}

interface DeckGLTrafficAnalysisReturn {
  layers: Ref<any[]>
  tooltipData: Ref<EdgeTooltipData | null>
  loadGraphEdges: () => Promise<void>
  updateModifiedEdges: () => void
  visualizeEdgeUsage: (newUsage: EdgeUsageStats[]) => void
  clearRoutes: () => void
  handleClick: (info: any) => void
  handleHover: (info: any) => void
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

  // Tooltip state
  const tooltipData = ref<EdgeTooltipData | null>(null)

  // Cache for edge stats from route calculation
  const edgeStatsMap = shallowRef<Map<string, EdgeUsageStats>>(new Map())

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
   * Update modified edges visualization with hollow outlines and speed limit icons
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

    // Create hull outline data - compute offset paths for each edge
    // Hull width in meters - will scale naturally with zoom
    const hullWidth = 8 // meters
    const hullPathsData: Array<{ path: number[][]; color: [number, number, number, number] }> = []

    for (const edge of modifiedEdgeData) {
      const [leftPath, rightPath] = createHullPaths(edge.coordinates, hullWidth)
      const color = MODIFICATION_COLORS[edge.action]
      hullPathsData.push({ path: leftPath, color })
      hullPathsData.push({ path: rightPath, color })
    }

    // Create hull outline layer with dashed lines
    // Use meters for width so it scales with zoom
    const hullOutlineLayer = new PathLayer({
      id: 'traffic-modified-edges-hull',
      data: hullPathsData,
      getPath: (d: any) => d.path,
      getColor: (d: any) => d.color,
      getWidth: 2, // meters
      widthUnits: 'meters',
      widthMinPixels: 2,
      widthMaxPixels: 8,
      getDashArray: [6, 4],
      dashJustified: true,
      pickable: false,
      extensions: [new PathStyleExtension({ dash: true })]
    })

    // Create end caps as small perpendicular lines at start and end of each edge
    const endCapData: Array<{ path: number[][]; color: [number, number, number, number] }> = []
    for (const edge of modifiedEdgeData) {
      const coords = edge.coordinates
      if (coords.length < 2) continue

      const color = MODIFICATION_COLORS[edge.action]
      const [leftPath, rightPath] = createHullPaths(coords, hullWidth)

      // Start cap: connect left[0] to right[0]
      endCapData.push({
        path: [leftPath[0], rightPath[0]],
        color
      })

      // End cap: connect left[last] to right[last]
      endCapData.push({
        path: [leftPath[leftPath.length - 1], rightPath[rightPath.length - 1]],
        color
      })
    }

    // Create end caps layer
    const endCapsLayer = new PathLayer({
      id: 'traffic-modified-edges-caps',
      data: endCapData,
      getPath: (d: any) => d.path,
      getColor: (d: any) => d.color,
      getWidth: 2, // meters - same as hull outline
      widthUnits: 'meters',
      widthMinPixels: 2,
      widthMaxPixels: 8,
      pickable: false
    })

    // Prepare data for speed limit icons (for speed modifications)
    // European speed limit signs: white circle with red border, black text
    const speedLimitData = modifiedEdgeData
      .filter((d) => d.action !== 'remove')
      .map((d) => ({
        position: getPathMidpoint(d.coordinates),
        text: SPEED_LIMIT_TEXT[d.action],
        action: d.action
      }))

    // Prepare data for removed edge icons (black circle with white X)
    const removedEdgeData = modifiedEdgeData
      .filter((d) => d.action === 'remove')
      .map((d) => ({
        position: getPathMidpoint(d.coordinates)
      }))

    // Create text layer for speed limit icons (European style: white bg, red border, black text)
    const speedLimitLayer = new TextLayer({
      id: 'traffic-modified-edges-speed-icons',
      data: speedLimitData,
      getPosition: (d: any) => d.position,
      getText: (d: any) => d.text,
      getColor: [0, 0, 0, 255], // Black text
      getSize: 12,
      fontWeight: 'bold',
      getBackgroundColor: [255, 255, 255, 255], // White background
      background: true,
      backgroundPadding: [6, 4, 6, 4],
      backgroundBorderRadius: 30,
      getBorderColor: [220, 38, 38, 255], // Red border (European style)
      getBorderWidth: 3,
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      fontFamily: 'Arial, sans-serif',
      billboard: true, // Always face camera
      sizeUnits: 'pixels',
      pickable: false
    })

    // Create text layer for removed edge icons (black circle with white X - "no entry" style)
    const removedEdgeLayer = new TextLayer({
      id: 'traffic-modified-edges-removed-icons',
      data: removedEdgeData,
      getPosition: (d: any) => d.position,
      getText: () => '✕',
      getColor: [255, 255, 255, 255], // White X
      getSize: 12,
      fontWeight: 'bold',
      getBackgroundColor: [0, 0, 0, 255], // Black background
      background: true,
      backgroundPadding: [6, 6, 6, 6],
      backgroundBorderRadius: 30, // Circular
      getBorderColor: [0, 0, 0, 255], // Black border
      getBorderWidth: 2,
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      fontFamily: 'Arial, sans-serif',
      billboard: true,
      sizeUnits: 'pixels',
      pickable: false
    })

    // Keep route layers if they exist
    const routeLayers = layers.value.filter((l) => l.id.startsWith('traffic-routes'))

    // Stack: base → routes → hull outline → end caps → speed icons → removed icons
    layers.value = [
      baseLayer,
      ...routeLayers,
      hullOutlineLayer,
      endCapsLayer,
      speedLimitLayer,
      removedEdgeLayer
    ]
  }

  /**
   * Visualize edge usage statistics using delta frequency for color coding
   */
  function visualizeEdgeUsage(newUsage: EdgeUsageStats[]): void {
    clearRoutes()

    console.log('[DEBUG] visualizeEdgeUsage called')
    console.log('[DEBUG] newUsage length:', newUsage.length)
    console.log('[DEBUG] First 3 newUsage entries:', newUsage.slice(0, 3))

    // Cache edge stats for tooltip display
    const statsMap = new Map<string, EdgeUsageStats>()
    newUsage.forEach((stat) => {
      statsMap.set(`${stat.u}-${stat.v}`, stat)
    })
    edgeStatsMap.value = statsMap

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

    // Preserve modified edges layers (hull, caps, speed icons)
    const modifiedEdgesLayers = layers.value.filter((l) =>
      l.id.startsWith('traffic-modified-edges')
    )

    layers.value = [baseLayer, outlineLayer, trafficLayer, ...modifiedEdgesLayers].filter(Boolean)
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

    // Keep base layer and modified edges layers
    const modifiedEdgesLayers = layers.value.filter((l) =>
      l.id.startsWith('traffic-modified-edges')
    )
    layers.value = [baseLayer, ...modifiedEdgesLayers].filter(Boolean)
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

    // Preserve modified edges layers
    const modifiedEdgesLayers = layers.value.filter((l) =>
      l.id.startsWith('traffic-modified-edges')
    )
    layers.value = [baseLayer, tripsLayer, ...modifiedEdgesLayers].filter(Boolean)

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
   * Handle hover events on edges to show tooltips
   */
  function handleHover(info: any): void {
    if (!info.object) {
      tooltipData.value = null
      return
    }

    // Handle both GeoJSON features and direct edge objects
    const hoveredEdge = info.object.properties || info.object
    if (hoveredEdge.u === undefined || hoveredEdge.v === undefined) {
      tooltipData.value = null
      return
    }

    const edgeKey = `${hoveredEdge.u}-${hoveredEdge.v}`
    const edgeGeom = edgeMap.value.get(edgeKey)
    const edgeStats = edgeStatsMap.value.get(edgeKey)

    // Calculate speed from length and travel_time if available
    const length = hoveredEdge.length || edgeGeom?.length
    const travelTime = hoveredEdge.travel_time || edgeGeom?.travel_time
    let speedKph: number | undefined
    if (length && travelTime && travelTime > 0) {
      speedKph = Math.round(length / 1000 / (travelTime / 3600)) // km/h
    }

    tooltipData.value = {
      x: info.x,
      y: info.y,
      name: hoveredEdge.name || edgeGeom?.name || `Edge ${hoveredEdge.u}→${hoveredEdge.v}`,
      highway: hoveredEdge.highway || edgeGeom?.highway,
      length: length,
      travel_time: travelTime,
      speed_kph: speedKph,
      // Add route stats if available
      frequency: edgeStats?.frequency ?? hoveredEdge.frequency,
      count: edgeStats?.count ?? hoveredEdge.count,
      delta_count: edgeStats?.delta_count ?? hoveredEdge.delta_count,
      co2_per_use: edgeStats?.co2_per_use ?? hoveredEdge.co2_per_use,
      co2_total: hoveredEdge.co2_total,
      co2_delta: hoveredEdge.co2_delta
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
    tooltipData,
    loadGraphEdges,
    updateModifiedEdges,
    visualizeEdgeUsage,
    clearRoutes,
    handleClick,
    handleHover,
    setEdgeClickCallback
  }
}
