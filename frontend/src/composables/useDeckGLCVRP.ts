import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { computed, ref, type ShallowRef } from 'vue'
import { useCVRPStore, getVehicleColor } from '@/stores/cvrp'
import type { EdgeGeometry } from '@/services/trafficAnalysis'

export interface CVRPTooltipData {
  x: number
  y: number
  routeId: number
  loadKg: number
  maxLoad: number
  nTrips: number
}

/**
 * Composable that produces reactive Deck.gl layers for CVRP visualization.
 *
 * Returns:
 *  - ScatterplotLayer: waste collection centroids
 *  - PathLayer:        vehicle routes (color per vehicle, hover-highlighted)
 *  - PathLayer:        edge load heatmap (uses real street geometry from edgeMap)
 */
export function useDeckGLCVRP(edgeMap: ShallowRef<Map<string, EdgeGeometry>>) {
  const cvrpStore = useCVRPStore()
  const hoveredRouteId = ref<number | null>(null)
  const cvrpTooltipData = ref<CVRPTooltipData | null>(null)

  const layers = computed(() => {
    const result: any[] = []

    // --- Centroids layer ---
    if (cvrpStore.showCentroids && cvrpStore.centroids) {
      const centroidData = cvrpStore.centroids.features.map((f: any) => ({
        position: f.geometry.coordinates as [number, number],
        waste: f.properties?.centroid_waste ?? 0,
      }))

      result.push(
        new ScatterplotLayer({
          id: 'cvrp-centroids',
          data: centroidData,
          getPosition: (d: any) => d.position,
          getRadius: 20,
          radiusUnits: 'meters',
          radiusMinPixels: 3,
          radiusMaxPixels: 8,
          getFillColor: [34, 197, 94, 200], // green
          getLineColor: [22, 163, 74, 255],
          stroked: true,
          lineWidthMinPixels: 1,
          pickable: false,
        })
      )
    }

    if (!cvrpStore.hasResult || !cvrpStore.lastResult) return result

    const { route_segments, edge_loads } = cvrpStore.lastResult

    // Pre-compute per-route stats for tooltip
    const routeStats = new Map<number, { maxLoad: number; nTrips: number }>()
    route_segments.forEach((seg: any) => {
      const existing = routeStats.get(seg.route_id)
      if (!existing) {
        routeStats.set(seg.route_id, { maxLoad: seg.load_kg, nTrips: seg.trip_id + 1 })
      } else {
        existing.maxLoad = Math.max(existing.maxLoad, seg.load_kg)
        existing.nTrips = Math.max(existing.nTrips, seg.trip_id + 1)
      }
    })

    // --- Route paths layer (one per vehicle, color-coded, hover-highlighted) ---
    if (cvrpStore.visualizationMode === 'routes' && route_segments.length > 0) {
      const hovered = hoveredRouteId.value

      result.push(
        new PathLayer({
          id: 'cvrp-routes',
          data: route_segments,
          getPath: (d: any) => d.path_coordinates,
          getColor: (d: any) => {
            const color = getVehicleColor(d.route_id)
            if (hovered !== null && d.route_id !== hovered) {
              return [color[0], color[1], color[2], 50] as [number, number, number, number]
            }
            return color
          },
          getWidth: (d: any) => (hovered !== null && d.route_id === hovered ? 7 : 4),
          widthUnits: 'pixels',
          widthMinPixels: 2,
          widthMaxPixels: 12,
          pickable: true,
          opacity: 1,
          updateTriggers: {
            getColor: [hovered],
            getWidth: [hovered],
          },
          onHover: (info: any) => {
            if (info.object) {
              const stats = routeStats.get(info.object.route_id)
              hoveredRouteId.value = info.object.route_id
              cvrpTooltipData.value = {
                x: info.x,
                y: info.y,
                routeId: info.object.route_id,
                loadKg: info.object.load_kg,
                maxLoad: stats?.maxLoad ?? 0,
                nTrips: stats?.nTrips ?? 1,
              }
            } else {
              hoveredRouteId.value = null
              cvrpTooltipData.value = null
            }
          },
        })
      )
    }

    // --- Edge load heatmap layer ---
    if (cvrpStore.visualizationMode === 'heatmap' && edge_loads.length > 0) {
      const heatmapData: { path: number[][]; load: number }[] = []

      edge_loads.forEach((el: any) => {
        const edge = edgeMap.value.get(`${el.u}-${el.v}`)
        if (!edge) return
        heatmapData.push({ path: edge.coordinates, load: el.load })
      })

      result.push(
        new PathLayer({
          id: 'cvrp-edge-heatmap',
          data: heatmapData,
          getPath: (d: any) => d.path,
          getColor: (d: any) => cvrpStore.getEdgeLoadColor(d.load),
          getWidth: 6,
          widthUnits: 'pixels',
          widthMinPixels: 2,
          widthMaxPixels: 12,
          pickable: false,
        })
      )
    }

    return result
  })

  return { layers, cvrpTooltipData }
}
