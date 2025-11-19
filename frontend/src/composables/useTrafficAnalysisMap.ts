import type { GraphEdge, RouteComparison } from '@/stores/trafficAnalysis'
import type { Map as MapLibre } from 'maplibre-gl'
import type { Ref } from 'vue'

interface TrafficAnalysisMapReturn {
  addGraphEdgesLayer: (edges: GraphEdge[]) => void
  removeGraphEdgesLayer: () => void
  updateRemovedEdges: (removedEdges: { u: number; v: number }[]) => void
  visualizeRoutes: (comparisons: RouteComparison[]) => void
  clearRoutes: () => void
  attachEdgeClickListener: (onEdgeClick: (u: number, v: number) => void) => void
  detachEdgeClickListener: () => void
}

/**
 * Composable for managing traffic analysis visualization on the map
 */
export function useTrafficAnalysisMap(mapRef: Ref<MapLibre | undefined>): TrafficAnalysisMapReturn {
  let edgeClickHandler: ((e: any) => void) | null = null

  /**
   * Add graph edges layer to the map
   */
  function addGraphEdgesLayer(edges: GraphEdge[]): void {
    if (!mapRef.value) return

    const map = mapRef.value

    // Create GeoJSON for all graph edges
    const geojson = {
      type: 'FeatureCollection' as const,
      features: edges.map((edge) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'LineString' as const,
          coordinates: edge.geometry.coordinates
        },
        properties: {
          u: edge.u,
          v: edge.v,
          name: edge.name || 'Unknown',
          highway: edge.highway || 'Unknown',
          speed_kph: edge.speed_kph || 0,
          length: edge.length || 0,
          travel_time: edge.travel_time || 0
        }
      }))
    }

    // Remove existing layers/sources if they exist
    if (map.getLayer('traffic-graph-edges')) {
      map.removeLayer('traffic-graph-edges')
    }
    if (map.getLayer('traffic-graph-edges-hover')) {
      map.removeLayer('traffic-graph-edges-hover')
    }
    if (map.getSource('traffic-graph-edges')) {
      map.removeSource('traffic-graph-edges')
    }

    // Add source
    map.addSource('traffic-graph-edges', {
      type: 'geojson',
      data: geojson
    })

    // Add base layer
    map.addLayer({
      id: 'traffic-graph-edges',
      type: 'line',
      source: 'traffic-graph-edges',
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

    // Add hover layer
    map.addLayer({
      id: 'traffic-graph-edges-hover',
      type: 'line',
      source: 'traffic-graph-edges',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#00f',
        'line-width': 4,
        'line-opacity': 0
      }
    })

    // Add hover effect
    map.on('mouseenter', 'traffic-graph-edges', () => {
      map.getCanvas().style.cursor = 'pointer'
    })

    map.on('mouseleave', 'traffic-graph-edges', () => {
      map.getCanvas().style.cursor = ''
    })

    map.on('mousemove', 'traffic-graph-edges', (e) => {
      if (e.features && e.features.length > 0) {
        const feature = e.features[0]
        map.setPaintProperty('traffic-graph-edges-hover', 'line-opacity', [
          'case',
          [
            'all',
            ['==', ['get', 'u'], feature.properties?.u],
            ['==', ['get', 'v'], feature.properties?.v]
          ],
          1,
          0
        ])
      }
    })
  }

  /**
   * Remove graph edges layer from the map
   */
  function removeGraphEdgesLayer(): void {
    if (!mapRef.value) return

    const map = mapRef.value

    if (map.getLayer('traffic-graph-edges')) {
      map.removeLayer('traffic-graph-edges')
    }
    if (map.getLayer('traffic-graph-edges-hover')) {
      map.removeLayer('traffic-graph-edges-hover')
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
    if (map.getSource('traffic-removed-edges')) {
      map.removeSource('traffic-removed-edges')
    }

    if (removedEdges.length === 0) return

    // Get the edges data from the graph source
    const graphSource = map.getSource('traffic-graph-edges') as any
    if (!graphSource) return

    const graphData = graphSource._data
    if (!graphData || !graphData.features) return

    // Filter edges that are in removedEdges
    const removedEdgesSet = new Set(removedEdges.map((e) => `${e.u}-${e.v}`))
    const removedFeatures = graphData.features.filter((feature: any) => {
      const key = `${feature.properties.u}-${feature.properties.v}`
      return removedEdgesSet.has(key)
    })

    // Add removed edges layer
    map.addSource('traffic-removed-edges', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection' as const,
        features: removedFeatures
      }
    })

    map.addLayer({
      id: 'traffic-removed-edges',
      type: 'line',
      source: 'traffic-removed-edges',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#000',
        'line-width': 4,
        'line-opacity': 1,
        'line-dasharray': [2, 2]
      }
    })
  }

  /**
   * Visualize calculated routes
   */
  function visualizeRoutes(comparisons: RouteComparison[]): void {
    if (!mapRef.value) return

    const map = mapRef.value

    // Clear existing route layers
    clearRoutes()

    // Create features for original routes
    const originalFeatures = comparisons
      .filter((c) => c.original_route.geometry)
      .map((comparison, index) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'LineString' as const,
          coordinates: comparison.original_route.geometry!.coordinates
        },
        properties: {
          type: 'original',
          index,
          origin: comparison.origin,
          destination: comparison.destination
        }
      }))

    // Create features for new routes
    const newFeatures = comparisons
      .filter((c) => c.new_route.geometry)
      .map((comparison, index) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'LineString' as const,
          coordinates: comparison.new_route.geometry!.coordinates
        },
        properties: {
          type: 'new',
          index,
          origin: comparison.origin,
          destination: comparison.destination
        }
      }))

    // Add original routes layer (faded)
    if (originalFeatures.length > 0) {
      map.addSource('traffic-original-routes', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection' as const,
          features: originalFeatures
        }
      })

      map.addLayer({
        id: 'traffic-original-routes',
        type: 'line',
        source: 'traffic-original-routes',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': [
            'case',
            ['==', ['%', ['get', 'index'], 5], 0],
            '#ff0000',
            ['==', ['%', ['get', 'index'], 5], 1],
            '#00ff00',
            ['==', ['%', ['get', 'index'], 5], 2],
            '#0000ff',
            ['==', ['%', ['get', 'index'], 5], 3],
            '#ffff00',
            '#ff00ff'
          ],
          'line-width': 4,
          'line-opacity': 0.3
        }
      })
    }

    // Add new routes layer (bright)
    if (newFeatures.length > 0) {
      map.addSource('traffic-new-routes', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection' as const,
          features: newFeatures
        }
      })

      map.addLayer({
        id: 'traffic-new-routes',
        type: 'line',
        source: 'traffic-new-routes',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': [
            'case',
            ['==', ['%', ['get', 'index'], 5], 0],
            '#ff0000',
            ['==', ['%', ['get', 'index'], 5], 1],
            '#00ff00',
            ['==', ['%', ['get', 'index'], 5], 2],
            '#0000ff',
            ['==', ['%', ['get', 'index'], 5], 3],
            '#ffff00',
            '#ff00ff'
          ],
          'line-width': 6,
          'line-opacity': 1
        }
      })
    }

    // Add origin/destination markers
    const markerFeatures = comparisons.flatMap((comparison) => {
      const markers = []

      if (comparison.original_route.geometry) {
        const coords = comparison.original_route.geometry.coordinates
        markers.push({
          type: 'Feature' as const,
          geometry: {
            type: 'Point' as const,
            coordinates: coords[0]
          },
          properties: {
            type: 'origin',
            nodeId: comparison.origin
          }
        })
        markers.push({
          type: 'Feature' as const,
          geometry: {
            type: 'Point' as const,
            coordinates: coords[coords.length - 1]
          },
          properties: {
            type: 'destination',
            nodeId: comparison.destination
          }
        })
      }

      return markers
    })

    if (markerFeatures.length > 0) {
      map.addSource('traffic-route-markers', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection' as const,
          features: markerFeatures
        }
      })

      map.addLayer({
        id: 'traffic-route-markers',
        type: 'circle',
        source: 'traffic-route-markers',
        paint: {
          'circle-radius': 6,
          'circle-color': ['case', ['==', ['get', 'type'], 'origin'], '#00ff00', '#ff0000'],
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 2
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

    const routeLayers = ['traffic-original-routes', 'traffic-new-routes', 'traffic-route-markers']

    routeLayers.forEach((layerId) => {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId)
      }
      if (map.getSource(layerId)) {
        map.removeSource(layerId)
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
    addGraphEdgesLayer,
    removeGraphEdgesLayer,
    updateRemovedEdges,
    visualizeRoutes,
    clearRoutes,
    attachEdgeClickListener,
    detachEdgeClickListener
  }
}
