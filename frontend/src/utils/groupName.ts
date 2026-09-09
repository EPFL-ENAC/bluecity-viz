/**
 * A readable name for a group of streets edited together.
 *
 * The dock used to say "6 streets", which says nothing about where they are.
 * A zone is a place, so it takes a place name: the neighbourhood the basemap
 * knows, the same way the area picker names a circle. When no place is close
 * enough, the longest street of the group carries the name instead.
 *
 * Pure, and unit tested. `collectPlaces` (areaName.ts) is what reads the map.
 */

import type { TrafficAreaSelection } from '@/stores/layers/types'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { areaLabel, type PlacePoint } from '@/utils/areaName'

/** One street of the group: its name (may be empty) and its shape. */
export interface NamedLine {
  name: string
  coordinates: [number, number][]
}

/**
 * A zone smaller than this still asks the basemap from this radius.
 *
 * areaLabel gives a quarter a reach of 1.2 radii, so a 100 m block would
 * never reach the point that names its own neighbourhood.
 */
const ZONE_MIN_RADIUS = 400

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
 * The main street of the group: the name that adds up to the most metres.
 *
 * A lasso around a block takes a dozen small side streets and one long axis,
 * and the axis is what a person would name it after. Streets with no name do
 * not count.
 */
export function mainAxis(lines: NamedLine[]): string | null {
  const metres = new Map<string, number>()

  for (const line of lines) {
    if (!line.name) continue
    let length = 0
    for (let i = 1; i < line.coordinates.length; i += 1) {
      length += distanceM(line.coordinates[i - 1], line.coordinates[i])
    }
    metres.set(line.name, (metres.get(line.name) ?? 0) + length)
  }

  let best: string | null = null
  let bestLength = -1
  for (const [name, length] of metres) {
    if (length > bestLength) {
      best = name
      bestLength = length
    }
  }
  return best
}

/**
 * What the group is called: the place around it, else its main street, else
 * how many streets it holds.
 */
export function groupName(lines: NamedLine[], places: PlacePoint[]): string {
  const circle = zoneCircle(lines)
  if (circle) {
    const label = areaLabel(circle, places)
    if (label) return label
  }

  const axis = mainAxis(lines)
  if (axis) return `Around ${axis}`

  return `${lines.length} streets`
}
