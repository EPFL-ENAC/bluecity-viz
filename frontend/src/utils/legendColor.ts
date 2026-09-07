import type { Encoding, MapLayerConfig } from '@/config/layerTypes'
import type { LayerSpecification } from 'maplibre-gl'

export type LegendColor = {
  color: string
  label: string
  variable?: string
}

export type DatasetLegend = MapLayerConfig & {
  colors: LegendColor[]
  isCategorical: boolean
  variable: string | undefined
  gradient: string | undefined
  showZero: boolean
}

/** The paint key that carries the colour, per layer type. */
function colorPaintProperty(layer: LayerSpecification): unknown {
  if (!layer.paint) return null
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  const paint = layer.paint as any
  return (
    paint['fill-color'] ||
    paint['line-color'] ||
    paint['fill-extrusion-color'] ||
    paint['circle-color'] ||
    null
  )
}

/** A match (or a case) paints one colour per category, not a ramp. */
function isCategoricalPaint(paintProperty: unknown): boolean {
  return (
    Array.isArray(paintProperty) && (paintProperty[0] === 'match' || paintProperty[0] === 'case')
  )
}

/** The legend entries an encoding describes, no parsing needed. */
export function legendEntriesFromEncoding(encoding: Encoding): LegendColor[] {
  if (encoding.kind === 'sequential') {
    return encoding.domain.map((value, index) => ({
      color: encoding.scheme[index],
      label: String(value)
    }))
  }

  const entries: LegendColor[] = encoding.categories.map(({ value, color }) => ({
    color,
    variable: encoding.property,
    label: String(value)
  }))

  // A default colour that is not just black stands for everything else.
  if (encoding.defaultColor !== '#000000' && encoding.defaultColor !== 'transparent') {
    entries.push({ color: encoding.defaultColor, label: 'Other' })
  }

  return entries
}

/**
 * Read the legend entries back from a layer paint expression. Used for the
 * layers that have no encoding, because their colour is not a plain ramp.
 * Returns null when the expression is not one we can read.
 */
export function generateLegendColors(layer: LayerSpecification): LegendColor[] | null {
  const paintProperty = colorPaintProperty(layer)
  if (!paintProperty) return null

  // 'match' expressions, categorical data
  if (Array.isArray(paintProperty) && paintProperty[0] === 'match') {
    const variableProperty = paintProperty[1][1]
    const stops = paintProperty.slice(2)
    const defaultColor = stops.pop()
    const legendColors: LegendColor[] = []

    for (let i = 0; i < stops.length; i += 2) {
      const value = stops[i]
      const color = stops[i + 1]

      if (value !== undefined && color !== undefined) {
        legendColors.push({
          color: color as string,
          variable: variableProperty,
          label: Array.isArray(value) ? value.join(', ') : String(value)
        })
      }
    }

    if (
      typeof defaultColor === 'string' &&
      defaultColor !== '#000000' &&
      defaultColor !== 'transparent'
    ) {
      legendColors.push({ color: defaultColor, label: 'Other' })
    }

    return legendColors
  }

  // 'interpolate' expressions, continuous data
  if (
    Array.isArray(paintProperty) &&
    paintProperty[0] === 'interpolate' &&
    paintProperty.length > 3
  ) {
    const stops = paintProperty.slice(3) // skip 'interpolate', 'linear' and the input
    const legendColors: LegendColor[] = []

    for (let i = 0; i < stops.length; i += 2) {
      legendColors.push({ color: stops[i + 1] as string, label: stops[i].toString() })
    }

    return legendColors
  }

  // A plain colour, a 'case' or an 'interpolate-hcl': nothing to show.
  return null
}

/**
 * Build the legend of one dataset layer. The encoding is the truth when the
 * layer has one, the paint expression is read back otherwise.
 */
export function datasetLegend(layer: MapLayerConfig): DatasetLegend {
  const paintProperty = colorPaintProperty(layer.layer)

  const colors = layer.encoding
    ? legendEntriesFromEncoding(layer.encoding)
    : generateLegendColors(layer.layer) || []

  const isCategorical = layer.encoding
    ? layer.encoding.kind === 'categorical'
    : isCategoricalPaint(paintProperty)

  // Only a categorical legend needs the property, its checkboxes filter on it.
  const variable = isCategorical
    ? layer.encoding
      ? layer.encoding.property
      : ((paintProperty as unknown[])[1] as unknown[])[1]
    : undefined

  return {
    ...layer,
    colors: isCategorical ? colors : colors.reverse(),
    isCategorical,
    variable: variable as string | undefined,
    gradient: !isCategorical
      ? `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`
      : undefined,
    showZero: false
  }
}

export type TrafficLegendMode =
  | 'frequency'
  | 'delta'
  | 'delta_relative'
  | 'co2'
  | 'co2_delta'
  | 'betweenness'
  | 'betweenness_delta'

export type TrafficLegend = {
  label: string
  unit: string
  colors: LegendColor[]
  gradient: string
  isCategorical: boolean
  showZero?: boolean
}

/** Same constant as the store: below 10% the relative scale is linear. */
const SYMLOG_LINEAR_LIMIT = 10

/** From max down to min, the top of the ramp is the highest value. */
const fromRange = (t: number, min: number, max: number) => max - t * (max - min)
/** From max down to zero, for the scales that start at zero. */
const fromMax = (t: number, _min: number, max: number) => max * (1 - t)

const withSign = (value: number, text: string) => `${value >= 0 ? '+' : ''}${text}`
/** Thousands as "1.2k", so the labels stay short. */
const short = (value: number) =>
  value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)
/** Same, for a value that can be negative. */
const shortSigned = (value: number) =>
  Math.abs(value) >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)

type TrafficLegendSpec = {
  label: string
  unit: string
  showZero?: boolean
  /** The value shown at position t, t goes from 0 (top) to 1 (bottom). */
  valueAt: (t: number, min: number, max: number) => number
  format: (value: number) => string
  /** Last word on the labels, for the ends of the ramp. */
  finalize?: (colors: LegendColor[], min: number, max: number) => void
}

const TRAFFIC_LEGENDS: Record<TrafficLegendMode, TrafficLegendSpec> = {
  frequency: {
    label: 'Edge Usage Frequency',
    unit: 'Relative Usage',
    valueAt: fromMax,
    format: (value) => (value * 100).toFixed(1) + '%'
  },

  delta: {
    label: 'Traffic Change',
    unit: 'Vehicle Count Difference',
    showZero: true,
    valueAt: fromRange,
    format: (value) => withSign(value, String(Math.round(value)))
  },

  delta_relative: {
    label: 'Traffic Change (Relative)',
    unit: `symlog scale  |  linear ≤ ±${SYMLOG_LINEAR_LIMIT}%`,
    showZero: true,
    // Undo the diverging symlog of the store, so the colours are spread
    // evenly along the ramp. t=0 is +max, t=0.5 is zero, t=1 is -max.
    valueAt: (t, _min, max) => {
      const c = SYMLOG_LINEAR_LIMIT
      const slMax = Math.log(1 + max / c) // max is absRelMax (positive)
      return t <= 0.5
        ? c * (Math.exp((1 - 2 * t) * slMax) - 1)
        : -(c * (Math.exp((2 * t - 1) * slMax) - 1))
    },
    format: (value) => withSign(value, `${Math.round(value)}%`),
    // Group the digits on the two ends, "+3 000%" reads better than "+3000%".
    finalize: (colors, _min, max) => {
      const fmtPct = (value: number) => withSign(value, `${Math.round(value).toLocaleString()}%`)
      colors[0].label = fmtPct(max)
      colors[colors.length - 1].label = fmtPct(-max)
    }
  },

  co2: {
    label: 'CO₂ Emissions',
    unit: 'g CO₂/km per use',
    valueAt: fromRange,
    format: (value) => `${Math.round(value)} g/km`
  },

  co2_delta: {
    label: 'CO₂ Emissions Change',
    unit: 'Δ g CO₂/km (freq-weighted)',
    showZero: true,
    valueAt: fromRange,
    format: (value) => withSign(value, `${value.toFixed(2)} g/km`)
  },

  betweenness: {
    label: 'Betweenness Centrality',
    unit: 'Norm. edge flow (veh/day)',
    valueAt: fromMax,
    format: short
  },

  betweenness_delta: {
    label: 'Betweenness Change',
    unit: 'Δ norm. edge flow (veh/day)',
    showZero: true,
    valueAt: fromRange,
    format: (value) => withSign(value, shortSigned(value))
  }
}

/** Build the traffic analysis legend for one visualization mode. */
export function trafficLegend(
  mode: TrafficLegendMode,
  min: number,
  max: number,
  getColor: (value: number) => [number, number, number]
): TrafficLegend {
  const spec = TRAFFIC_LEGENDS[mode] ?? TRAFFIC_LEGENDS.frequency
  const steps = 40
  const colors: LegendColor[] = []

  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1)
    const value = spec.valueAt(t, min, max)
    const [r, g, b] = getColor(value)
    colors.push({ color: `rgb(${r}, ${g}, ${b})`, label: spec.format(value) })
  }

  if (spec.finalize) spec.finalize(colors, min, max)

  return {
    label: spec.label,
    unit: spec.unit,
    colors,
    gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
    isCategorical: false,
    ...(spec.showZero ? { showZero: true } : {})
  }
}
