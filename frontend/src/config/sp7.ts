import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

const vehicleTracksSource: VectorSourceSpecification = {
  type: 'vector',
  url: `pmtiles://${baseUrl}/vehicle_tracks.pmtiles`,
  minzoom: 8
}

export const sp7VehicleSources: VectorSourceSpecification[] = [vehicleTracksSource]

export const sp7VehicleLayers: MapLayerConfig[] = [
  {
    id: 'vehicle_tracks',
    label: 'Vehicle Tracking Routes',
    unit: 'tracks',
    info: 'Vehicle tracking data showing routes taken by vehicles on different dates',
    source: vehicleTracksSource,
    layer: {
      id: 'vehicle_tracks-layer',
      type: 'line',
      source: 'vehicle_tracks',
      'source-layer': 'vehicle_tracks',
      paint: {
        // Generate a color based on the vehicle ID for consistent coloring per vehicle
        'line-color': [
          'interpolate-hcl',
          ['linear'],
          // Hash the vehicle_id string to a number, then normalize to 0-1
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
    } as LayerSpecification
  },
  {
    id: 'vehicle_tracks_by_date',
    label: 'Vehicle Tracks by Date',
    unit: 'date',
    info: 'Vehicle tracking routes colored by date of travel',
    source: vehicleTracksSource,
    layer: {
      id: 'vehicle_tracks_by_date-layer',
      type: 'line',
      source: 'vehicle_tracks_by_date',
      'source-layer': 'vehicle_tracks',
      paint: {
        // Color based on date using a sequential color scheme
        // Assumes dates are in YYYY-MM-DD format
        'line-color': [
          'interpolate',
          ['linear'],
          // Convert date string to timestamp for color mapping
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
    } as LayerSpecification
  }
]
