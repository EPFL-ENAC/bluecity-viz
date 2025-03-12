import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export const sp0MigrationLayers: MapLayerConfig[] = [
  // SPO MIGRATION LAYERS
  // Population Density Layer
  {
    id: 'lausanne_pop_density',
    label: 'Population Density per Hectare',
    unit: 'people/ha',
    info: 'Total population per hectare in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_pop_density-layer',
      type: 'fill-extrusion',
      source: 'lausanne_pop_density',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': ['get', 'pop_mean'],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'pop_mean']],
          0,
          '#e3f2fd', // Lightest blue
          50,
          '#90caf9', // Light blue
          100,
          '#42a5f5', // Medium blue
          200,
          '#1976d2', // Dark blue
          500,
          '#0d47a1' // Darkest blue
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Birth Rate Layer
  {
    id: 'lausanne_birth_rate',
    label: 'Birth Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'Birth rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_birth_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_birth_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'birth_rate']],
          10 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'birth_rate']],
          0,
          '#e8f5e9', // Lightest green
          5,
          '#a5d6a7', // Light green
          10,
          '#66bb6a', // Medium green
          15,
          '#388e3c', // Dark green
          20,
          '#1b5e20' // Darkest green
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Death Rate Layer
  {
    id: 'lausanne_death_rate',
    label: 'Death Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'Death rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_death_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_death_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'death_rate']],
          10 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'death_rate']],
          0,
          '#f5f5f5', // Lightest gray
          5,
          '#e0e0e0', // Light gray
          10,
          '#9e9e9e', // Medium gray
          15,
          '#616161', // Dark gray
          20,
          '#212121' // Darkest gray
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Internal In-migration Rate Layer
  {
    id: 'lausanne_inmigration_rate',
    label: 'Internal In-migration Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'Internal in-migration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_inmigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_inmigration_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'inmigration_rate']],
          2 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'inmigration_rate']],
          0,
          '#f3e5f5', // Lightest purple
          25,
          '#ce93d8', // Light purple
          50,
          '#ab47bc', // Medium purple
          75,
          '#7b1fa2', // Dark purple
          100,
          '#4a148c' // Darkest purple
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // Internal Out-migration Rate Layer
  {
    id: 'lausanne_outmigration_rate',
    label: 'Internal Out-migration Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'Internal out-migration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_outmigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_outmigration_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'outmigration_rate']],
          2 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'outmigration_rate']],
          0,
          '#fff3e0', // Lightest orange
          25,
          '#ffcc80', // Light orange
          50,
          '#ffa726', // Medium orange
          75,
          '#f57c00', // Dark orange
          100,
          '#e65100' // Darkest orange
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // International Immigration Rate Layer
  {
    id: 'lausanne_immigration_rate',
    label: 'International Immigration Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'International immigration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_immigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_immigration_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'immigration_rate']],
          2 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'immigration_rate']],
          0,
          '#e0f2f1', // Lightest teal
          25,
          '#80cbc4', // Light teal
          50,
          '#26a69a', // Medium teal
          75,
          '#00796b', // Dark teal
          100,
          '#004d40' // Darkest teal
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  },

  // International Emigration Rate Layer
  {
    id: 'lausanne_emigration_rate',
    label: 'International Emigration Rate per 1,000 Population',
    unit: 'per 1,000',
    info: 'International emigration rate per 1,000 population in Lausanne (2011-2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_emigration_rate-layer',
      type: 'fill-extrusion',
      source: 'lausanne_emigration_rate',
      'source-layer': 'lausanne_migration_2011_2023',
      paint: {
        'fill-extrusion-height': [
          '*',
          ['to-number', ['get', 'emigration_rate']],
          2 // Multiplier to make the visualization more visible
        ],
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'emigration_rate']],
          0,
          '#efebe9', // Lightest brown
          10,
          '#bcaaa4', // Light brown
          20,
          '#8d6e63', // Medium brown
          30,
          '#5d4037', // Dark brown
          40,
          '#3e2723' // Darkest brown
        ],
        'fill-extrusion-opacity': 0.8,
        'fill-extrusion-base': 0
      }
    } as LayerSpecification
  }
]
