import type { CVRPRouteSegment } from '@/services/cvrp'
import { routeDistance, routeFeatures, routeSummaries, vehicleHex } from '@/utils/cvrpSource'
import { describe, expect, it } from 'vitest'

function segment(
  route_id: number,
  trip_id: number,
  path: [number, number][],
  load_kg = 100
): CVRPRouteSegment {
  return { route_id, trip_id, path_coordinates: path, load_kg }
}

const LINE: [number, number][] = [
  [6.6, 46.5],
  [6.61, 46.5]
]

describe('vehicleHex', () => {
  it('gives the Okabe-Ito hue of a vehicle, and reuses them past the eighth', () => {
    expect(vehicleHex(0)).toBe('#0072b2')
    expect(vehicleHex(1)).toBe('#e69f00')
    expect(vehicleHex(8)).toBe(vehicleHex(0))
  })
})

describe('routeFeatures', () => {
  it('centres the slots on zero so the routes braid around the street', () => {
    const collection = routeFeatures([
      segment(0, 0, LINE),
      segment(1, 0, LINE),
      segment(2, 0, LINE),
      segment(3, 0, LINE),
      segment(4, 0, LINE)
    ])
    expect(collection.features.map((f) => f.properties.slot)).toEqual([-2, -1, 0, 1, 2])
  })

  it('gives a lone route the centre line', () => {
    const collection = routeFeatures([segment(0, 0, LINE)])
    expect(collection.features[0].properties.slot).toBe(0)
  })

  it('keeps a route on its slot across every segment it drives', () => {
    const collection = routeFeatures([
      segment(0, 0, LINE),
      segment(1, 0, LINE),
      segment(0, 1, LINE)
    ])
    const slots = collection.features.map((f) => f.properties.slot)
    expect(slots[0]).toBe(slots[2])
    expect(slots[0]).not.toBe(slots[1])
  })

  it('counts the slots over the vehicles the solver was given, not the ones that drove', () => {
    const collection = routeFeatures([segment(0, 0, LINE), segment(1, 0, LINE)], 5)
    expect(collection.features.map((f) => f.properties.slot)).toEqual([-2, -1])
  })

  it('carries the hue and the load through', () => {
    const collection = routeFeatures([segment(1, 2, LINE, 4200)])
    expect(collection.features[0].properties.color).toBe('#e69f00')
    expect(collection.features[0].properties.load_kg).toBe(4200)
    expect(collection.features[0].properties.trip_id).toBe(2)
  })
})

describe('routeDistance', () => {
  it('adds up only the segments of that vehicle', () => {
    const segments = [segment(0, 0, LINE), segment(1, 0, LINE)]
    const one = routeDistance(segments, 0)
    const both = routeDistance([...segments, segment(0, 1, LINE)], 0)
    // 0.01 degree of longitude at 46.5 N is about 765 m
    expect(one).toBeGreaterThan(700)
    expect(one).toBeLessThan(800)
    expect(both).toBeCloseTo(one * 2, 3)
  })
})

describe('routeSummaries', () => {
  const segments = [segment(0, 0, LINE, 3000), segment(0, 1, LINE, 5000), segment(1, 0, LINE, 1000)]

  it('gives one row per vehicle, sorted, with its trips and its worst load', () => {
    const rows = routeSummaries(segments)
    expect(rows.map((row) => row.route_id)).toEqual([0, 1])
    expect(rows[0].trips).toBe(2)
    expect(rows[0].load_kg).toBe(5000)
    expect(rows[1].trips).toBe(1)
  })

  it('gives each row its own hue and distance', () => {
    const rows = routeSummaries(segments)
    expect(rows[0].color).toBe('#0072b2')
    expect(rows[0].distance_m).toBeCloseTo(rows[1].distance_m * 2, 3)
  })
})
