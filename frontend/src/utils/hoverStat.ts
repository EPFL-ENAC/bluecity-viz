/**
 * The number the hover card shows for one street: the value of the layer on
 * the map, with its unit, both directions summed like the map.
 *
 * The legend has short labels ("1.2k") for the ends of a ramp. The card shows
 * one street, so it gives the full number.
 */
import type { StreetTotals } from '@/composables/useResultStates'
import type { TrafficLegendMode } from '@/utils/legendColor'

export interface HoverStat {
  label: string
  value: string
}

/** A rounded number, digits grouped with a plain space ("12 345"). */
export function number(value: number): string {
  // fr-CH groups with a narrow no-break space (an apostrophe in some ICU
  // builds, Node for one); use a plain one
  return Math.round(value)
    .toLocaleString('fr-CH')
    .replace(/[\u202f\u00a0\u2009'\u2019]/g, ' ')
}

/** "+" in front of a positive value. The minus comes with the number. */
function sign(value: number): string {
  return value > 0 ? '+' : ''
}

function signed(value: number): string {
  // Math.round(-0.4) is -0, which would print as "-0"
  return Math.round(value) === 0 ? '0' : `${sign(value)}${number(value)}`
}

function percent(value: number): string {
  return `${sign(value)}${value.toFixed(1)}%`
}

/** Grams per km as "850 g/km" or "12.4 kg/km". */
function gramsPerKm(value: number): string {
  if (Math.abs(value) < 1000) return `${number(value)} g/km`
  return `${(value / 1000).toFixed(1)} kg/km`
}

function signedGramsPerKm(value: number): string {
  if (Math.round(value) === 0) return '0 g/km'
  return `${sign(value)}${gramsPerKm(value)}`
}

/** The label and the formatted value of one layer, for one street. */
export function hoverStat(row: StreetTotals, mode: TrafficLegendMode): HoverStat {
  switch (mode) {
    case 'delta':
      return {
        label: 'Change',
        value: `${signed(row.delta_count)} · ${percent(row.delta_relative)}`
      }
    case 'delta_relative':
      return {
        label: 'Relative change',
        value: `${percent(row.delta_relative)} · ${signed(row.delta_count)}`
      }
    case 'co2':
      return { label: 'CO₂', value: gramsPerKm(row.co2_g_per_km) }
    case 'co2_delta':
      return { label: 'CO₂ change', value: signedGramsPerKm(row.delta_co2_g_per_km) }
    case 'betweenness':
      return { label: 'Betweenness', value: `${number(row.betweenness_centrality)} veh/day` }
    case 'betweenness_delta':
      return {
        label: 'Betweenness change',
        value: `${signed(row.delta_betweenness)} veh/day`
      }
    case 'frequency':
    default:
      return { label: 'Vehicles / day', value: number(row.count) }
  }
}
