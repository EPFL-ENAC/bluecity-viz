import type { TrafficAreaSelection } from '@/stores/layers/types'
import {
  AREA_RING_LAYER,
  AREA_SOURCE,
  areaFeatures,
  areaLayerIds,
  areaLayers,
  areaRingLayer,
  clipPathOf,
  emptyArea
} from '@/utils/areaCircle'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { describe, expect, it } from 'vitest'

const BERN: TrafficAreaSelection = { kind: 'circle', lon: 7.44, lat: 46.95, radiusM: 3000 }

function ring(circle = BERN, ok = true) {
  const feature = areaFeatures(circle, ok).features[0]
  return (feature.geometry as { coordinates: [number, number][][] }).coordinates[0]
}

describe('the picker circle', () => {
  it('closes the ring, so the fill has no gap', () => {
    const points = ring()
    expect(points.length).toBeGreaterThan(32)
    expect(points[0]).toEqual(points[points.length - 1])
  })

  it('is the asked radius, in metres, at this latitude', () => {
    const points = ring()
    // due east and due north of the centre
    const east = points[0]
    const north = points[(points.length - 1) / 4]

    expect((east[0] - BERN.lon) * mPerDegLon(BERN.lat)).toBeCloseTo(3000, 0)
    expect((north[1] - BERN.lat) * mPerDegLat).toBeCloseTo(3000, 0)
  })

  it('is wider in degrees the further north it sits', () => {
    const south = ring({ ...BERN, lat: 0 })[0][0]
    const north = ring({ ...BERN, lat: 60 })[0][0]
    expect(north - BERN.lon).toBeGreaterThan(south - BERN.lon)
  })

  it('carries the centre handle and the usable flag', () => {
    const usable = areaFeatures(BERN, true)
    const refused = areaFeatures(BERN, false)

    expect(usable.features.map((f) => f.properties.role)).toEqual(['ring', 'handle'])
    expect(usable.features[1].geometry).toEqual({ type: 'Point', coordinates: [7.44, 46.95] })
    expect(usable.features.map((f) => f.properties.ok)).toEqual([1, 1])
    expect(refused.features.map((f) => f.properties.ok)).toEqual([0, 0])
  })

  it('empties to a collection the map can still read', () => {
    expect(emptyArea()).toEqual({ type: 'FeatureCollection', features: [] })
  })
})

describe('the picker layers', () => {
  it('all sit on the picker source, never on the graph', () => {
    const layers = areaLayers(GRAPH_COLORS.light)
    expect(layers.map((l) => l.id)).toEqual(areaLayerIds())
    expect(layers.every((l) => 'source' in l && l.source === AREA_SOURCE)).toBe(true)
  })

  it('splits the mask, the ring and the handle with a fixed filter', () => {
    const layers = areaLayers(GRAPH_COLORS.light)
    const roles = layers.map((l) => (l as { filter: unknown[] }).filter[2])
    expect(roles).toEqual(['ring', 'ring', 'handle'])
  })

  it('is accent when usable and grey when not', () => {
    const line = areaLayers(GRAPH_COLORS.light)[1] as { paint: { 'line-color': unknown[] } }
    expect(line.paint['line-color']).toContain(GRAPH_COLORS.light.accent)
    expect(line.paint['line-color']).toContain(GRAPH_COLORS.light.grey)
  })

  it('draws no disc: the streets inside are the fill', () => {
    const fill = areaLayers(GRAPH_COLORS.light)[0] as { paint: { 'fill-opacity': number } }
    expect(fill.paint['fill-opacity']).toBe(0)
  })
})

describe('the clip that cuts the network canvas', () => {
  it('is a closed CSS path of the points, in pixels', () => {
    expect(
      clipPathOf([
        [10, 20],
        [30, 20],
        [30, 40]
      ])
    ).toBe('path("M10 20L30 20L30 40Z")')
  })

  it('keeps a tenth of a pixel, enough for the cut to sit on the ring', () => {
    expect(
      clipPathOf([
        [1.26, 2.34],
        [3, 4],
        [5, 6]
      ])
    ).toBe('path("M1.3 2.3L3 4L5 6Z")')
  })

  it('hides everything when there is no circle', () => {
    const nothing = clipPathOf([])
    expect(nothing).toBe('path("M0 0Z")')
    expect(
      clipPathOf([
        [1, 1],
        [2, 2]
      ])
    ).toBe(nothing)
  })
})

describe('the ring that stays after the pick', () => {
  it('is ink on the picker source, so it is not the pointer', () => {
    const ring = areaRingLayer(GRAPH_COLORS.light) as {
      id: string
      source: string
      paint: { 'line-color': string }
    }
    expect(ring.id).toBe(AREA_RING_LAYER)
    expect(ring.source).toBe(AREA_SOURCE)
    expect(ring.paint['line-color']).toBe(GRAPH_COLORS.light.ink)
  })

  it('is not one of the picker layers, they have separate owners', () => {
    expect(areaLayerIds()).not.toContain(AREA_RING_LAYER)
  })
})
