import type { CustomSourceSpecification, MapLayerConfig } from '@/config/layerTypes'
import type { LayerSpecification } from 'maplibre-gl'

const isDev = import.meta.env.DEV
const API_BASE_URL = isDev ? 'http://localhost:8000/api/v1/routes' : '/api/v1/routes'

const HABITAT_MAX = 100

const habitatSource: CustomSourceSpecification = {
  type: 'geojson',
  id: 'habitat_density',
  label: 'Habitat Density - Biodiversity',
  data: `${API_BASE_URL}/habitat-geojson`
}

export const biodiversitySources: CustomSourceSpecification[] = [habitatSource]

export const biodiversityLayers: MapLayerConfig[] = [
  {
    id: 'habitat_density',
    label: 'Habitat Density (10m buffer)',
    unit: 'm²/m',
    info: 'Total habitat area within a 10m buffer around each road, normalised by road length (m²/m). Data: Swiss Lebensraumkarte.',
    source: habitatSource,
    layer: {
      id: 'habitat_density-layer',
      type: 'line',
      source: 'habitat_density',
      filter: ['>', ['get', 'habitat_density_m2_per_m'], 0],
      paint: {
        'line-color': [
          'interpolate',
          ['linear'],
          ['get', 'habitat_density_m2_per_m'],
          1,
          '#d5f0d0', // barely present
          5,
          '#8ed68a', // low-medium
          20,
          '#3db038', // medium
          50,
          '#1a7d17', // high
          100,
          '#0b4a09' // very dense
        ],
        'line-width': [
          'interpolate',
          ['linear'],
          ['get', 'habitat_density_m2_per_m'],
          0,
          3,
          HABITAT_MAX,
          5
        ]
      }
    } as LayerSpecification
  }
]
