import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// Shared source configuration for all SP2 mobility layers
const mobilitySource: CustomSourceSpecification = {
  type: 'vector',
  id: 'accessibility_atlas',
  label: 'Urban Accessibility Atlas - SP2',
  attribution: 'Urban Accessibility Atlas (ETH/ESD), based on OpenStreetMap',
  url: `pmtiles://${baseUrl}/accessibility_20250220.pmtiles`,
  minzoom: 5
}

// Spectral, blue is the best value, red the worst. Reversed when a high
// value is the good one.
const SPECTRAL = ['#3288bd', '#66c2a5', '#abdda4', '#fdae61', '#d53e4f']
const SPECTRAL_R = ['#d53e4f', '#fdae61', '#abdda4', '#66c2a5', '#3288bd']
// Access ratio between two modes, red means one mode is much slower.
const RATIO_SCHEME = ['#b71c1c', '#e57373', '#ffcdd2', '#c5cae9', '#1a237e']

export const sp2MobilityGroup = defineGroup({
  id: 'sp2_mobility',
  label: 'SP2 Mobility',
  multiple: false,
  layers: [
    defineLayer({
      id: 'access_food_shops_walk',
      label: 'Access to food shops (walk)',
      unit: 'seconds',
      info: 'Average round-trip travel time from each cell to the nearest 3 short-term goods shops (groceries, bakeries, etc.).',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_nearest_k_time_return_walk_poi_shop_short',
        domain: [116, 950, 1800, 2650, 3525],
        scheme: SPECTRAL
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_recreation_pois_walk',
      label: 'Access to recreational POIs (walk)',
      unit: 'seconds',
      info: 'Average round-trip travel time from each cell to the nearest 10 indoor recreational POIs (bars, restaurants, theaters).',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_nearest_k_time_return_walk_poi_recreation_indoors',
        domain: [152, 950, 1800, 2650, 3485],
        scheme: SPECTRAL
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_school_ebike',
      label: 'Access to nearest school (e-bike)',
      unit: 'seconds',
      info: 'Round-trip travel time from each cell to the nearest school by e-bike.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_nearest_time_return_bike_e25_poi_education_school',
        domain: [154, 650, 1100, 1600, 2081],
        scheme: SPECTRAL
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_school_car_peak',
      label: 'Access to nearest school (car, peak hours)',
      unit: 'seconds',
      info: 'Round-trip travel time from each cell to the nearest school by car during peak hours.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_nearest_time_return_drive_peak_poi_education_school',
        domain: [128, 425, 725, 1025, 1325],
        scheme: SPECTRAL
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'ratio_schools_ebike_bike',
      label: 'Access to schools: e-bikes vs bikes',
      unit: 'ratio',
      info: 'Ratio of travel times (e-bike vs. bike) to the nearest school and back. Lower values indicate e-bike advantage.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'ar_schools_ebike_bike',
        domain: [0.6, 0.7, 0.8, 0.9, 1],
        scheme: ['#1a237e', '#7986cb', '#c5cae9', '#f5f5f5', '#ffcdd2']
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'ratio_schools_ebike_car',
      label: 'Access to schools: e-bikes vs cars',
      unit: 'ratio',
      info: 'Ratio of travel times (e-bike vs. car during peak hours) to the nearest school and back. Lower values favor e-bikes.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'ar_schools_ebike_car',
        domain: [0.31, 0.65, 1, 2.3, 3.62],
        scheme: ['#1a237e', '#7986cb', '#f5f5f5', '#e57373', '#b71c1c']
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_jobs_ebike',
      label: 'Access to jobs (score) by e-bike',
      unit: 'score',
      info: 'Gravity-based cumulative access from each cell to employment opportunities by e-bike (higher is better).',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_gravity_time_return_bike_e25_employment_total',
        domain: [2336, 95000, 185000, 280000, 371330],
        scheme: SPECTRAL_R
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_jobs_transit',
      label: 'Access to jobs (score) by transit',
      unit: 'score',
      info: 'Gravity-based cumulative access from each cell to employment opportunities by public transit (higher is better).',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_gravity_time_return_transit_employment_total',
        domain: [518, 95000, 190000, 285000, 376478],
        scheme: SPECTRAL_R
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'access_jobs_car',
      label: 'Access to jobs (score) by car',
      unit: 'score',
      info: 'Gravity-based cumulative access from each cell to employment opportunities by car during peak hours (higher is better).',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'access_gravity_time_return_drive_peak_employment_total',
        domain: [28981, 130000, 235000, 340000, 444832],
        scheme: SPECTRAL_R
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'ratio_jobs_transit_car',
      label: 'Access to jobs: transit vs car',
      unit: 'ratio',
      info: 'Ratio of gravity-based scores for access to jobs (transit vs. driving). Lower values indicate driving advantage.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'ar_jobs_transit_car',
        domain: [0.1, 0.3, 0.55, 0.8, 1],
        scheme: RATIO_SCHEME
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'ratio_jobs_ebike_car',
      label: 'Access to jobs: e-bikes vs cars',
      unit: 'ratio',
      info: 'Ratio of gravity-based scores for access to jobs (e-bike vs. driving). Lower values indicate driving advantage.',
      source: mobilitySource,
      encoding: {
        kind: 'sequential',
        property: 'ar_jobs_ebike_car',
        domain: [0.1, 0.3, 0.55, 0.8, 1.07],
        scheme: RATIO_SCHEME
      },
      layer: {
        type: 'fill',
        'source-layer': 'accessibility_20250220_wgs84',
        paint: {
          'fill-opacity': 0.8
        }
      }
    })
  ]
})
