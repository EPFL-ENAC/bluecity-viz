// Deterministic input for the traffic store scale tests.
//
// The numbers in EXPECTED_SCALES were recorded from the store before the
// single-pass refactor of setEdgeUsage. They are the contract: the new code
// must give the same min/max and the same colors for every mode.

import type { EdgeUsageStats } from '@/stores/trafficAnalysis'

/** Small LCG so the fixture is the same on every machine. */
function lcg(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

/**
 * 300 edges with every field the six visualization modes need, plus the cases
 * that matter: zeros, negative deltas, and a few CO2 outliers so the 98th
 * percentile in robustMax is not the plain max.
 */
export function makeUsage(): EdgeUsageStats[] {
  const rand = lcg(20250907)
  const out: EdgeUsageStats[] = []
  for (let i = 0; i < 300; i++) {
    const frequency = +(rand() * 0.2).toFixed(6)
    const count = Math.round(frequency * 500)
    // every 7th edge has no CO2 and no betweenness, like a service road
    const quiet = i % 7 === 0
    // 3 outliers with a huge CO2/km (zero length stubs in real data)
    const outlier = i === 11 || i === 97 || i === 240
    const co2 = quiet ? 0 : outlier ? 4000 + rand() * 1000 : +(20 + rand() * 300).toFixed(4)
    // half the edges move, some up some down, some not at all
    const moves = i % 2 === 0
    const deltaFrequency = moves ? +((rand() - 0.5) * 0.05).toFixed(6) : 0
    const deltaCount = moves ? Math.round(deltaFrequency * 500) : 0
    out.push({
      u: 1000 + i,
      v: 2000 + i,
      count,
      frequency,
      delta_count: deltaCount,
      delta_frequency: deltaFrequency,
      co2_per_km: co2,
      betweenness_centrality: quiet ? 0 : +(rand() * 1500).toFixed(4),
      delta_betweenness: moves ? +((rand() - 0.5) * 200).toFixed(4) : 0
    })
  }
  return out
}

/** Min, max and a few colors per mode, recorded from the store before the refactor. */
export const EXPECTED_SCALES = {
  autoSelected: 'delta',
  modes: [
    'frequency',
    'co2',
    'delta',
    'delta_relative',
    'co2_delta',
    'betweenness',
    'betweenness_delta'
  ],
  // colors are getColor(min), getColor(middle), getColor(max), getColor(0)
  perMode: {
    frequency: {
      legendMode: 'frequency',
      min: 0,
      max: 0.199806,
      colors: [
        [68, 1, 84],
        [33, 145, 140],
        [253, 231, 37],
        [68, 1, 84]
      ]
    },
    co2: {
      legendMode: 'co2',
      min: 20.0789,
      max: 316.2941,
      colors: [
        [68, 1, 84],
        [33, 144, 141],
        [253, 231, 37],
        [68, 1, 84]
      ]
    },
    delta: {
      legendMode: 'delta',
      min: -12,
      max: 12,
      colors: [
        [94, 79, 162],
        [251, 248, 176],
        [158, 1, 66],
        [251, 248, 176]
      ]
    },
    delta_relative: {
      legendMode: 'delta_relative',
      min: -362.16979564711744,
      max: 362.16979564711744,
      colors: [
        [94, 79, 162],
        [251, 248, 176],
        [158, 1, 66],
        [251, 248, 176]
      ]
    },
    co2_delta: {
      legendMode: 'co2_delta',
      min: -6,
      max: 6,
      colors: [
        [94, 79, 162],
        [251, 248, 176],
        [158, 1, 66],
        [251, 248, 176]
      ]
    },
    betweenness: {
      legendMode: 'betweenness',
      min: 0,
      max: 1498.7274,
      colors: [
        [68, 1, 84],
        [33, 145, 140],
        [253, 231, 37],
        [68, 1, 84]
      ]
    },
    betweenness_delta: {
      legendMode: 'betweenness_delta',
      min: -98.8217,
      max: 98.8217,
      colors: [
        [94, 79, 162],
        [251, 248, 176],
        [158, 1, 66],
        [251, 248, 176]
      ]
    }
  }
} as const

/** Everything the store gives to its consumers. Must not change. */
export const EXPECTED_PUBLIC_KEYS = [
  'activeVisualization',
  'area',
  'areaError',
  'areaId',
  'areaInfo',
  'areaLimits',
  'availableVisualizations',
  'clearResults',
  'closePanel',
  'colorScale',
  'congestionIterations',
  'draftArea',
  'elasticDemand',
  'ensureArea',
  'enterPickMode',
  'exitPickMode',
  'filterBusRoutes',
  'forgetAreaId',
  'getBaseline',
  'getColor',
  'graphKey',
  'hasCalculatedRoutes',
  'impactStatistics',
  'isBuildingArea',
  'isStale',
  'isCalculating',
  'isLoading',
  'isOpen',
  'isRestoring',
  'legendMode',
  'loadAreaLimits',
  'loadGraphInfo',
  'maxValue',
  'minValue',
  'moveDraft',
  'newEdgeUsage',
  'nodePairs',
  'odPairs',
  'odPairsDefault',
  'odPairsFull',
  'odPairsMax',
  'openPanel',
  'originalEdgeUsage',
  'pickMode',
  'restoreState',
  'resultOdPairs',
  'resultScenarioHash',
  'resultTotals',
  'setActiveVisualization',
  'setArea',
  'setDraftRadius',
  'setEdgeUsage',
  'setNodePairs',
  'setOdPairs',
  'togglePanel',
  'useCongestionModel',
  'useDefaultArea'
]

/** The refs the store puts in the pinia state. The scales must stay out of it. */
export const EXPECTED_STATE_KEYS = [
  'activeVisualization',
  'area',
  'areaError',
  'areaId',
  'areaInfo',
  'areaLimits',
  'colorScale',
  'congestionIterations',
  'draftArea',
  'elasticDemand',
  'filterBusRoutes',
  'impactStatistics',
  'isBuildingArea',
  'isCalculating',
  'isLoading',
  'isOpen',
  'isRestoring',
  'legendMode',
  'maxValue',
  'minValue',
  'newEdgeUsage',
  'nodePairs',
  'odPairs',
  'odPairsDefault',
  'odPairsFull',
  'odPairsMax',
  'originalEdgeUsage',
  'pickMode',
  'resultOdPairs',
  'resultScenarioHash',
  'useCongestionModel'
]
