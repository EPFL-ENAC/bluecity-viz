import { mapConfig } from '@/config/mapConfig'
import { datasetLegend, trafficLegend, type TrafficLegendMode } from '@/utils/legendColor'
import { describe, expect, it } from 'vitest'

// Fake colour scale: deterministic, so the snapshot only tracks the labels,
// the stops and the shape of the legend.
const fakeGetColor = (value: number): [number, number, number] => [
  Math.abs(Math.round(value)) % 256,
  0,
  0
]

const MODES: TrafficLegendMode[] = [
  'frequency',
  'delta',
  'delta_relative',
  'co2',
  'co2_delta',
  'betweenness',
  'betweenness_delta'
]

describe('dataset legends', () => {
  it('builds the same legend for every layer', () => {
    const legends = mapConfig.layers.map((layer) => {
      const legend = datasetLegend(layer)
      return {
        id: layer.layer.id,
        colors: legend.colors,
        isCategorical: legend.isCategorical,
        variable: legend.variable,
        gradient: legend.gradient,
        showZero: legend.showZero
      }
    })
    expect(legends).toMatchSnapshot()
  })

  it('covers every layer of the registry', () => {
    expect(mapConfig.layers.length).toBeGreaterThan(0)
  })
})

describe('traffic legend', () => {
  it.each(MODES)('builds the %s legend', (mode) => {
    expect(trafficLegend(mode, -50, 120, fakeGetColor)).toMatchSnapshot()
  })

  it('builds the same legend with a zero range', () => {
    expect(trafficLegend('frequency', 0, 0, fakeGetColor)).toMatchSnapshot()
  })
})
