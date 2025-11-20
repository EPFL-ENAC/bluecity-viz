import {
  fetchEdgeGeometries,
  getGraphTilesUrl,
  type EdgeGeometry
} from '@/services/trafficAnalysis'
import { TileLayer } from '@deck.gl/geo-layers'
import { GeoJsonLayer, PathLayer } from '@deck.gl/layers'
import { createDataSource } from '@loaders.gl/core'
import { PMTilesSource } from '@loaders.gl/pmtiles'
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

  // Cache the base layer to avoid recreating it (can be MVTLayer or PathLayer)
  let baseLayer: any = null

  /**
   * Load graph edges from PMTiles for efficient tile-based rendering
   */
  async function loadGraphEdges(): Promise<void> {
    try {
      console.time('Loading graph edges from PMTiles')

      // Load edge geometries for interaction (removed edges, routes)
      const edges = await fetchEdgeGeometries()
      edgeGeometries.value = edges
      console.log(`Loaded ${edges.length} edge geometries for interaction`)

      // Get PMTiles URL
      const tilesUrl = getGraphTilesUrl()
      const pmtilesUrl = `${window.location.origin}${tilesUrl}`

      // Create data source using loaders.gl pattern
      const tileSource: any = createDataSource(pmtilesUrl, [PMTilesSource], {})

      // Use TileLayer with getTileData from the source (following loaders.gl example)
      baseLayer = new TileLayer({
        id: 'traffic-graph-edges',
        getTileData: tileSource.getTileData.bind(tileSource),
        pickable: true,
        autoHighlight: true,
        highlightColor: [0, 170, 255, 200],
        minZoom: 0,
        maxZoom: 20,
        tileSize: 256,
        renderSubLayers: (props: any) => {
          if (!props.data) return null

          return new GeoJsonLayer({
            ...props,
            id: `${props.id}-geojson`,
            data: props.data,
            lineWidthMinPixels: 1,
            getLineColor: [136, 136, 136, 153],
            getLineWidth: 2,
            getFillColor: [136, 136, 136, 100],
            pickable: true,
            autoHighlight: true
          })
        }
      })

      console.timeEnd('Loading graph edges from PMTiles')

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
      getWidth: 5,
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

    // Create original routes layer (blue)
    const originalLayer = new PathLayer({
      id: 'traffic-original-routes',
      data: originalWithFreq,
      getPath: (d: EdgeGeometry) => d.coordinates,
      getColor: [33, 150, 243, 200], // Blue
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
            getColor: [255, 152, 0, 200], // Orange
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

    const edge = info.object as EdgeGeometry
    if (edge.u !== undefined && edge.v !== undefined) {
      edgeClickCallback(edge.u, edge.v)
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
