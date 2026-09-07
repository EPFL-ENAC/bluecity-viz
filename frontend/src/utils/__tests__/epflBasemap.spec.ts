import { GRAPH_COLORS, VARIANTS, buildStyle } from '@/utils/epflBasemap'
import { describe, expect, it } from 'vitest'

/* eslint-disable @typescript-eslint/no-explicit-any */
const LIGHT = { ink: '#141414', paper: '#ffffff', density: 0.8 }
const DARK = { ink: '#F2F2F2', paper: '#141414', density: 0.8 }

function layers(key: string, t = LIGHT) {
  return buildStyle(key, t).layers as any[]
}

function byId(key: string, id: string, t = LIGHT) {
  return layers(key, t).find((l) => l.id === id)
}

describe('buildStyle: substrat', () => {
  it('draws no road line, only a faint dashed rail', () => {
    const ids = layers('substrat').map((l) => l.id)
    expect(ids).not.toContain('rd-minor')
    expect(ids).not.toContain('rd-sec')
    expect(ids).not.toContain('rd-path')
    expect(ids).not.toContain('rd-major')

    const rail = byId('substrat', 'rail')
    expect(rail.paint['line-dasharray']).toEqual([3, 2])
    // faint(ink, .72) toward the paper, not the full ink
    expect(rail.paint['line-color']).not.toBe('#141414')
  })

  it('has no building outline, only a solid tint', () => {
    const ids = layers('substrat').map((l) => l.id)
    expect(ids).not.toContain('bld-line')
    expect(byId('substrat', 'bld-fill').paint['fill-color']).toBeTypeOf('string')
  })

  it('draws both labels at 50 % ink with a paper halo', () => {
    for (const id of ['rd-label', 'place-label']) {
      const layer = byId('substrat', id)
      expect(layer.paint['text-color']).toBe('#8a8a8a')
      expect(layer.paint['text-halo-color']).toBe('#ffffff')
    }
  })

  it('keeps the label layers last so the overlay can insert before rd-label', () => {
    const ids = layers('substrat').map((l) => l.id)
    expect(ids.slice(-2)).toEqual(['rd-label', 'place-label'])
  })

  it('swaps ink and paper in dark', () => {
    expect(byId('substrat', 'bg', DARK).paint['background-color']).toBe('#141414')
    expect(byId('substrat', 'rd-label', DARK).paint['text-halo-color']).toBe('#141414')
  })

  it('is the only quiet, road-free variant', () => {
    expect(VARIANTS.substrat.roads).toBe('none')
    expect(VARIANTS.substrat.quiet).toBe(true)
    expect(VARIANTS.contour.quiet).toBeUndefined()
  })

  it('still draws the roads for the other variants', () => {
    expect(layers('contour').map((l) => l.id)).toContain('rd-major')
  })

  it('gives the overlay a graph grey that is not the ink', () => {
    expect(GRAPH_COLORS.light.accent).toBe('#0500E1')
    expect(GRAPH_COLORS.dark.accent).toBe('#8583FF')
    expect(GRAPH_COLORS.light.grey).not.toBe(GRAPH_COLORS.light.ink)
  })
})
