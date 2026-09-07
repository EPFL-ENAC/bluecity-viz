import { edgeKey } from '@/composables/useGraphEdges'
import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { getVehicleColor, useCVRPStore } from '@/stores/cvrp'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { computed, ref, shallowRef, type ShallowRef } from 'vue'

/** What the CVRP route tooltip shows. Like the edge tooltip, no x and y: the
 *  position is written straight to the element. */
export interface CVRPTooltipData {
  routeId: number
  loadKg: number
  maxLoad: number
  nTrips: number
}

export type TooltipMover = (x: number, y: number) => void

interface Centroid {
  position: [number, number]
  waste: number
}

interface HeatmapEdge {
  path: [number, number][]
  load: number
}

const getCentroidPosition = (d: Centroid) => d.position
const getRoutePath = (d: any) => d.path_coordinates
const getHeatmapPath = (d: HeatmapEdge) => d.path

/**
 * Deck.gl layers for the CVRP visualization.
 *
 *  - ScatterplotLayer: waste collection centroids
 *  - PathLayer:        vehicle routes (color per vehicle, hover-highlighted)
 *  - PathLayer:        edge load heatmap (uses real street geometry from edgeMap)
 *
 * The three data arrays are their own computeds and none of them reads the
 * hovered route, so hovering a vehicle only flips two updateTriggers instead of
 * rebuilding every array and making deck upload it all again.
 */
export function useDeckGLCVRP(edgeMap: ShallowRef<Map<string, EdgeGeometry>>) {
  const cvrpStore = useCVRPStore()
  const hoveredRouteId = ref<number | null>(null)
  const cvrpTooltipData = shallowRef<CVRPTooltipData | null>(null)
  let mover: TooltipMover | null = null

  function setTooltipMover(fn: TooltipMover | null): void {
    mover = fn
  }

  const centroidData = computed<Centroid[]>(() => {
    const centroids = cvrpStore.centroids
    if (!cvrpStore.showCentroids || !centroids) return []
    return centroids.features.map((f: any) => ({
      position: f.geometry.coordinates as [number, number],
      waste: f.properties?.centroid_waste ?? 0
    }))
  })

  const routeSegments = computed<any[]>(() => cvrpStore.lastResult?.route_segments ?? [])

  /** Peak load and number of trips per vehicle, for the tooltip. */
  const routeStats = computed(() => {
    const stats = new Map<number, { maxLoad: number; nTrips: number }>()
    for (const seg of routeSegments.value) {
      const existing = stats.get(seg.route_id)
      if (!existing) {
        stats.set(seg.route_id, { maxLoad: seg.load_kg, nTrips: seg.trip_id + 1 })
      } else {
        existing.maxLoad = Math.max(existing.maxLoad, seg.load_kg)
        existing.nTrips = Math.max(existing.nTrips, seg.trip_id + 1)
      }
    }
    return stats
  })

  const heatmapData = computed<HeatmapEdge[]>(() => {
    const loads = cvrpStore.lastResult?.edge_loads ?? []
    const map = edgeMap.value
    if (loads.length === 0 || map.size === 0) return []

    const out: HeatmapEdge[] = []
    for (const el of loads as any[]) {
      const edge = map.get(edgeKey(el.u, el.v))
      if (!edge) continue
      out.push({ path: edge.coordinates, load: el.load })
    }
    return out
  })

  function handleRouteHover(info: any): void {
    if (!info.object) {
      if (hoveredRouteId.value !== null) {
        hoveredRouteId.value = null
        cvrpTooltipData.value = null
      }
      return
    }

    mover?.(info.x, info.y)

    const routeId = info.object.route_id
    if (routeId === hoveredRouteId.value) return

    hoveredRouteId.value = routeId
    const stats = routeStats.value.get(routeId)
    cvrpTooltipData.value = {
      routeId,
      loadKg: info.object.load_kg,
      maxLoad: stats?.maxLoad ?? 0,
      nTrips: stats?.nTrips ?? 1
    }
  }

  const layers = computed(() => {
    const result: any[] = []

    const centroids = centroidData.value
    if (centroids.length > 0) {
      result.push(
        new ScatterplotLayer({
          id: 'cvrp-centroids',
          data: centroids,
          getPosition: getCentroidPosition,
          getRadius: 20,
          radiusUnits: 'meters',
          radiusMinPixels: 3,
          radiusMaxPixels: 8,
          getFillColor: [34, 197, 94, 200], // green
          getLineColor: [22, 163, 74, 255],
          stroked: true,
          lineWidthMinPixels: 1,
          pickable: false
        })
      )
    }

    if (!cvrpStore.hasResult) return result

    const hovered = hoveredRouteId.value
    const segments = routeSegments.value

    if (cvrpStore.visualizationMode === 'routes' && segments.length > 0) {
      result.push(
        new PathLayer({
          id: 'cvrp-routes',
          data: segments,
          getPath: getRoutePath,
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
            getWidth: [hovered]
          },
          onHover: handleRouteHover
        })
      )
    }

    if (cvrpStore.visualizationMode === 'heatmap' && heatmapData.value.length > 0) {
      result.push(
        new PathLayer({
          id: 'cvrp-edge-heatmap',
          data: heatmapData.value,
          getPath: getHeatmapPath,
          getColor: (d: HeatmapEdge) => cvrpStore.getEdgeLoadColor(d.load),
          getWidth: 6,
          widthUnits: 'pixels',
          widthMinPixels: 2,
          widthMaxPixels: 12,
          pickable: false
        })
      )
    }

    return result
  })

  /** Drop the highlight and the tooltip. */
  function clearHover(): void {
    if (hoveredRouteId.value === null && cvrpTooltipData.value === null) return
    hoveredRouteId.value = null
    cvrpTooltipData.value = null
  }

  return { layers, cvrpTooltipData, clearHover, setTooltipMover }
}
