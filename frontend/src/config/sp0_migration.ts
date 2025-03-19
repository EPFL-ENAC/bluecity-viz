import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export const sp0MigrationLayers: MapLayerConfig[] = [
  // SPO MIGRATION LAYERS
  // Population Density Layer
  {
    id: 'lausanne_pop_density',
    label: 'Population Density',
    unit: 'people/ha',
    info: 'Total population per hectare in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_pop_density-layer',
      type: 'fill-extrusion',
      source: 'lausanne_pop_density',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['get', 'pop_mean']],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'pop_mean']],
          200,
          '#e3f2fd', // Min value: ~200
          400,
          '#90caf9',
          600,
          '#42a5f5',
          800,
          '#1976d2',
          1140,
          '#0d47a1' // Max value: ~1140
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Birth Rate Layer
  {
    id: 'lausanne_birth_rate',
    label: 'Birth Rate',
    unit: 'per 1,000',
    info: 'Birth rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_birth_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_birth_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['*', ['to-number', ['get', 'birth_rate']], 5]],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'birth_rate']],
          3,
          '#e8f5e9', // Min value: ~3.5
          10,
          '#a5d6a7',
          20,
          '#66bb6a',
          30,
          '#388e3c',
          41,
          '#1b5e20' // Max value: ~41
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Death Rate Layer
  {
    id: 'lausanne_death_rate',
    label: 'Death Rate',
    unit: 'per 1,000',
    info: 'Death rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_death_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_death_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['*', ['to-number', ['get', 'death_rate']], 2]],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'death_rate']],
          1,
          '#ffebee', // Min value: ~1.8
          25,
          '#ef9a9a',
          50,
          '#e57373',
          75,
          '#c62828',
          109,
          '#b71c1c' // Max value: ~109
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Internal In-migration Rate Layer
  {
    id: 'lausanne_inmigration_rate',
    label: 'Internal In-migration',
    unit: 'per 1,000',
    info: 'Internal in-migration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_inmigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_inmigration_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['*', ['to-number', ['get', 'inmigration_rate']], 0.5]],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'inmigration_rate']],
          20,
          '#f3e5f5', // Min value: ~21
          125,
          '#ce93d8',
          250,
          '#ab47bc',
          375,
          '#7b1fa2',
          505,
          '#4a148c' // Max value: ~505
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Internal Out-migration Rate Layer
  {
    id: 'lausanne_outmigration_rate',
    label: 'Internal Out-migration',
    unit: 'per 1,000',
    info: 'Internal out-migration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_outmigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_outmigration_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': [
          'max',
          2,
          ['*', ['to-number', ['get', 'outmigration_rate']], 0.5]
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'outmigration_rate']],
          40,
          '#fff3e0', // Min value: ~41
          110,
          '#ffcc80',
          180,
          '#ffa726',
          250,
          '#f57c00',
          337,
          '#e65100' // Max value: ~337
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // International Immigration Rate Layer
  {
    id: 'lausanne_immigration_rate',
    label: 'International Immigration',
    unit: 'per 1,000',
    info: 'International immigration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_immigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_immigration_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['*', ['to-number', ['get', 'immigration_rate']], 0.2]],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'immigration_rate']],
          2,
          '#e0f2f1', // Min value: ~2.4
          250,
          '#80cbc4',
          500,
          '#26a69a',
          750,
          '#00796b',
          1014,
          '#004d40' // Max value: ~1014
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // International Emigration Rate Layer
  {
    id: 'lausanne_emigration_rate',
    label: 'International Emigration',
    unit: 'per 1,000',
    info: 'International emigration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      attribution: 'https://www.bfs.admin.ch/',
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_emigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_emigration_rate',
      'source-layer': 'lausanne_migration',
      paint: {
        // Add max function to ensure minimum height of 2
        'fill-extrusion-height': ['max', 2, ['*', ['to-number', ['get', 'emigration_rate']], 0.2]],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'emigration_rate']],
          2,
          '#efebe9', // Min value: ~2.8
          200,
          '#bcaaa4',
          400,
          '#8d6e63',
          600,
          '#5d4037',
          798,
          '#3e2723' // Max value: ~798
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  }
]
