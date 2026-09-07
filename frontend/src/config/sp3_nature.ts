import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// Shared source configuration for SP3 nature layers
const temperatureYearlySource: CustomSourceSpecification = {
  type: 'vector',
  id: 'lausanne_temperature',
  label: 'Temperature Data - SP3',
  attribution: 'Sparrow Analytics SA',
  url: `pmtiles://${baseUrl}/lausanne_temperature_yearly.pmtiles`,
  minzoom: 5
}

const aqiYearlySource: CustomSourceSpecification = {
  type: 'vector',
  id: 'lausanne_aqi',
  label: 'Air Quality Index - SP3',
  attribution: 'Sparrow Analytics SA',
  url: `pmtiles://${baseUrl}/lausanne_aqi_yearly.pmtiles`,
  minzoom: 5
}

const speciesObservationSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'lausanne_species',
  label: 'Species Observations - SP3',
  attribution: 'info fauna, National Data and Information Centre on Wildlife in Switzerland',
  url: `pmtiles://${baseUrl}/lausanne_species.pmtiles`,
  minzoom: 5
}

export const sp3NatureGroup = defineGroup({
  id: 'sp3_nature',
  label: 'SP3 Nature',
  multiple: false,
  layers: [
    defineLayer({
      id: 'lausanne_temperature',
      label: 'Temperature (Annual Average)',
      unit: '°C',
      info: 'Annual average temperature across Lausanne using 200m x 200m grid cells.',
      source: temperatureYearlySource,
      // Blue at 0 degrees, cyan, yellow, red at 30
      encoding: {
        kind: 'sequential',
        property: 'value',
        domain: [0, 5, 10, 15, 20, 25, 30],
        scheme: ['#0000ff', '#0066ff', '#00ccff', '#00ffcc', '#ffff00', '#ff9900', '#ff0000']
      },
      layer: {
        type: 'fill',
        'source-layer': 'lausanne_temperature_yearly',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'lausanne_aqi',
      label: 'Air Quality Index (Annual)',
      unit: 'AQI',
      info: 'Annual average air quality index across Lausanne using 200m x 200m grid cells.',
      source: aqiYearlySource,
      // Standard AQI bands, the stops are doubled so each band is flat:
      // 0-50 good, 51-100 moderate, 101-150 unhealthy for sensitive groups,
      // 151-200 unhealthy, 201-300 very unhealthy.
      encoding: {
        kind: 'sequential',
        property: 'value',
        domain: [0, 50, 51, 100, 101, 150, 151, 200, 201, 300],
        scheme: [
          '#00e400',
          '#00e400',
          '#ffff00',
          '#ffff00',
          '#ff7e00',
          '#ff7e00',
          '#ff0000',
          '#ff0000',
          '#99004c',
          '#99004c'
        ]
      },
      layer: {
        type: 'fill',
        'source-layer': 'lausanne_aqi_yearly',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'species_observations_by_group',
      label: 'Species Observations (by Group)',
      unit: 'group',
      info: 'Animal species observations in Lausanne area, colored by taxonomic group.',
      source: speciesObservationSource,
      encoding: {
        kind: 'categorical',
        property: 'Group',
        categories: [
          {
            value: 'Fish',
            color: '#3ca0d3'
          },
          {
            value: 'Amphibian',
            color: '#9c27b0'
          },
          {
            value: 'Mammal',
            color: '#d16b30'
          },
          {
            value: 'Reptile',
            color: '#2e7d32'
          },
          {
            value: 'Bird',
            color: '#e91e63'
          }
        ],
        defaultColor: '#aaaaaa'
      },
      layer: {
        type: 'circle',
        'source-layer': 'species_observations',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 14, 6, 16, 8],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'species_observations_by_redlist',
      label: 'Species Observations (by Red List Status)',
      unit: 'status',
      info: 'Animal species observations in Lausanne area, colored by conservation status (Red List category).',
      source: speciesObservationSource,
      encoding: {
        kind: 'categorical',
        property: 'Red List',
        categories: [
          {
            value: 'Critically Endangered',
            color: '#bd0026'
          },
          {
            value: 'Endangered',
            color: '#f03b20'
          },
          {
            value: 'Vulnerable',
            color: '#fd8d3c'
          },
          {
            value: 'Near Threatened',
            color: '#fecc5c'
          },
          {
            value: 'Least Concern',
            color: '#ffffb2'
          },
          {
            value: 'Data Deficient',
            color: '#999999'
          },
          {
            value: 'Not Evaluated',
            color: '#cccccc'
          }
        ],
        defaultColor: '#cccccc'
      },
      layer: {
        type: 'circle',
        'source-layer': 'species_observations',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 14, 6, 16, 8],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.8
        }
      }
    })
  ]
})
