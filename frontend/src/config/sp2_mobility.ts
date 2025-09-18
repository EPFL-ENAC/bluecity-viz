import type { CustomSourceSpecification, MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification } from 'maplibre-gl'

// Shared source configuration for all SP2 mobility layers
const mobilitySource: CustomSourceSpecification = {
  type: 'vector',
  id: 'accessibility_atlas',
  label: 'Urban Accessibility Atlas - SP2',
  attribution: 'Urban Accessibility Atlas (ETH/ESD), based on OpenStreetMap',
  url: `pmtiles://${baseUrl}/accessibility_20250220.pmtiles`,
  minzoom: 5
}

export const sp2MobilitySources: CustomSourceSpecification[] = [mobilitySource]

export const sp2MobilityLayers: MapLayerConfig[] = [
  // Access to food shops (walk)
  {
    id: 'access_food_shops_walk',
    label: 'Access to food shops (walk)',
    unit: 'seconds',
    info: 'Average round-trip travel time from each cell to the nearest 3 short-term goods shops (groceries, bakeries, etc.).',
    source: mobilitySource,
    layer: {
      id: 'access_food_shops_walk-layer',
      type: 'fill',
      source: 'access_food_shops_walk',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral_r colormap (inverse - lower is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_nearest_k_time_return_walk_poi_shop_short']],
          116,
          '#3288bd', // Best (lowest time) - blue
          950,
          '#66c2a5',
          1800,
          '#abdda4',
          2650,
          '#fdae61',
          3525,
          '#d53e4f' // Worst (highest time) - red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to recreational POIs (walk)
  {
    id: 'access_recreation_pois_walk',
    label: 'Access to recreational POIs (walk)',
    unit: 'seconds',
    info: 'Average round-trip travel time from each cell to the nearest 10 indoor recreational POIs (bars, restaurants, theaters).',
    source: mobilitySource,
    layer: {
      id: 'access_recreation_pois_walk-layer',
      type: 'fill',
      source: 'access_recreation_pois_walk',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral_r colormap (inverse - lower is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_nearest_k_time_return_walk_poi_recreation_indoors']],
          152,
          '#3288bd', // Best (lowest time) - blue
          950,
          '#66c2a5',
          1800,
          '#abdda4',
          2650,
          '#fdae61',
          3485,
          '#d53e4f' // Worst (highest time) - red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to nearest school (e-bike)
  {
    id: 'access_school_ebike',
    label: 'Access to nearest school (e-bike)',
    unit: 'seconds',
    info: 'Round-trip travel time from each cell to the nearest school by e-bike.',
    source: mobilitySource,
    layer: {
      id: 'access_school_ebike-layer',
      type: 'fill',
      source: 'access_school_ebike',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral_r colormap (inverse - lower is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_nearest_time_return_bike_e25_poi_education_school']],
          154,
          '#3288bd', // Best (lowest time) - blue
          650,
          '#66c2a5',
          1100,
          '#abdda4',
          1600,
          '#fdae61',
          2081,
          '#d53e4f' // Worst (highest time) - red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to nearest school (car, peak hours)
  {
    id: 'access_school_car_peak',
    label: 'Access to nearest school (car, peak hours)',
    unit: 'seconds',
    info: 'Round-trip travel time from each cell to the nearest school by car during peak hours.',
    source: mobilitySource,
    layer: {
      id: 'access_school_car_peak-layer',
      type: 'fill',
      source: 'access_school_car_peak',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral_r colormap (inverse - lower is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_nearest_time_return_drive_peak_poi_education_school']],
          128,
          '#3288bd', // Best (lowest time) - blue
          425,
          '#66c2a5',
          725,
          '#abdda4',
          1025,
          '#fdae61',
          1325,
          '#d53e4f' // Worst (highest time) - red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to schools: e-bikes vs bikes (ratio)
  {
    id: 'ratio_schools_ebike_bike',
    label: 'Access to schools: e-bikes vs bikes',
    unit: 'ratio',
    info: 'Ratio of travel times (e-bike vs. bike) to the nearest school and back. Lower values indicate e-bike advantage.',
    source: mobilitySource,
    layer: {
      id: 'ratio_schools_ebike_bike-layer',
      type: 'fill',
      source: 'ratio_schools_ebike_bike',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Diverging colormap (blue is better for e-bikes - lower values)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'ar_schools_ebike_bike']],
          0.6,
          '#1a237e', // Strong e-bike advantage - dark blue
          0.7,
          '#7986cb',
          0.8,
          '#c5cae9',
          0.9,
          '#f5f5f5', // Neutral - light gray
          1.0,
          '#ffcdd2' // No advantage - light red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to schools: e-bikes vs cars (ratio)
  {
    id: 'ratio_schools_ebike_car',
    label: 'Access to schools: e-bikes vs cars',
    unit: 'ratio',
    info: 'Ratio of travel times (e-bike vs. car during peak hours) to the nearest school and back. Lower values favor e-bikes.',
    source: mobilitySource,
    layer: {
      id: 'ratio_schools_ebike_car-layer',
      type: 'fill',
      source: 'ratio_schools_ebike_car',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Diverging colormap (blue for e-bike advantage, red for car advantage)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'ar_schools_ebike_car']],
          0.31,
          '#1a237e', // Strong e-bike advantage - dark blue
          0.65,
          '#7986cb',
          1.0,
          '#f5f5f5', // Equal - white
          2.3,
          '#e57373',
          3.62,
          '#b71c1c' // Strong car advantage - dark red
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to jobs (score) by e-bike
  {
    id: 'access_jobs_ebike',
    label: 'Access to jobs (score) by e-bike',
    unit: 'score',
    info: 'Gravity-based cumulative access from each cell to employment opportunities by e-bike (higher is better).',
    source: mobilitySource,
    layer: {
      id: 'access_jobs_ebike-layer',
      type: 'fill',
      source: 'access_jobs_ebike',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral colormap (standard - higher is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_gravity_time_return_bike_e25_employment_total']],
          2336,
          '#d53e4f', // Worst (lowest access) - red
          95000,
          '#fdae61',
          185000,
          '#abdda4',
          280000,
          '#66c2a5',
          371330,
          '#3288bd' // Best (highest access) - blue
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to jobs (score) by transit
  {
    id: 'access_jobs_transit',
    label: 'Access to jobs (score) by transit',
    unit: 'score',
    info: 'Gravity-based cumulative access from each cell to employment opportunities by public transit (higher is better).',
    source: mobilitySource,
    layer: {
      id: 'access_jobs_transit-layer',
      type: 'fill',
      source: 'access_jobs_transit',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral colormap (standard - higher is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_gravity_time_return_transit_employment_total']],
          518,
          '#d53e4f', // Worst (lowest access) - red
          95000,
          '#fdae61',
          190000,
          '#abdda4',
          285000,
          '#66c2a5',
          376478,
          '#3288bd' // Best (highest access) - blue
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to jobs (score) by car
  {
    id: 'access_jobs_car',
    label: 'Access to jobs (score) by car',
    unit: 'score',
    info: 'Gravity-based cumulative access from each cell to employment opportunities by car during peak hours (higher is better).',
    source: mobilitySource,
    layer: {
      id: 'access_jobs_car-layer',
      type: 'fill',
      source: 'access_jobs_car',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Spectral colormap (standard - higher is better)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'access_gravity_time_return_drive_peak_employment_total']],
          28981,
          '#d53e4f', // Worst (lowest access) - red
          130000,
          '#fdae61',
          235000,
          '#abdda4',
          340000,
          '#66c2a5',
          444832,
          '#3288bd' // Best (highest access) - blue
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to jobs: transit vs car (ratio)
  {
    id: 'ratio_jobs_transit_car',
    label: 'Access to jobs: transit vs car',
    unit: 'ratio',
    info: 'Ratio of gravity-based scores for access to jobs (transit vs. driving). Lower values indicate driving advantage.',
    source: mobilitySource,
    layer: {
      id: 'ratio_jobs_transit_car-layer',
      type: 'fill',
      source: 'ratio_jobs_transit_car',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Diverging colormap (blue for transit advantage, red for car advantage)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'ar_jobs_transit_car']],
          0.1,
          '#b71c1c', // Strong car advantage - dark red
          0.3,
          '#e57373',
          0.55,
          '#ffcdd2',
          0.8,
          '#c5cae9',
          1.0,
          '#1a237e' // Transit equal or better - dark blue
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Access to jobs: e-bikes vs cars (ratio)
  {
    id: 'ratio_jobs_ebike_car',
    label: 'Access to jobs: e-bikes vs cars',
    unit: 'ratio',
    info: 'Ratio of gravity-based scores for access to jobs (e-bike vs. driving). Lower values indicate driving advantage.',
    source: mobilitySource,
    layer: {
      id: 'ratio_jobs_ebike_car-layer',
      type: 'fill',
      source: 'ratio_jobs_ebike_car',
      'source-layer': 'accessibility_20250220_wgs84',
      paint: {
        // Diverging colormap (blue for e-bike advantage, red for car advantage)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'ar_jobs_ebike_car']],
          0.1,
          '#b71c1c', // Strong car advantage - dark red
          0.3,
          '#e57373',
          0.55,
          '#ffcdd2',
          0.8,
          '#c5cae9',
          1.07,
          '#1a237e' // E-bike equal or better - dark blue
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  }
]
