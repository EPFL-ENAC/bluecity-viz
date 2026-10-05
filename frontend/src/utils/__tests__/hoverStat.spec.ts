import type { StreetTotals } from '@/composables/useResultStates'
import { hoverStat } from '@/utils/hoverStat'
import type { TrafficLegendMode } from '@/utils/legendColor'
import { describe, expect, it } from 'vitest'

function row(fields: Partial<StreetTotals> = {}): StreetTotals {
  return {
    key: '1-2',
    name: 'Rue Centrale',
    id: 0,
    bus: false,
    count: 12345,
    frequency: 0.2,
    delta_count: 120,
    delta_relative: 3.42,
    co2_g_per_km: 850,
    delta_co2_g_per_km: 120,
    betweenness_centrality: 1234,
    delta_betweenness: 56,
    delta_frequency: 0.01,
    ...fields
  }
}

describe('hoverStat', () => {
  it.each<[TrafficLegendMode, string, string]>([
    ['frequency', 'Vehicles / day', '12 345'],
    ['delta', 'Change', '+120 · +3.4%'],
    ['delta_relative', 'Relative change', '+3.4% · +120'],
    ['co2', 'CO₂', '850 g/km'],
    ['co2_delta', 'CO₂ change', '+120 g/km'],
    ['betweenness', 'Betweenness', '1 234 veh/day'],
    ['betweenness_delta', 'Betweenness change', '+56 veh/day']
  ])('shows the %s layer', (mode, label, value) => {
    expect(hoverStat(row(), mode)).toEqual({ label, value })
  })

  it('switches to kg/km above 1000 g', () => {
    expect(hoverStat(row({ co2_g_per_km: 12400 }), 'co2').value).toBe('12.4 kg/km')
    expect(hoverStat(row({ delta_co2_g_per_km: -2500 }), 'co2_delta').value).toBe('-2.5 kg/km')
  })

  it('keeps the minus of a negative change', () => {
    const stat = hoverStat(row({ delta_count: -1500, delta_relative: -12.34 }), 'delta')
    expect(stat.value).toBe('-1 500 · -12.3%')
  })

  it('puts no sign on zero', () => {
    const stat = hoverStat(row({ delta_count: -0.2, delta_relative: 0 }), 'delta')
    expect(stat.value).toBe('0 · 0.0%')
    expect(hoverStat(row({ delta_co2_g_per_km: 0 }), 'co2_delta').value).toBe('0 g/km')
  })
})
