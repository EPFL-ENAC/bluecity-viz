/**
 * A readable name for the circle the user picked, "East Lausanne" instead of
 * "3.0 km around 46.520, 6.632".
 *
 * The names come from the basemap: the substrat style draws the OpenMapTiles
 * `place` layer (see epflBasemap.ts), one point per city, town, village or
 * quarter, with its class and its rank. We read those points back from the
 * source, so the label is free: no geocoder, no extra file, no request.
 *
 * `collectPlaces` talks to the map, `areaLabel` is pure and unit tested.
 */

import type { TrafficAreaSelection } from '@/stores/layers/types'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import type { Map as MapLibreMap } from 'maplibre-gl'

/** One settlement of the basemap, reduced to what naming needs. */
export interface PlacePoint {
  name: string
  /** the OpenMapTiles class: city, town, village, hamlet, suburb… */
  kind: string
  lon: number
  lat: number
}

/** How much a place counts once it is in reach. */
const WEIGHT: Record<string, number> = {
  city: 4,
  town: 3,
  village: 2,
  hamlet: 1.5,
  suburb: 1,
  quarter: 1,
  neighbourhood: 1
}

/**
 * How far a place carries its name, in radii of the circle. A city names the
 * area from twice the radius away, a quarter only from just outside it.
 */
const REACH: Record<string, number> = {
  city: 2,
  town: 1.6,
  village: 1.3,
  hamlet: 1.2,
  suburb: 1.2,
  quarter: 1.2,
  neighbourhood: 1.2
}

/** Only these get the "East …" prefix: a quarter is already one part of a town. */
const TAKES_DIRECTION = new Set(['city', 'town'])

const DIRECTIONS = [
  'North',
  'North-east',
  'East',
  'South-east',
  'South',
  'South-west',
  'West',
  'North-west'
]

// The centre must be off the place by this share of the radius before the
// name gets a direction, else a circle roughly on the town would read "South".
const OFF_CENTRE = 0.4
// A second name is added when it scores this close to the first one, and only
// between places of the same size: a town next to a city is a part of the area,
// not half of it.
const SECOND_NAME = 0.75
// Nothing in reach: how far we still look for a "Near …", in radii.
const NEAR_RADII = 2.5

/**
 * The settlements of the tiles the map has loaded.
 *
 * Source features, not rendered ones: a label the map dropped for lack of room
 * is still a place we can name the area after. Empty on the styles that carry
 * no labels (style/light.json, style/none.json), and then the caller keeps the
 * coordinates.
 */
export function collectPlaces(map: MapLibreMap): PlacePoint[] {
  if (!map.getSource('openmaptiles')) return []

  let features
  try {
    features = map.querySourceFeatures('openmaptiles', { sourceLayer: 'place' })
  } catch {
    // The source is in the style but has no tile yet.
    return []
  }

  const seen = new Set<string>()
  const places: PlacePoint[] = []

  for (const feature of features) {
    const properties = feature.properties ?? {}
    const name = typeof properties.name === 'string' ? properties.name : ''
    const kind = typeof properties.class === 'string' ? properties.class : ''
    if (!name || !(kind in WEIGHT)) continue
    if (feature.geometry?.type !== 'Point') continue

    const [lon, lat] = feature.geometry.coordinates as [number, number]
    // The same point comes back once per loaded tile, and once per zoom level.
    const key = `${name}|${lon.toFixed(3)}|${lat.toFixed(3)}`
    if (seen.has(key)) continue
    seen.add(key)

    places.push({ name, kind, lon, lat })
  }

  return places
}

/** Metres between two lon/lat, flat earth. Good enough over a few km. */
function distanceM(a: { lon: number; lat: number }, b: { lon: number; lat: number }): number {
  const dx = (a.lon - b.lon) * mPerDegLon((a.lat + b.lat) / 2)
  const dy = (a.lat - b.lat) * mPerDegLat
  return Math.hypot(dx, dy)
}

/** Where the circle sits compared to the place: "East", "South-west"… */
function directionOf(place: PlacePoint, circle: TrafficAreaSelection): string {
  const dx = (circle.lon - place.lon) * mPerDegLon(circle.lat)
  const dy = (circle.lat - place.lat) * mPerDegLat
  // Bearing from north, clockwise, cut in eight.
  const bearing = (Math.atan2(dx, dy) * 180) / Math.PI
  const index = Math.round(((bearing + 360) % 360) / 45) % 8
  return DIRECTIONS[index]
}

/**
 * The name of a circle, or null when no place is close enough. The caller then
 * keeps the coordinates.
 */
export function areaLabel(circle: TrafficAreaSelection, places: PlacePoint[]): string | null {
  if (!places.length || circle.radiusM <= 0) return null

  const scored = places
    .map((place) => {
      const distance = distanceM(place, circle)
      const reach = circle.radiusM * (REACH[place.kind] ?? 1)
      return {
        place,
        distance,
        // Full weight in the middle, nothing at the edge of its reach. So a
        // city one radius away still wins over a quarter in the middle, and a
        // city three radii away does not count at all.
        score: (WEIGHT[place.kind] ?? 0) * (1 - distance / reach)
      }
    })
    .sort((a, b) => b.score - a.score || a.distance - b.distance)

  const inside = scored.filter((entry) => entry.score > 0)

  if (!inside.length) {
    const nearest = scored.reduce((best, entry) => (entry.distance < best.distance ? entry : best))
    if (nearest.distance > circle.radiusM * NEAR_RADII) return null
    return `Near ${nearest.place.name}`
  }

  const best = inside[0]
  const second = inside[1]

  // Two places of the same size, both well inside: the area belongs to both.
  const sameSize = second && WEIGHT[second.place.kind] === WEIGHT[best.place.kind]
  if (second && sameSize && second.score >= best.score * SECOND_NAME) {
    return `${best.place.name} & ${second.place.name}`
  }

  const offset = best.distance / circle.radiusM
  if (TAKES_DIRECTION.has(best.place.kind) && offset > OFF_CENTRE) {
    return `${directionOf(best.place, circle)} ${best.place.name}`
  }

  return best.place.name
}
