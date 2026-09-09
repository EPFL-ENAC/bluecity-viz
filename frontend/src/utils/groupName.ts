/**
 * A readable name for a group of streets edited together.
 *
 * The dock used to say "6 streets", which says nothing about where they are.
 *
 * The first idea was to name a zone after its neighbourhood, the way the area
 * picker names a circle. The basemap does not carry them: around the middle of
 * Lausanne the only place points are the city itself and two hamlets over a
 * kilometre away, so every zone came back as "North-east Lausanne". A city
 * name says nothing about six streets, so it is not used at all now.
 *
 * What the map does carry is street names, and the graph knows how big each
 * street is. So a zone is named after its main street: the name that adds up
 * to the most road, counting a main road for more than a lane, and counting
 * the traffic on it when a result has been computed. A neighbourhood still
 * wins when there is one close by.
 *
 * Pure, and unit tested. `collectPlaces` (areaName.ts) is what reads the map.
 */

import type { TrafficAreaSelection } from '@/stores/layers/types'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import type { PlacePoint } from '@/utils/areaName'

/** One street of the group: its name, its shape, and how much it carries. */
export interface NamedLine {
  name: string
  coordinates: [number, number][]
  /** how big the road is, from classFactor: 1.6 primary … 0.7 minor */
  cls?: number
  /** vehicles on it, when a routing result has been computed */
  volume?: number
}

/**
 * The places small enough to name a zone.
 *
 * A city or a town covers far more than a lasso ever will, so its name would
 * be wrong every time. These are the ones that mean a part of a town.
 */
const LOCAL_KINDS = new Set(['neighbourhood', 'quarter', 'suburb', 'hamlet'])

/** A local place still names a zone from this far out, in metres. */
const LOCAL_REACH = 500

/** A zone smaller than this is still given this radius, in metres. */
const ZONE_MIN_RADIUS = 400

/** How much the busiest street of the group is favoured over the quietest. */
const VOLUME_WEIGHT = 2

/** Metres between two lon/lat, flat earth. Good enough over a few km. */
function distanceM(a: [number, number], b: [number, number]): number {
  const dx = (a[0] - b[0]) * mPerDegLon((a[1] + b[1]) / 2)
  const dy = (a[1] - b[1]) * mPerDegLat
  return Math.hypot(dx, dy)
}

/** The circle the group covers: the mean of its points, out to the farthest. */
export function zoneCircle(lines: NamedLine[]): TrafficAreaSelection | null {
  let sumLon = 0
  let sumLat = 0
  let count = 0

  for (const line of lines) {
    for (const point of line.coordinates) {
      sumLon += point[0]
      sumLat += point[1]
      count += 1
    }
  }
  if (count === 0) return null

  const centre: [number, number] = [sumLon / count, sumLat / count]
  let radius = 0
  for (const line of lines) {
    for (const point of line.coordinates) {
      radius = Math.max(radius, distanceM(centre, point))
    }
  }

  return {
    kind: 'circle',
    lon: centre[0],
    lat: centre[1],
    radiusM: Math.max(radius, ZONE_MIN_RADIUS)
  }
}

/**
 * The neighbourhood the zone sits in, when one is close enough.
 *
 * Closest wins, whatever its kind: they are all parts of a town, and a
 * ranking between them would only guess.
 */
export function localPlace(circle: TrafficAreaSelection, places: PlacePoint[]): string | null {
  const reach = Math.max(circle.radiusM, LOCAL_REACH)
  let best: string | null = null
  let bestDistance = reach

  for (const place of places) {
    if (!LOCAL_KINDS.has(place.kind)) continue
    const distance = distanceM([place.lon, place.lat], [circle.lon, circle.lat])
    if (distance < bestDistance) {
      best = place.name
      bestDistance = distance
    }
  }
  return best
}

/**
 * The main street of the group.
 *
 * A lasso around a block takes a dozen small side streets and one axis, and
 * the axis is what a person would name it after. Length alone picks the wrong
 * one: three quiet lanes add up to more metres than the avenue they hang off.
 * So every metre counts for more on a bigger road, and for more again on a
 * street the routing sends traffic down.
 */
export function mainAxis(lines: NamedLine[]): string | null {
  let peak = 0
  for (const line of lines) peak = Math.max(peak, line.volume ?? 0)

  const scores = new Map<string, number>()

  for (const line of lines) {
    if (!line.name) continue

    let length = 0
    for (let i = 1; i < line.coordinates.length; i += 1) {
      length += distanceM(line.coordinates[i - 1], line.coordinates[i])
    }

    // A primary road counts for about five times a residential one.
    const size = (line.cls ?? 1) ** 2
    // No result yet: every street carries the same weight.
    const busy = peak > 0 ? 1 + (VOLUME_WEIGHT * (line.volume ?? 0)) / peak : 1

    scores.set(line.name, (scores.get(line.name) ?? 0) + length * size * busy)
  }

  let best: string | null = null
  let bestScore = -1
  for (const [name, score] of scores) {
    if (score > bestScore) {
      best = name
      bestScore = score
    }
  }
  return best
}

/**
 * What the zone is called: the neighbourhood around it, else its main street,
 * else how many streets it holds.
 */
export function groupName(lines: NamedLine[], places: PlacePoint[]): string {
  const circle = zoneCircle(lines)
  if (circle) {
    const local = localPlace(circle, places)
    if (local) return local
  }

  const axis = mainAxis(lines)
  if (axis) return `Around ${axis}`

  return `${lines.length} streets`
}
