import {
  COMMUNES_HIT_LAYER,
  COMMUNES_SOURCE,
  communeLayerIds,
  communeLayers,
  swissCommunesSource,
  swissNetworkLayer,
  swissNetworkStyle
} from '@/config/toolLayers'
import { describe, expect, it } from 'vitest'

type Case = ['case', unknown, number, number]

/** The width expression at one zoom stop: [main road, other street]. */
function widthsAt(zoom: number): [number, number] {
  const paint = swissNetworkLayer.layer.paint as Record<string, unknown>
  const width = paint['line-width'] as unknown[]
  expect(width.slice(0, 3)).toEqual(['interpolate', ['linear'], ['zoom']])
  const at = width.indexOf(zoom, 3)
  expect(at).toBeGreaterThan(0)
  const value = width[at + 1]
  if (typeof value === 'number') return [value, value]
  const [, , main, other] = value as Case
  return [main, other]
}

describe('swissNetworkLayer', () => {
  it('draws the main roads wider from far away', () => {
    const [main6, other6] = widthsAt(6)
    expect(main6).toBeGreaterThan(other6)
    const [main10, other10] = widthsAt(10)
    expect(main10).toBeGreaterThan(other10)
  })

  it('draws every street the same hairline at z14', () => {
    const [main, other] = widthsAt(14)
    expect(main).toBe(other)
  })

  it('reads only the highway class from the tiles', () => {
    const json = JSON.stringify(swissNetworkLayer.layer)
    const gets = [...json.matchAll(/\["get","(\w+)"\]/g)].map((m) => m[1])
    expect(new Set(gets)).toEqual(new Set(['highway']))
  })
})

describe('swissNetworkStyle', () => {
  it('holds the network and nothing else', () => {
    const style = swissNetworkStyle()
    expect(style.version).toBe(8)
    expect(Object.keys(style.sources)).toEqual([swissNetworkLayer.sourceId])
    expect(style.layers.map((l) => l.id)).toEqual([swissNetworkLayer.layer.id])
  })
})

describe('communeLayers', () => {
  const colors = { ink: '#141414', grey: '#B8B8B8', accent: '#0500E1' }

  it('all read the communes layer of the communes source', () => {
    const layers = communeLayers(colors)
    expect(layers.map((l) => l.id)).toEqual(communeLayerIds())
    for (const layer of layers) {
      expect(layer).toMatchObject({
        source: COMMUNES_SOURCE,
        'source-layer': 'communes',
        minzoom: 7
      })
    }
  })

  it('starts with an invisible fill, the one the pointer hits', () => {
    const [hit] = communeLayers(colors) as Array<{ id: string; paint: Record<string, unknown> }>
    expect(hit.id).toBe(COMMUNES_HIT_LAYER)
    expect(hit.paint['fill-opacity']).toBe(0)
  })

  it('shows hover and selection through feature-state, never a filter', () => {
    const layers = communeLayers(colors) as Array<{ filter?: unknown }>
    expect(layers.every((l) => l.filter === undefined)).toBe(true)
    const json = JSON.stringify(layers)
    expect(json).toContain('["feature-state","hover"]')
    expect(json).toContain('["feature-state","selected"]')
    expect(json).toContain('["feature-state","ok"]')
  })

  it('reads no property: the BFS number is the feature id', () => {
    const json = JSON.stringify(communeLayers(colors))
    expect(json).not.toContain('"get"')
  })

  it('loads the pmtiles next to the network', () => {
    expect((swissCommunesSource as { url: string }).url).toMatch(
      /^pmtiles:\/\/.*\/swiss_communes\.pmtiles$/
    )
  })
})
