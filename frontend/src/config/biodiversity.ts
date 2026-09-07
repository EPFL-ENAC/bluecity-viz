import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'

// Relative in dev too: vite proxies /api to this checkout's own backend, whose
// port changes per git worktree (see vite.config.ts and docs/worktree-env/).
const API_BASE_URL = '/api/v1/routes'

const HABITAT_MAX = 100

const habitatSource: CustomSourceSpecification = {
  type: 'geojson',
  id: 'habitat_density',
  label: 'Habitat Density - Biodiversity',
  data: `${API_BASE_URL}/habitat-geojson`
}

// No encoding: the ramp reads the property without to-number, keep the
// expression as it is so the rendering does not change.
export const biodiversityGroup = defineGroup({
  id: 'biodiversity',
  label: 'Biodiversity',
  multiple: false,
  layers: [
    defineLayer({
      id: 'habitat_density',
      label: 'Habitat Density (10m buffer)',
      unit: 'm²/m',
      info: 'Total habitat area within a 10m buffer around each road, normalised by road length (m²/m). Data: Swiss Lebensraumkarte.',
      source: habitatSource,
      layer: {
        type: 'line',
        filter: ['>', ['get', 'habitat_density_m2_per_m'], 0],
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'habitat_density_m2_per_m'],
            1,
            '#d5f0d0',
            5,
            '#8ed68a',
            20,
            '#3db038',
            50,
            '#1a7d17',
            100,
            '#0b4a09'
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
      }
    })
  ]
})

export const biodiversitySources: CustomSourceSpecification[] = [habitatSource]
export const biodiversityLayers = biodiversityGroup.layers
