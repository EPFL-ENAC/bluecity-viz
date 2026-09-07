/**
 * The routing result, drawn on the graph.
 *
 * The numbers come back per directed edge. The map shows them on the street
 * centreline with both directions summed (the guideline: per lane data only
 * when the visualisation is directional, which none of the six modes are).
 *
 * The colour goes in as feature-state `c` on one feature per street, and the
 * data layers are filtered to that same id list. Switching mode is one pass
 * of setFeatureState, no source reload.
 */
import type { Street } from '@/stores/scenario'
import type { EdgeUsageStats } from '@/stores/trafficAnalysis'
import type { TrafficLegendMode } from '@/utils/legendColor'

/** The seven numbers a street can be coloured by, summed over both directions. */
export interface StreetTotals {
  key: string
  name: string
  /** the feature the colour is written on, and the one the data layers draw */
  id: number
  bus: boolean
  /** vehicles on the street, both directions summed */
  count: number
  frequency: number
  delta_count: number
  delta_relative: number
  co2_per_km: number
  co2_delta: number
  betweenness_centrality: number
  delta_betweenness: number
  /** kept to work out delta_relative, not shown on its own */
  delta_frequency: number
}

/** Read the value one visualisation mode shows. */
export function valueOf(row: StreetTotals, mode: TrafficLegendMode): number {
  switch (mode) {
    case 'delta':
      return row.delta_count
    case 'delta_relative':
      return row.delta_relative
    case 'co2':
      return row.co2_per_km
    case 'co2_delta':
      return row.co2_delta
    case 'betweenness':
      return row.betweenness_centrality
    case 'betweenness_delta':
      return row.delta_betweenness
    case 'frequency':
    default:
      return row.frequency
  }
}

/**
 * Join the per-edge numbers to the streets and sum the two directions.
 *
 * A row whose street is not in the graph is dropped: the backend keys by
 * `(u, v)` and the graph has 71 parallel edges, so a miss is possible.
 */
export function streetTotals(
  usage: EdgeUsageStats[],
  streets: Map<string, Street>
): StreetTotals[] {
  const byKey = new Map<string, StreetTotals>()

  for (const stat of usage) {
    const key = stat.u <= stat.v ? `${stat.u}-${stat.v}` : `${stat.v}-${stat.u}`
    const street = streets.get(key)
    if (!street) continue

    const id = street.fwdId ?? street.bwdId
    if (id === undefined) continue

    let row = byKey.get(key)
    if (!row) {
      row = {
        key,
        id,
        name: street.name,
        bus: street.bus,
        count: 0,
        frequency: 0,
        delta_count: 0,
        delta_relative: 0,
        co2_per_km: 0,
        co2_delta: 0,
        betweenness_centrality: 0,
        delta_betweenness: 0,
        delta_frequency: 0
      }
      byKey.set(key, row)
    }

    const deltaFrequency = stat.delta_frequency ?? 0
    const co2PerKm = stat.co2_per_km ?? 0

    row.count += stat.count ?? 0
    row.frequency += stat.frequency
    row.delta_frequency += deltaFrequency
    row.delta_count += stat.delta_count ?? 0
    row.co2_per_km += co2PerKm
    row.co2_delta += co2PerKm * deltaFrequency
    row.betweenness_centrality += stat.betweenness_centrality ?? 0
    row.delta_betweenness += stat.delta_betweenness ?? 0
  }

  // The relative change needs the totals, so it is a second pass over the
  // streets. It is a percentage of the traffic the street had before.
  for (const row of byKey.values()) {
    const before = row.frequency - row.delta_frequency
    row.delta_relative = before > 0.0001 ? (row.delta_frequency / before) * 100 : 0
  }

  return [...byKey.values()]
}

/**
 * The streets that absorbed the diverted traffic: the biggest gains among the
 * streets the user did not touch.
 */
export function topAbsorbers(
  rows: StreetTotals[],
  modified: Set<string>,
  count = 3
): StreetTotals[] {
  return rows
    .filter((row) => !modified.has(row.key) && row.delta_count > 0)
    .sort((a, b) => b.delta_count - a.delta_count)
    .slice(0, count)
}
