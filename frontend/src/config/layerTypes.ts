import type { LayerSpecification, SourceSpecification } from 'maplibre-gl'

export interface MapLayerConfig {
  id: string
  label: string
  unit: string
  info: string
  source: SourceSpecification
  layer: LayerSpecification
}

export const baseUrlOptions = {
  prod: 'https://enacit4r-cdn.epfl.ch/bluecity',
  dev: '/geodata'
}

export const baseUrl = import.meta.env.DEV ? baseUrlOptions.dev : baseUrlOptions.prod
