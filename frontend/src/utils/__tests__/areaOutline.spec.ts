import type { AreaOutline } from '@/services/trafficAnalysis'
import { outlineBbox, outlineFeatures, outlineRings } from '@/utils/areaOutline'
import { describe, expect, it } from 'vitest'

const WITH_HOLE: AreaOutline = {
  type: 'Polygon',
  coordinates: [
    [
      [6.6, 46.5],
      [6.7, 46.5],
      [6.7, 46.6],
      [6.6, 46.5]
    ],
    [
      [6.65, 46.52],
      [6.66, 46.52],
      [6.66, 46.53],
      [6.65, 46.52]
    ]
  ]
}

const TWO_PIECES: AreaOutline = {
  type: 'MultiPolygon',
  coordinates: [
    WITH_HOLE.coordinates,
    [
      [
        [6.8, 46.7],
        [6.9, 46.7],
        [6.9, 46.8],
        [6.8, 46.7]
      ]
    ]
  ]
}

describe('outlineRings', () => {
  it('gives the outer ring and the hole of a polygon', () => {
    expect(outlineRings(WITH_HOLE)).toHaveLength(2)
  })

  it('gives every ring of every piece', () => {
    const rings = outlineRings(TWO_PIECES)
    expect(rings).toHaveLength(3)
    expect(rings[2][0]).toEqual([6.8, 46.7])
  })

  it('is empty without an outline', () => {
    expect(outlineRings(null)).toEqual([])
  })
})

describe('outlineFeatures', () => {
  it('is one ring feature with the usable flag, and no handle', () => {
    const usable = outlineFeatures(TWO_PIECES, true)
    expect(usable.features).toHaveLength(1)
    expect(usable.features[0].properties).toEqual({ role: 'ring', ok: 1 })
    expect(usable.features[0].geometry.type).toBe('MultiPolygon')
    expect(outlineFeatures(WITH_HOLE, false).features[0].properties.ok).toBe(0)
  })

  it('is an empty collection without an outline', () => {
    expect(outlineFeatures(null, true)).toEqual({ type: 'FeatureCollection', features: [] })
  })
})

describe('outlineBbox', () => {
  it('covers every piece', () => {
    expect(outlineBbox(TWO_PIECES)).toEqual([6.6, 46.5, 6.9, 46.8])
  })

  it('is null without an outline', () => {
    expect(outlineBbox(null)).toBeNull()
  })
})
