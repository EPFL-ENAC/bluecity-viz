import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

const vehicleTracksSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'vehicle_tracks',
  label: 'Vehicle Tracking - SP7',
  url: `pmtiles://${baseUrl}/vehicle_tracks.pmtiles`,
  minzoom: 8
}

// No encoding here: the colour comes from a hash of the vehicle id, not from
// the value of one property, so it stays a hand written expression.
export const sp7VehicleGroup = defineGroup({
  id: 'sp7',
  label: 'SP7 Goods',
  multiple: false,
  layers: [
    defineLayer({
      id: 'vehicle_tracks',
      label: 'Vehicle Tracking Routes',
      unit: 'tracks',
      info: 'Vehicle tracking data showing routes taken by vehicles on different dates',
      source: vehicleTracksSource,
      layer: {
        type: 'line',
        'source-layer': 'vehicle_tracks',
        paint: {
          'line-color': [
            'interpolate-hcl',
            ['linear'],
            [
              '%',
              [
                '+',
                ['length', ['get', 'vehicle_id']],
                [
                  '+',
                  ['to-number', ['slice', ['get', 'vehicle_id'], 0, 2], 16],
                  ['to-number', ['slice', ['get', 'vehicle_id'], 2, 4], 16]
                ]
              ],
              360
            ],
            0,
            '#e31a1c',
            60,
            '#ff7f00',
            120,
            '#ffff33',
            180,
            '#33a02c',
            240,
            '#1f78b4',
            300,
            '#6a3d9a',
            359,
            '#e31a1c'
          ],
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 12, 2, 16, 4],
          'line-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'vehicle_tracks_by_date',
      label: 'Vehicle Tracks by Date',
      unit: 'date',
      info: 'Vehicle tracking routes colored by date of travel',
      source: vehicleTracksSource,
      layer: {
        type: 'line',
        'source-layer': 'vehicle_tracks',
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['to-number', ['to-number', ['slice', ['get', 'date'], 8, 10]]],
            1,
            '#440154',
            10,
            '#3b528b',
            20,
            '#21908d',
            30,
            '#5dc963',
            31,
            '#fde725'
          ],
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 12, 2, 16, 4],
          'line-opacity': 0.8
        }
      }
    })
  ]
})

export const sp7VehicleSources: CustomSourceSpecification[] = [vehicleTracksSource]
export const sp7VehicleLayers = sp7VehicleGroup.layers
