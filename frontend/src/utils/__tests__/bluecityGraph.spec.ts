import type { Street } from '@/stores/scenario'
import {
  BEFORE_LAYER,
  buildGraphLayers,
  cvrpHoverStates,
  drawFor,
  GRAPH_SOURCE,
  POINTER_SOURCE,
  graphLayerIds,
  idFilter,
  laneOffset,
  wData,
  wGraph,
  wMod
} from '@/utils/bluecityGraph'
import { GRAPH_COLORS } from '@/utils/epflBasemap'
import { describe, expect, it } from 'vitest'

/* eslint-disable @typescript-eslint/no-explicit-any */
const light = GRAPH_COLORS.light
const dark = GRAPH_COLORS.dark

function layer(id: string, colors = light, mode?: 'scenario' | 'result') {
  return buildGraphLayers({ colors, mode }).find((l) => l.id === id) as any
}

function street(lo: number, hi: number, over: Partial<Street> = {}): Street {
  return {
    key: `${lo}-${hi}`,
    lo,
    hi,
    name: `Street ${lo}-${hi}`,
    fwdId: 10,
    bwdId: 11,
    oneway: false,
    at: [6.6, 46.5],
    cls: 1,
    ...over
  }
}

describe('buildGraphLayers', () => {
  it('draws the graph, the data, the modifications, the pointer and the badges', () => {
    const ids = graphLayerIds()
    expect(ids).toContain('bc-graph-one')
    expect(ids).toContain('bc-lanes')
    expect(ids).toContain('bc-data')
    expect(ids).toContain('bc-mod')
    expect(ids).toContain('bc-hover')
    expect(ids).toContain('bc-selected-ghost')
    expect(ids.some((id) => id.startsWith('bc-badge-'))).toBe(true)
  })

  it('puts the pointer above the data and the badges last', () => {
    const ids = graphLayerIds()
    expect(ids.indexOf('bc-data')).toBeLessThan(ids.indexOf('bc-hover'))
    expect(ids.indexOf('bc-mod')).toBeLessThan(ids.indexOf('bc-hover'))
    expect(ids.indexOf('bc-hover')).toBeLessThan(ids.indexOf('bc-badge-both-closed'))
  })

  it('inserts under the street names', () => {
    expect(BEFORE_LAYER).toBe('rd-label')
  })

  // Touching the graph source on every mouse move is what made hovering slow:
  // a filter change reloads its tiles, and dropping the filter made these four
  // layers carry all 10k edges. They ride their own two feature source now.
  it('draws the pointer from its own source, not from the graph', () => {
    for (const id of ['bc-hover', 'bc-hover-halo', 'bc-selected', 'bc-selected-ghost']) {
      expect(layer(id).source).toBe(POINTER_SOURCE)
    }
    for (const id of ['bc-graph-one', 'bc-lanes', 'bc-data', 'bc-mod']) {
      expect(layer(id).source).toBe(GRAPH_SOURCE)
    }
  })

  it('gives each pointer layer a fixed role filter, so nothing changes at runtime', () => {
    expect(layer('bc-hover').filter).toEqual(['==', ['get', 'role'], 'hover'])
    expect(layer('bc-hover-halo').filter).toEqual(['==', ['get', 'role'], 'hover'])
    expect(layer('bc-selected').filter).toEqual(['==', ['get', 'role'], 'selected'])
    expect(layer('bc-selected-ghost').filter).toEqual(['==', ['get', 'role'], 'ghost'])
  })

  it('keeps the pointer opacity constant and reads the lane from the feature', () => {
    expect(layer('bc-selected').paint['line-opacity']).toBe(0.25)
    expect(layer('bc-hover-halo').paint['line-opacity']).toBe(0.18)
    const offset = JSON.stringify(layer('bc-hover').paint['line-offset'])
    expect(offset).toContain('["get","side"]')
    expect(offset).toContain('["get","lane"]')
    expect(offset).not.toContain('feature-state')
  })

  it('splits the graph into one-way lines and two-way lanes', () => {
    expect(layer('bc-graph-one').filter).toEqual(['==', ['get', 'two'], 0])
    expect(layer('bc-graph-two').filter).toEqual(['==', ['get', 'two'], 1])
    expect(layer('bc-lanes').filter).toEqual(['==', ['get', 'two'], 1])
    // the single centre line fades out exactly as the lanes fade in
    expect(layer('bc-graph-two').paint['line-opacity']).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      14.2,
      1,
      14.8,
      0
    ])
    expect(layer('bc-lanes').paint['line-opacity']).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      14.2,
      0,
      14.8,
      1
    ])
  })

  it('uses the accent for the pointer and nothing else', () => {
    // the cvrp halo is the pointer too: it says which vehicle you are on
    const pointer = [
      'bc-hover',
      'bc-hover-halo',
      'bc-selected',
      'bc-selected-ghost',
      'bc-cvrp-halo'
    ]
    for (const id of pointer) {
      expect(layer(id).paint['line-color']).toBe(light.accent)
    }

    const others = buildGraphLayers({ colors: light }).filter((l) => !pointer.includes(l.id))
    for (const l of others) {
      expect(JSON.stringify(l)).not.toContain(light.accent)
    }
  })

  it('draws a modification in ink in scenario mode', () => {
    expect(layer('bc-mod', light, 'scenario').paint['line-color']).toBe(light.ink)
  })

  it('lets the result colour own the stroke in result mode', () => {
    expect(layer('bc-mod', light, 'result').paint['line-color']).toEqual([
      'coalesce',
      ['feature-state', 'c'],
      light.ink
    ])
  })

  it('cuts a closed edge with paper dashes, and thins it in result mode', () => {
    expect(layer('bc-mod-cut').paint['line-color']).toBe(light.paper)
    expect(layer('bc-mod-cut').paint['line-dasharray']).toEqual([0.6, 1.2])
    expect(layer('bc-mod-closed-result').paint['line-dasharray']).toEqual([2, 2])
  })

  it('switches the arrow to ink when the colour owns the stroke', () => {
    expect(layer('bc-mod-arrows', light, 'scenario').layout['icon-image']).toBe('bc-arrow')
    expect(layer('bc-mod-arrows', light, 'result').layout['icon-image']).toBe('bc-arrow-ink')
  })

  it('swaps ink, paper and grey in dark, and lifts the accent', () => {
    expect(layer('bc-graph-one', dark).paint['line-color']).toBe('#5C5C5C')
    expect(layer('bc-mod', dark).paint['line-color']).toBe('#F2F2F2')
    expect(layer('bc-hover', dark).paint['line-color']).toBe('#8583FF')
  })

  it('shifts the badge onto its lane, and only tags a one-direction one', () => {
    expect(layer('bc-badge-both-closed').layout['icon-offset']).toEqual([0, 0])
    expect(layer('bc-badge-fwd-closed').layout['icon-offset']).toEqual([0, 10])
    expect(layer('bc-badge-bwd-closed').layout['icon-offset']).toEqual([0, -10])

    expect(layer('bc-badge-tag-fwd').layout['text-field']).toBe('→')
    expect(layer('bc-badge-tag-bwd').layout['text-field']).toBe('←')
    expect(layer('bc-badge-tag-both')).toBeUndefined()
  })

  it('draws a closed badge in ink and a speed badge in paper', () => {
    expect(layer('bc-badge-both-closed').layout['icon-image']).toBe('bc-badge-ink')
    expect(layer('bc-badge-both-speed').layout['icon-image']).toBe('bc-badge-paper')
    expect(layer('bc-badge-both-closed').paint['text-color']).toBe(light.paper)
    expect(layer('bc-badge-both-speed').paint['text-color']).toBe(light.ink)
  })
})

describe('widths and lane offset', () => {
  it('follows the design stops', () => {
    expect(wGraph()).toEqual(['interpolate', ['linear'], ['zoom'], 12, 0.6, 14, 1.2, 16, 2.2])
    expect(wMod()).toEqual(['interpolate', ['linear'], ['zoom'], 12, 3, 14, 5, 16, 9])
  })

  it('scales the data width by the road class', () => {
    // [interpolate, [linear], [zoom], z0, value0, ...]
    const expression = wData() as any
    expect(expression[3]).toBe(12)
    expect(expression[4]).toEqual(['*', 1.4, ['get', 'cls']])
  })

  it('keeps a one-way street on the centre and offsets a lane to its own right', () => {
    const expression = laneOffset() as any
    expect(expression[3]).toBe(13)
    expect(expression[4]).toEqual([
      'case',
      ['==', ['get', 'two'], 0],
      0,
      ['*', 1.6, ['get', 'side']]
    ])
  })
})

describe('drawFor', () => {
  const streets = new Map<string, Street>([
    ['1-2', street(1, 2)],
    ['3-4', street(3, 4, { fwdId: 20, bwdId: undefined, oneway: true })]
  ])

  it('covers both lanes of a both modification', () => {
    const draw = drawFor([['1-2', { action: 'remove', dir: 'both' }]], streets)
    expect(draw.strokeIds.sort()).toEqual([10, 11])
    expect(draw.closedIds.sort()).toEqual([10, 11])
    expect(draw.arrowIds).toEqual([])
    expect(draw.laneIds).toEqual([])
  })

  it('covers one lane, and says so, for a one-direction modification', () => {
    const draw = drawFor([['1-2', { action: '30', dir: 'fwd' }]], streets)
    expect(draw.strokeIds).toEqual([10])
    expect(draw.laneIds).toEqual([10])
    expect(draw.arrowIds).toEqual([10])
    expect(draw.closedIds).toEqual([])
  })

  it('uses the single edge a one-way street has', () => {
    const draw = drawFor([['3-4', { action: 'remove', dir: 'both' }]], streets)
    expect(draw.strokeIds).toEqual([20])
  })

  it('makes one badge per street, with the glyph and the direction', () => {
    const draw = drawFor(
      [
        ['1-2', { action: 'remove', dir: 'both' }],
        ['3-4', { action: '50', dir: 'fwd' }]
      ],
      streets
    )

    expect(draw.badges).toHaveLength(2)
    expect(draw.badges[0].properties).toMatchObject({ glyph: '×', closed: 1, dir: 'both' })
    expect(draw.badges[1].properties).toMatchObject({ glyph: '50', closed: 0, dir: 'fwd' })
    expect(draw.badges[0].geometry.coordinates).toEqual([6.6, 46.5])
  })

  it('skips a street the graph does not know', () => {
    const draw = drawFor([['9-9', { action: 'remove', dir: 'both' }]], streets)
    expect(draw.strokeIds).toEqual([])
    expect(draw.badges).toEqual([])
  })
})

describe('idFilter', () => {
  it('matches by feature id, so a missing name cannot break it', () => {
    expect(idFilter([1, 2])).toEqual(['in', ['id'], ['literal', [1, 2]]])
    expect(idFilter([])).toEqual(['in', ['id'], ['literal', []]])
  })
})

describe('cvrpHoverStates', () => {
  const features = [
    { id: 0, properties: { route_id: 1 } },
    { id: 1, properties: { route_id: 2 } },
    { id: 2, properties: { route_id: 1 } }
  ]

  it('lights the hovered vehicle and dims the others', () => {
    expect(cvrpHoverStates(features, 1)).toEqual([
      { id: 0, state: { hl: 1, dim: 0 } },
      { id: 1, state: { hl: 0, dim: 1 } },
      { id: 2, state: { hl: 1, dim: 0 } }
    ])
  })

  it('clears every feature when the pointer leaves', () => {
    for (const row of cvrpHoverStates(features, null)) {
      expect(row.state).toEqual({ hl: 0, dim: 0 })
    }
  })
})
