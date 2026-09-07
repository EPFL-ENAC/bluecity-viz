import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// Shared source configuration for all SP0 migration layers
const migrationSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'lausanne_migration',
  label: 'Lausanne Migration Data - SP0',
  attribution: 'https://www.bfs.admin.ch/',
  url: `pmtiles://${baseUrl}/lausanne_migration_2011_2023_2.pmtiles`,
  minzoom: 5
}

/** Same block on every layer: flat base, height at least 2, see through. */
function extrusion(height: unknown) {
  return {
    'fill-extrusion-height': height,
    'fill-extrusion-opacity': 0.8,
    'fill-extrusion-base': 0
  } as Record<string, unknown>
}

/** Height of the block, from the value of one property. */
function scaledHeight(property: string, factor: number) {
  return ['max', 2, ['*', ['to-number', ['get', property]], factor]]
}

export const sp0MigrationGroup = defineGroup({
  id: 'sp0_migration',
  label: 'SP0 Migration',
  multiple: false,
  layers: [
    defineLayer({
      id: 'lausanne_pop_density',
      label: 'Population Density',
      unit: 'people/ha',
      info: 'Total population per hectare in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'pop_mean',
        // Data goes from about 200 to about 1140
        domain: [200, 400, 600, 800, 1140],
        scheme: ['#e3f2fd', '#90caf9', '#42a5f5', '#1976d2', '#0d47a1']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(['max', 2, ['get', 'pop_mean']])
      }
    }),

    defineLayer({
      id: 'lausanne_birth_rate',
      label: 'Birth Rate',
      unit: 'per 1,000',
      info: 'Birth rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'birth_rate',
        // About 3.5 to 41
        domain: [3, 10, 20, 30, 41],
        scheme: ['#e8f5e9', '#a5d6a7', '#66bb6a', '#388e3c', '#1b5e20']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('birth_rate', 5))
      }
    }),

    defineLayer({
      id: 'lausanne_death_rate',
      label: 'Death Rate',
      unit: 'per 1,000',
      info: 'Death rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'death_rate',
        // About 1.8 to 109
        domain: [1, 25, 50, 75, 109],
        scheme: ['#ffebee', '#ef9a9a', '#e57373', '#c62828', '#b71c1c']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('death_rate', 2))
      }
    }),

    defineLayer({
      id: 'lausanne_inmigration_rate',
      label: 'Internal In-migration',
      unit: 'per 1,000',
      info: 'Internal in-migration rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'inmigration_rate',
        // About 21 to 505
        domain: [20, 125, 250, 375, 505],
        scheme: ['#f3e5f5', '#ce93d8', '#ab47bc', '#7b1fa2', '#4a148c']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('inmigration_rate', 0.5))
      }
    }),

    defineLayer({
      id: 'lausanne_outmigration_rate',
      label: 'Internal Out-migration',
      unit: 'per 1,000',
      info: 'Internal out-migration rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'outmigration_rate',
        // About 41 to 337
        domain: [40, 110, 180, 250, 337],
        scheme: ['#fff3e0', '#ffcc80', '#ffa726', '#f57c00', '#e65100']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('outmigration_rate', 0.5))
      }
    }),

    defineLayer({
      id: 'lausanne_immigration_rate',
      label: 'International Immigration',
      unit: 'per 1,000',
      info: 'International immigration rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'immigration_rate',
        // About 2.4 to 1014
        domain: [2, 250, 500, 750, 1014],
        scheme: ['#e0f2f1', '#80cbc4', '#26a69a', '#00796b', '#004d40']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('immigration_rate', 0.2))
      }
    }),

    defineLayer({
      id: 'lausanne_emigration_rate',
      label: 'International Emigration',
      unit: 'per 1,000',
      info: 'International emigration rate per 1,000 population in Lausanne (2011-2023)',
      source: migrationSource,
      encoding: {
        kind: 'sequential',
        property: 'emigration_rate',
        // About 2.8 to 798
        domain: [2, 200, 400, 600, 798],
        scheme: ['#efebe9', '#bcaaa4', '#8d6e63', '#5d4037', '#3e2723']
      },
      layer: {
        type: 'fill-extrusion',
        'source-layer': 'lausanne_migration',
        paint: extrusion(scaledHeight('emigration_rate', 0.2))
      }
    })
  ]
})

export const sp0MigrationSources: CustomSourceSpecification[] = [migrationSource]
export const sp0MigrationLayers = sp0MigrationGroup.layers
