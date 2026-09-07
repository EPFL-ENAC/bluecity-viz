import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
  VectorSourceSpecification
} from 'maplibre-gl'

export type CustomLayerSpecification = LayerSpecification & { groupId: string }
export type CustomSourceSpecification = (VectorSourceSpecification | GeoJSONSourceSpecification) & {
  id: string
  label?: string
}

export type LayerGroup = {
  id: string
  label: string
  expanded: boolean
  multiple: boolean
  layers: MapLayerConfig[]
}

/**
 * How the values of one property become colours. The map turns it into a
 * paint expression, the legend reads it back without parsing anything.
 */
export type SequentialEncoding = {
  kind: 'sequential'
  /** Feature property, read as a number. */
  property: string
  /** Stop values, same length as scheme. */
  domain: number[]
  /** Colour of each stop. */
  scheme: string[]
}

export type CategoricalEncoding = {
  kind: 'categorical'
  property: string
  categories: { value: string; color: string }[]
  /** Colour for a value that is in no category. */
  defaultColor: string
}

export type Encoding = SequentialEncoding | CategoricalEncoding

/** Same as a MapLibre layer, without the fields defineLayer fills in. */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never
export type DatasetLayerInput = DistributiveOmit<LayerSpecification, 'id' | 'source'> & {
  id?: string
  source?: string
}

export interface MapLayerConfig {
  id: string
  label: string
  unit: string
  info: string
  source: CustomSourceSpecification
  layer: LayerSpecification
  encoding?: Encoding
}

export const baseUrlOptions = {
  prod: 'https://enacit4r-cdn.epfl.ch/bluecity',
  dev: '/geodata'
}

export const baseUrl = import.meta.env.DEV ? baseUrlOptions.dev : baseUrlOptions.prod
