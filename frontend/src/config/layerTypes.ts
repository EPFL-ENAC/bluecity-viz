import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export type CustomLayerSpecification = LayerSpecification & { groupId: string }
export type CustomSourceSpecification = VectorSourceSpecification & {
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
export interface MapLayerConfig {
  id: string
  label: string
  unit: string
  info: string
  source: CustomSourceSpecification
  layer: LayerSpecification
}

export const baseUrlOptions = {
  prod: 'https://enacit4r-cdn.epfl.ch/bluecity',
  dev: '/geodata'
}

export const baseUrl = import.meta.env.DEV ? baseUrlOptions.dev : baseUrlOptions.prod
