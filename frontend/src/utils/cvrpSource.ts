/**
 * The waste collection solution, as GeoJSON for the map.
 *
 * The routes share streets, so they are braided: every route keeps a fixed
 * slot around the centreline and stays on it for the whole run. That way you
 * can follow one vehicle with your eye where five of them overlap.
 */
import type { CVRPRouteSegment } from '@/services/cvrp'
import { getVehicleColor } from '@/stores/cvrp'
import type { FeatureCollection } from 'geojson'

export interface RouteFeature {
  type: 'Feature'
  id: number
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  properties: {
    route_id: number
    trip_id: number
    load_kg: number
    /** the lane this route rides, centred on 0 */
    slot: number
    color: string
  }
}

export interface RouteCollection {
  type: 'FeatureCollection'
  features: RouteFeature[]
}

/** The Okabe-Ito colour of a vehicle, as hex, so MapLibre can read it. */
export function vehicleHex(routeId: number): string {
  const [r, g, b] = getVehicleColor(routeId)
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

/**
 * One feature per segment. `slot` centres the routes around the street, so
 * with 5 vehicles the slots are -2, -1, 0, 1, 2.
 */
export function routeFeatures(segments: CVRPRouteSegment[], routeCount?: number): RouteCollection {
  const ids = [...new Set(segments.map((segment) => segment.route_id))].sort((a, b) => a - b)
  const total = routeCount ?? ids.length
  const slotOf = new Map<number, number>()
  ids.forEach((id, index) => slotOf.set(id, index - (total - 1) / 2))

  return {
    type: 'FeatureCollection',
    features: segments.map((segment, index) => ({
      type: 'Feature' as const,
      id: index,
      geometry: { type: 'LineString' as const, coordinates: segment.path_coordinates },
      properties: {
        route_id: segment.route_id,
        trip_id: segment.trip_id,
        load_kg: segment.load_kg,
        slot: slotOf.get(segment.route_id) ?? 0,
        color: vehicleHex(segment.route_id)
      }
    }))
  }
}

/** Metres between two lng/lat points, flat earth. Good enough over a city. */
function metres(a: [number, number], b: [number, number]): number {
  const mid = ((a[1] + b[1]) / 2) * (Math.PI / 180)
  const x = (b[0] - a[0]) * 111320 * Math.cos(mid)
  const y = (b[1] - a[1]) * 110540
  return Math.hypot(x, y)
}

/** How far one vehicle drives, from its own path. */
export function routeDistance(segments: CVRPRouteSegment[], routeId: number): number {
  let total = 0
  for (const segment of segments) {
    if (segment.route_id !== routeId) continue
    const path = segment.path_coordinates
    for (let i = 1; i < path.length; i++) total += metres(path[i - 1], path[i])
  }
  return total
}

export interface RouteSummary {
  route_id: number
  trips: number
  load_kg: number
  distance_m: number
  color: string
}

/** One row per vehicle, for the solution table in the dock. */
export function routeSummaries(segments: CVRPRouteSegment[]): RouteSummary[] {
  const byRoute = new Map<number, RouteSummary>()

  for (const segment of segments) {
    let row = byRoute.get(segment.route_id)
    if (!row) {
      row = {
        route_id: segment.route_id,
        trips: 0,
        load_kg: 0,
        distance_m: 0,
        color: vehicleHex(segment.route_id)
      }
      byRoute.set(segment.route_id, row)
    }
    row.load_kg = Math.max(row.load_kg, segment.load_kg)
  }

  const trips = new Map<number, Set<number>>()
  for (const segment of segments) {
    if (!trips.has(segment.route_id)) trips.set(segment.route_id, new Set())
    trips.get(segment.route_id)!.add(segment.trip_id)
  }

  for (const row of byRoute.values()) {
    row.trips = trips.get(row.route_id)?.size ?? 0
    row.distance_m = routeDistance(segments, row.route_id)
  }

  return [...byRoute.values()].sort((a, b) => a.route_id - b.route_id)
}

export interface PointFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: { kind: 'point' | 'depot'; reached: number }
}

/**
 * The collection points. A point the solver could not reach is drawn hollow,
 * not hidden: the user asked where the waste is, not where the solver went.
 */
export function pointFeatures(centroids: FeatureCollection | null, missing = 0): PointFeature[] {
  const features = centroids?.features ?? []
  const out: PointFeature[] = []

  features.forEach((feature, index) => {
    if (feature.geometry?.type !== 'Point') return
    const at = feature.geometry.coordinates
    if (!at || at.length < 2) return
    out.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [at[0], at[1]] },
      // The backend does not say which ones it dropped, only how many, so the
      // last N are shown hollow. Replace this when it sends the list.
      properties: { kind: 'point', reached: index >= features.length - missing ? 0 : 1 }
    })
  })

  return out
}
