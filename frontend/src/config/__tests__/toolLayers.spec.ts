import { swissNetworkLayer, swissNetworkStyle } from '@/config/toolLayers'
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
