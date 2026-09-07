import type {
  ColorSpecification,
  DataDrivenPropertyValueSpecification,
  LayerSpecification
} from 'maplibre-gl'
import type {
  CustomSourceSpecification,
  DatasetLayerInput,
  Encoding,
  LayerGroup,
  MapLayerConfig
} from '@/config/layerTypes'

/** The paint key that carries the colour, per layer type. */
const COLOR_KEYS = {
  fill: 'fill-color',
  line: 'line-color',
  circle: 'circle-color',
  'fill-extrusion': 'fill-extrusion-color'
} as const

export function colorKey(type: LayerSpecification['type']): string | null {
  return type in COLOR_KEYS ? COLOR_KEYS[type as keyof typeof COLOR_KEYS] : null
}

/**
 * Turn an encoding into the paint expression MapLibre wants.
 * Sequential gives an interpolate ramp, categorical gives a match.
 */
export function buildPaint(
  encoding: Encoding
): DataDrivenPropertyValueSpecification<ColorSpecification> {
  if (encoding.kind === 'sequential') {
    if (encoding.domain.length !== encoding.scheme.length) {
      throw new Error(
        `encoding on "${encoding.property}": ${encoding.domain.length} stops for ${encoding.scheme.length} colours`
      )
    }
    if (encoding.domain.length < 2) {
      throw new Error(`encoding on "${encoding.property}": needs at least two stops`)
    }

    const stops: (number | string)[] = []
    encoding.domain.forEach((value, index) => stops.push(value, encoding.scheme[index]))

    // MapLibre types expressions as tuples, an array built at runtime cannot
    // match them. The shape is checked by the config tests instead.
    return [
      'interpolate',
      ['linear'],
      ['to-number', ['get', encoding.property]],
      ...stops
    ] as unknown as DataDrivenPropertyValueSpecification<ColorSpecification>
  }

  if (encoding.categories.length === 0) {
    throw new Error(`encoding on "${encoding.property}": needs at least one category`)
  }

  const branches: string[] = []
  encoding.categories.forEach(({ value, color }) => branches.push(value, color))

  return [
    'match',
    ['get', encoding.property],
    ...branches,
    encoding.defaultColor
  ] as unknown as DataDrivenPropertyValueSpecification<ColorSpecification>
}

export interface LayerDefinition {
  id: string
  label: string
  unit: string
  info: string
  source: CustomSourceSpecification
  /** Optional. When set, it writes the colour paint property and the legend. */
  encoding?: Encoding
  layer: DatasetLayerInput
}

/**
 * Declare one dataset layer. It fills the layer id (<id>-layer) and the
 * source id, and writes the colour paint property when an encoding is given.
 */
export function defineLayer(def: LayerDefinition): MapLayerConfig {
  const type = def.layer.type
  const paint = { ...(def.layer.paint as Record<string, unknown> | undefined) }

  if (def.encoding) {
    const key = colorKey(type)
    if (!key) {
      throw new Error(`layer "${def.id}": a ${type} layer takes no colour encoding`)
    }
    if (paint[key] !== undefined) {
      throw new Error(`layer "${def.id}": ${key} is set twice, by paint and by encoding`)
    }
    paint[key] = buildPaint(def.encoding)
  }

  const layer = {
    ...def.layer,
    id: def.layer.id ?? `${def.id}-layer`,
    source: def.source.id,
    ...(Object.keys(paint).length > 0 ? { paint } : {})
  }

  return {
    id: def.id,
    label: def.label,
    unit: def.unit,
    info: def.info,
    source: def.source,
    ...(def.encoding ? { encoding: def.encoding } : {}),
    // TypeScript cannot prove a spread still matches the layer type it came
    // from. This is the only widening, the 37 casts in the config files are gone.
    layer: layer as unknown as MapLayerConfig['layer']
  }
}

/** Declare one group of the layers panel. */
export function defineGroup(group: {
  id: string
  label: string
  multiple: boolean
  expanded?: boolean
  layers: MapLayerConfig[]
}): LayerGroup {
  return {
    id: group.id,
    label: group.label,
    expanded: group.expanded ?? false,
    multiple: group.multiple,
    layers: group.layers
  }
}
