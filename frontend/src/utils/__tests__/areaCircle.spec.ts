import type { TrafficAreaSelection } from '@/stores/layers/types'
import { AREA_SOURCE, areaFeatures, areaLayerIds, areaLayers, emptyArea } from '@/utils/areaCircle'
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

  it('splits the ring from the handle with a fixed filter', () => {
    const layers = areaLayers(GRAPH_COLORS.light)
    const roles = layers.map((l) => (l as { filter: unknown[] }).filter[2])
    expect(roles).toEqual(['ring', 'ring', 'handle'])
  })

  it('is accent when usable and grey when not', () => {
    const fill = areaLayers(GRAPH_COLORS.light)[0] as { paint: { 'fill-color': unknown[] } }
    expect(fill.paint['fill-color']).toContain(GRAPH_COLORS.light.accent)
    expect(fill.paint['fill-color']).toContain(GRAPH_COLORS.light.grey)
  })
})
