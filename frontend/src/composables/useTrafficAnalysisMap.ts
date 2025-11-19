import { getGraphTilesUrl } from '@/services/trafficAnalysis'
import type { Map as MapLibre } from 'maplibre-gl'
import type { Ref } from 'vue'

interface EdgeUsageStats {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  delta_frequency?: number
}

interface TrafficAnalysisMapReturn {
  addGraphEdgesLayerFromTiles: () => void
  removeGraphEdgesLayer: () => void
  updateRemovedEdges: (removedEdges: { u: number; v: number }[]) => void
  visualizeEdgeUsage: (originalUsage: EdgeUsageStats[], newUsage: EdgeUsageStats[]) => void
  clearRoutes: () => void
  attachEdgeClickListener: (onEdgeClick: (u: number, v: number) => void) => void
  detachEdgeClickListener: () => void
}

/**
 * Composable for managing traffic analysis visualization on the map
 */
export function useTrafficAnalysisMap(mapRef: Ref<MapLibre | undefined>): TrafficAnalysisMapReturn {
  let edgeClickHandler: ((e: any) => void) | null = null
  let hoveredEdgeKey: string | null = null

  function addGraphEdgesLayerFromTiles(): void {
    if (!mapRef.value) return

    const map = mapRef.value
    const tilesUrl = getGraphTilesUrl()

    if (map.getLayer('traffic-graph-edges')) {
      map.removeLayer('traffic-graph-edges')
    }
    if (map.getSource('traffic-graph-edges')) {
      map.removeSource('traffic-graph-edges')
    }

    // Add PMTiles source
    map.addSource('traffic-graph-edges', {
      type: 'vector',
      url: `pmtiles://${tilesUrl}`,
      promoteId: { graph_edges: 'edge_id' }
    })

    // Add base layer
    map.addLayer({
      id: 'traffic-graph-edges',
      type: 'line',
      source: 'traffic-graph-edges',
      'source-layer': 'graph_edges',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#888',
        'line-width': 2,
        'line-opacity': 0.6
      }
    })

    // Add hover highlight layer
    map.addLayer({
      id: 'traffic-graph-edges-hover',
      type: 'line',
      source: 'traffic-graph-edges',
      'source-layer': 'graph_edges',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#00aaff',
        'line-width': 4,
        'line-opacity': 0
      }
    })

    // Handle hover effect
    map.on('mousemove', 'traffic-graph-edges', (e) => {
      map.getCanvas().style.cursor = 'pointer'

      if (e.features && e.features.length > 0) {
        const feature = e.features[0]
        const u = feature.properties?.u
        const v = feature.properties?.v
        const newHoveredKey = `${u}-${v}`

        if (hoveredEdgeKey !== newHoveredKey) {
          hoveredEdgeKey = newHoveredKey

          // Update hover layer filter
          map.setPaintProperty('traffic-graph-edges-hover', 'line-opacity', [
            'case',
            ['all', ['==', ['get', 'u'], u], ['==', ['get', 'v'], v]],
            1,
            0
          ])
        }
      }
    })

    map.on('mouseleave', 'traffic-graph-edges', () => {
      map.getCanvas().style.cursor = ''
      hoveredEdgeKey = null

      // Clear hover layer
      map.setPaintProperty('traffic-graph-edges-hover', 'line-opacity', 0)
    })
  }

  /**
   * Remove graph edges layer from the map
   */
  function removeGraphEdgesLayer(): void {
    if (!mapRef.value) return

    const map = mapRef.value

    if (map.getLayer('traffic-removed-edges')) {
      map.removeLayer('traffic-removed-edges')
    }
    if (map.getLayer('traffic-graph-edges-hover')) {
      map.removeLayer('traffic-graph-edges-hover')
    }
    if (map.getLayer('traffic-graph-edges')) {
      map.removeLayer('traffic-graph-edges')
    }
    if (map.getSource('traffic-graph-edges')) {
      map.removeSource('traffic-graph-edges')
    }
  }

  /**
   * Update removed edges visualization
   */
  function updateRemovedEdges(removedEdges: { u: number; v: number }[]): void {
    if (!mapRef.value) return

    const map = mapRef.value

    // Remove existing removed edges layer
    if (map.getLayer('traffic-removed-edges')) {
      map.removeLayer('traffic-removed-edges')
    }

    if (removedEdges.length === 0) return

    // Build filter expression to match removed edges
    const filterExpression = ['any'] as any

    for (const edge of removedEdges) {
      filterExpression.push(['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]])
    }

    // Add removed edges layer using the same vector source with a filter
    map.addLayer({
      id: 'traffic-removed-edges',
      type: 'line',
      source: 'traffic-graph-edges',
      'source-layer': 'graph_edges',
      filter: filterExpression as any,
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#ff0000',
        'line-width': 5,
        'line-opacity': 0.9,
        'line-dasharray': [2, 2]
      }
    })
  }

  /**
   * Visualize edge usage statistics on the map
   */
  function visualizeEdgeUsage(originalUsage: EdgeUsageStats[], newUsage: EdgeUsageStats[]): void {
    if (!mapRef.value) return

    const map = mapRef.value

    // Clear existing route layers
    clearRoutes()

    // Build filter expressions for original and new edge usage
    const originalFilterExpression = ['any'] as any
    const newFilterExpression = ['any'] as any

    // Create lookup maps for frequencies
    const originalFrequencyMap = new Map<string, number>()
    const newFrequencyMap = new Map<string, number>()

    originalUsage.forEach((edge) => {
      const key = `${edge.u}-${edge.v}`
      originalFrequencyMap.set(key, edge.frequency)
      originalFilterExpression.push([
        'all',
        ['==', ['get', 'u'], edge.u],
        ['==', ['get', 'v'], edge.v]
      ])
    })

    newUsage.forEach((edge) => {
      const key = `${edge.u}-${edge.v}`
      newFrequencyMap.set(key, edge.frequency)
      newFilterExpression.push(['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]])
    })

    // Add original edge usage layer
    if (originalUsage.length > 0) {
      // Build expression for dynamic opacity based on frequency
      const opacityExpression = ['case'] as any
      originalUsage.forEach((edge) => {
        opacityExpression.push(
          ['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]],
          edge.frequency * 20 + 0.01 // Scale between 0.2 and 0.9
        )
      })
      opacityExpression.push(0.2) // Default

      const widthExpression = ['case'] as any
      originalUsage.forEach((edge) => {
        widthExpression.push(
          ['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]],
          edge.frequency * 100 + 10 // Scale between 2 and 6
        )
      })
      widthExpression.push(2) // Default

      map.addLayer({
        id: 'traffic-original-routes',
        type: 'line',
        source: 'traffic-graph-edges',
        'source-layer': 'graph_edges',
        filter: originalFilterExpression,
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#2196F3',
          'line-width': widthExpression,
          'line-opacity': opacityExpression
        }
      })
    }

    // Add new edge usage layer (only if edges were removed)
    if (newUsage.length > 0 && newUsage.length !== originalUsage.length) {
      const opacityExpression = ['case'] as any
      newUsage.forEach((edge) => {
        opacityExpression.push(
          ['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]],
          edge.frequency * 20 + 0.01
        )
      })
      opacityExpression.push(0.2)

      const widthExpression = ['case'] as any
      newUsage.forEach((edge) => {
        widthExpression.push(
          ['all', ['==', ['get', 'u'], edge.u], ['==', ['get', 'v'], edge.v]],
          edge.frequency * 100 + 10
        )
      })
      widthExpression.push(2)

      map.addLayer({
        id: 'traffic-new-routes',
        type: 'line',
        source: 'traffic-graph-edges',
        'source-layer': 'graph_edges',
        filter: newFilterExpression,
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#FF9800',
          'line-width': widthExpression,
          'line-opacity': opacityExpression
        }
      })
    }
  }
  /**
   * Clear all route visualizations
   */
  function clearRoutes(): void {
    if (!mapRef.value) return

    const map = mapRef.value

    const routeLayers = ['traffic-original-routes', 'traffic-new-routes']

    routeLayers.forEach((layerId) => {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId)
      }
    })
  }

  /**
   * Attach click listener for edge selection
   */
  function attachEdgeClickListener(onEdgeClick: (u: number, v: number) => void): void {
    if (!mapRef.value) return

    const map = mapRef.value

    // Remove existing handler
    detachEdgeClickListener()

    // Create new handler
    edgeClickHandler = (e: any) => {
      if (!e.features || e.features.length === 0) return

      const feature = e.features[0]
      const u = feature.properties?.u
      const v = feature.properties?.v

      if (u !== undefined && v !== undefined) {
        onEdgeClick(u, v)
      }
    }

    map.on('click', 'traffic-graph-edges', edgeClickHandler)
  }

  /**
   * Detach click listener for edge selection
   */
  function detachEdgeClickListener(): void {
    if (!mapRef.value || !edgeClickHandler) return

    const map = mapRef.value
    map.off('click', 'traffic-graph-edges', edgeClickHandler)
    edgeClickHandler = null
  }

  return {
    addGraphEdgesLayerFromTiles,
    removeGraphEdgesLayer,
    updateRemovedEdges,
    visualizeEdgeUsage,
    clearRoutes,
    attachEdgeClickListener,
    detachEdgeClickListener
  }
}
