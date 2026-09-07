import { streetTotals, topAbsorbers, valueOf } from '@/composables/useResultStates'
import type { Street } from '@/stores/scenario'
import type { EdgeUsageStats } from '@/stores/trafficAnalysis'
import { describe, expect, it } from 'vitest'

function street(key: string, over: Partial<Street> = {}): Street {
  const [lo, hi] = key.split('-').map(Number)
  return {
    key,
    lo,
    hi,
    name: `Street ${key}`,
    fwdId: 0,
    bwdId: 1,
    oneway: false,
    at: [0, 0],
    cls: 1,
    bus: false,
    ...over
  }
}

function usage(over: Partial<EdgeUsageStats> & { u: number; v: number }): EdgeUsageStats {
  return { count: 0, frequency: 0, ...over }
}

describe('streetTotals', () => {
  it('sums the two directions of a street onto one row', () => {
    const streets = new Map([['1-2', street('1-2', { fwdId: 4, bwdId: 5 })]])
    const rows = streetTotals(
      [
        usage({ u: 1, v: 2, frequency: 100, delta_count: 10, delta_frequency: 20 }),
        usage({ u: 2, v: 1, frequency: 40, delta_count: 4, delta_frequency: 5 })
      ],
      streets
    )

    expect(rows).toHaveLength(1)
    expect(rows[0].frequency).toBe(140)
    expect(rows[0].delta_count).toBe(14)
    // before = 140 - 25 = 115, so 25 / 115
    expect(rows[0].delta_relative).toBeCloseTo((25 / 115) * 100, 6)
  })

  it('colours on the forward feature, and falls back to the backward one', () => {
    const streets = new Map([
      ['1-2', street('1-2', { fwdId: 7, bwdId: 8 })],
      ['3-4', street('3-4', { fwdId: undefined, bwdId: 9, oneway: true })]
    ])
    const rows = streetTotals(
      [usage({ u: 1, v: 2, frequency: 1 }), usage({ u: 4, v: 3, frequency: 1 })],
      streets
    )

    expect(rows.find((row) => row.key === '1-2')?.id).toBe(7)
    expect(rows.find((row) => row.key === '3-4')?.id).toBe(9)
  })

  it('skips a row whose street the graph does not have', () => {
    const rows = streetTotals([usage({ u: 9, v: 9, frequency: 5 })], new Map())
    expect(rows).toEqual([])
  })

  it('carries the bus flag through, for the bus routes filter', () => {
    const streets = new Map([['1-2', street('1-2', { bus: true })]])
    const rows = streetTotals([usage({ u: 1, v: 2, frequency: 1 })], streets)
    expect(rows[0].bus).toBe(true)
  })

  it('leaves the relative change at zero when there was no traffic before', () => {
    const streets = new Map([['1-2', street('1-2')]])
    const rows = streetTotals([usage({ u: 1, v: 2, frequency: 10, delta_frequency: 10 })], streets)
    expect(rows[0].delta_relative).toBe(0)
  })
})

describe('valueOf', () => {
  const streets = new Map([['1-2', street('1-2')]])
  const rows = streetTotals(
    [
      usage({
        u: 1,
        v: 2,
        frequency: 100,
        delta_count: 12,
        co2_per_km: 3,
        delta_frequency: 2,
        betweenness_centrality: 0.5,
        delta_betweenness: -0.1
      })
    ],
    streets
  )

  it('reads the number each mode shows', () => {
    expect(valueOf(rows[0], 'frequency')).toBe(100)
    expect(valueOf(rows[0], 'delta')).toBe(12)
    expect(valueOf(rows[0], 'co2')).toBe(3)
    expect(valueOf(rows[0], 'co2_delta')).toBe(6)
    expect(valueOf(rows[0], 'betweenness')).toBe(0.5)
    expect(valueOf(rows[0], 'betweenness_delta')).toBe(-0.1)
  })
})

describe('topAbsorbers', () => {
  const streets = new Map([
    ['1-2', street('1-2')],
    ['3-4', street('3-4')],
    ['5-6', street('5-6')],
    ['7-8', street('7-8')]
  ])
  const rows = streetTotals(
    [
      usage({ u: 1, v: 2, delta_count: 90, frequency: 1 }),
      usage({ u: 3, v: 4, delta_count: 50, frequency: 1 }),
      usage({ u: 5, v: 6, delta_count: 30, frequency: 1 }),
      usage({ u: 7, v: 8, delta_count: -80, frequency: 1 })
    ],
    streets
  )

  it('gives the biggest gains among the streets nobody touched', () => {
    const top = topAbsorbers(rows, new Set(['1-2']))
    expect(top.map((row) => row.key)).toEqual(['3-4', '5-6'])
  })

  it('never lists a street that lost traffic', () => {
    const top = topAbsorbers(rows, new Set())
    expect(top.map((row) => row.key)).toEqual(['1-2', '3-4', '5-6'])
  })
})
