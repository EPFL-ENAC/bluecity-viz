/**
 * A readable name for a group of streets edited together.
 *
 * The dock used to say "6 streets", which says nothing about where they are.
 *
 * A zone should be called by its district, the way a person would say it. The
 * basemap cannot do that: around the middle of Lausanne the only place points
 * are the city itself and two hamlets over a kilometre away, so every zone
 * came back as "North-east Lausanne". OpenStreetMap has no quartier boundary
 * for Lausanne either. So the districts are bundled, see data/districts.ts.
 *
 * Three tries, in order:
 * 1. the closest bundled district, when the zone is small enough for one
 * 2. the closest neighbourhood of the basemap, for the rest of Switzerland
 * 3. the main street of the zone, the name that adds up to the most road,
 *    counting a main road for more than a lane and counting the traffic on it
 *    when a result has been computed
 *
 * A city or a town name is never used: it says nothing about six streets.
 *
 * Pure, and unit tested. `collectPlaces` (areaName.ts) is what reads the map.
 */

import { DISTRICT_REACH, DISTRICTS, type DistrictPoint } from '@/data/districts'
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

/**
 * A zone wider than this is not one district any more, in metres.
 *
 * A brush stroke across the whole town would still find a sector point 300 m
 * away, and calling half of Lausanne "Cite" would be a lie. Past this the main
 * street names it.
 */
const DISTRICT_MAX_RADIUS = 1000

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
 * The district the zone sits in, from the bundled list.
 *
 * The points cut the city the way a Voronoi does, so the closest one wins.
 * Outside Lausanne the list holds nothing in reach and this gives null.
 */
export function district(
  circle: TrafficAreaSelection,
  points: DistrictPoint[] = DISTRICTS
): string | null {
  if (circle.radiusM > DISTRICT_MAX_RADIUS) return null

  let best: string | null = null
  let bestDistance = DISTRICT_REACH

  for (const point of points) {
    const distance = distanceM([point.lon, point.lat], [circle.lon, circle.lat])
    if (distance < bestDistance) {
      best = point.name
      bestDistance = distance
    }
  }
  return best
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
 * What the zone is called: its district, else the neighbourhood around it,
 * else its main street, else how many streets it holds.
 */
export function groupName(lines: NamedLine[], places: PlacePoint[]): string {
  const circle = zoneCircle(lines)
  if (circle) {
    const name = district(circle) ?? localPlace(circle, places)
    if (name) return name
  }

  const axis = mainAxis(lines)
  if (axis) return `Around ${axis}`

  return `${lines.length} streets`
}
