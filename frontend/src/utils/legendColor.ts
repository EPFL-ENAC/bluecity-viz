import type { LayerSpecification } from 'maplibre-gl'
import type { MapLayerConfig } from '@/config/layerTypes'

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

/**
 * Read the legend entries back from a layer paint expression.
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

  return null
}

/** Build the legend of one dataset layer. */
export function datasetLegend(layer: MapLayerConfig): DatasetLegend {
  const colors = generateLegendColors(layer.layer) || []
  const paintProperty = colorPaintProperty(layer.layer)

  const isCategorical =
    Array.isArray(paintProperty) && (paintProperty[0] === 'match' || paintProperty[0] === 'case')

  return {
    ...layer,
    colors: isCategorical ? colors : colors.reverse(),
    isCategorical,
    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    variable: (paintProperty as any)[1][1],
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

/** Build the traffic analysis legend for one visualization mode. */
export function trafficLegend(
  mode: TrafficLegendMode,
  min: number,
  max: number,
  getColor: (value: number) => [number, number, number]
): TrafficLegend {
  const colors: LegendColor[] = []
  const steps = 40

  if (mode === 'delta') {
    // Delta mode: actual min/max from the store (vehicle count differences)
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      // From max (positive, red) to min (negative, blue)
      const value = max - t * (max - min)
      const [r, g, b] = getColor(value)
      const count = Math.round(value)
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: value >= 0 ? `+${count}` : `${count}`
      })
    }

    return {
      label: 'Traffic Change',
      unit: 'Vehicle Count Difference',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false,
      showZero: true
    }
  } else if (mode === 'co2_delta') {
    // CO2 delta: co2_per_km x delta_frequency -> g/km
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max - t * (max - min)
      const [r, g, b] = getColor(value)
      const sign = value >= 0 ? '+' : ''
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: `${sign}${value.toFixed(2)} g/km`
      })
    }

    return {
      label: 'CO₂ Emissions Change',
      unit: 'Δ g CO₂/km (freq-weighted)',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false,
      showZero: true
    }
  } else if (mode === 'co2') {
    // CO2: fixed scale [CO2_KM_MIN, CO2_KM_MAX]
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max - t * (max - min)
      const [r, g, b] = getColor(value)
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: `${Math.round(value)} g/km`
      })
    }

    return {
      label: 'CO₂ Emissions',
      unit: 'g CO₂/km per use',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false
    }
  } else if (mode === 'betweenness') {
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max * (1 - t)
      const [r, g, b] = getColor(value)
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)
      })
    }

    return {
      label: 'Betweenness Centrality',
      unit: 'Norm. edge flow (veh/day)',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false
    }
  } else if (mode === 'betweenness_delta') {
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max - t * (max - min)
      const [r, g, b] = getColor(value)
      const sign = value >= 0 ? '+' : ''
      const abs = Math.abs(value)
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: `${sign}${abs >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(0)}`
      })
    }

    return {
      label: 'Betweenness Change',
      unit: 'Δ norm. edge flow (veh/day)',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false,
      showZero: true
    }
  } else if (mode === 'delta_relative') {
    // Sample the gradient in symlog space so the ramp looks evenly spread.
    // Same constant=10 as the store: linear within ±10%, log beyond.
    const C = 10
    const slMax = Math.log(1 + max / C) // max is absRelMax (positive)

    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1) // t in [0, 1]
      // Invert the diverging symlog transform to get the value at this position
      const value =
        t <= 0.5
          ? C * (Math.exp((1 - 2 * t) * slMax) - 1) // positive half: t=0 -> max, t=0.5 -> 0
          : -(C * (Math.exp((2 * t - 1) * slMax) - 1)) // negative half: t=0.5 -> 0, t=1 -> -max
      const [r, g, b] = getColor(value)
      const sign = value >= 0 ? '+' : ''
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: `${sign}${Math.round(value)}%`
      })
    }

    // Nicer end labels (e.g. "+3 000%" instead of "+3000%")
    const fmtPct = (v: number) => {
      const sign = v >= 0 ? '+' : ''
      return `${sign}${Math.round(v).toLocaleString()}%`
    }
    colors[0].label = fmtPct(max)
    colors[colors.length - 1].label = fmtPct(-max)

    return {
      label: 'Traffic Change (Relative)',
      unit: `symlog scale  |  linear ≤ ±${C}%`,
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false,
      showZero: true
    }
  } else {
    // Frequency: actual max frequency from the store
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max * (1 - t)
      const [r, g, b] = getColor(value)
      colors.push({
        color: `rgb(${r}, ${g}, ${b})`,
        label: (value * 100).toFixed(1) + '%'
      })
    }

    return {
      label: 'Edge Usage Frequency',
      unit: 'Relative Usage',
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false
    }
  }
}
