import type { CustomSourceSpecification, MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification } from 'maplibre-gl'

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

export const sp3NatureSources: CustomSourceSpecification[] = [
  temperatureYearlySource,
  aqiYearlySource,
  speciesObservationSource
]

export const sp3NatureLayers: MapLayerConfig[] = [
  // Temperature Layer
  {
    id: 'lausanne_temperature',
    label: 'Temperature (Annual Average)',
    unit: '°C',
    info: 'Annual average temperature across Lausanne using 200m x 200m grid cells.',
    source: temperatureYearlySource,
    layer: {
      id: 'lausanne_temperature-layer',
      type: 'fill',
      source: 'lausanne_temperature',
      'source-layer': 'lausanne_temperature_yearly',
      paint: {
        // Custom temperature colormap (blue → cyan → yellow → red)
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'value']],
          0,
          '#0000ff', // Blue (0°C)
          5,
          '#0066ff', // Light Blue (5°C)
          10,
          '#00ccff', // Cyan (10°C)
          15,
          '#00ffcc', // Light Cyan (15°C)
          20,
          '#ffff00', // Yellow (20°C)
          25,
          '#ff9900', // Orange (25°C)
          30,
          '#ff0000' // Red (30°C)
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Air Quality Index (AQI) Layer
  {
    id: 'lausanne_aqi',
    label: 'Air Quality Index (Annual)',
    unit: 'AQI',
    info: 'Annual average air quality index across Lausanne using 200m x 200m grid cells.',
    source: aqiYearlySource,
    layer: {
      id: 'lausanne_aqi-layer',
      type: 'fill',
      source: 'lausanne_aqi',
      'source-layer': 'lausanne_aqi_yearly',
      paint: {
        // AQI standard color scale
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['get', 'value']],
          0,
          '#00e400', // Good (0-50) - Green
          50,
          '#00e400', // Good (50) - Green
          51,
          '#ffff00', // Moderate (51-100) - Yellow
          100,
          '#ffff00', // Moderate (100) - Yellow
          101,
          '#ff7e00', // Unhealthy for Sensitive Groups (101-150) - Orange
          150,
          '#ff7e00', // Unhealthy for Sensitive Groups (150) - Orange
          151,
          '#ff0000', // Unhealthy (151-200) - Red
          200,
          '#ff0000', // Unhealthy (200) - Red
          201,
          '#99004c', // Very Unhealthy (201-300) - Purple
          300,
          '#99004c' // Very Unhealthy (300) - Purple
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Species Observations by Group
  {
    id: 'species_observations_by_group',
    label: 'Species Observations (by Group)',
    unit: 'group',
    info: 'Animal species observations in Lausanne area, colored by taxonomic group.',
    source: speciesObservationSource,
    layer: {
      id: 'species_observations_by_group-layer',
      type: 'circle',
      source: 'species_observations_by_group',
      'source-layer': 'species_observations',
      // filter: [
      //   'all',
      //   ['has', 'Group'],
      //   ['>=', ['to-number', ['get', 'Year']], 2023],
      //   ['<=', ['to-number', ['get', 'Year']], 2024]
      // ] as FilterSpecification,
      paint: {
        // Color by species group
        'circle-color': [
          'match',
          ['get', 'Group'],
          'Fish',
          '#3ca0d3', // Blue for fish (aquatic)
          'Amphibian',
          '#9c27b0', // Purple for amphibians
          'Mammal',
          '#d16b30', // Orange/brown for mammals
          'Reptile',
          '#2e7d32', // Dark green for reptiles
          'Bird',
          '#e91e63', // Pink for birds
          '#aaaaaa' // Default grey
        ],
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          10,
          3, // Small at low zoom
          14,
          6, // Medium at middle zoom
          16,
          8 // Larger at high zoom
        ],
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Species Observations by Red List Category (Conservation Status)
  {
    id: 'species_observations_by_redlist',
    label: 'Species Observations (by Red List Status)',
    unit: 'status',
    info: 'Animal species observations in Lausanne area, colored by conservation status (Red List category).',
    source: speciesObservationSource,
    layer: {
      id: 'species_observations_by_redlist-layer',
      type: 'circle',
      source: 'species_observations_by_redlist',
      'source-layer': 'species_observations',
      // filter: [
      //   'all',
      //   ['has', 'Red List'],
      //   ['>=', ['to-number', ['get', 'Year']], 2023],
      //   ['<=', ['to-number', ['get', 'Year']], 2024]
      // ],
      paint: {
        // Color by Red List category (darker = more threatened)
        'circle-color': [
          'match',
          ['get', 'Red List'],
          'Critically Endangered',
          '#bd0026', // Darkest red
          'Endangered',
          '#f03b20', // Dark red
          'Vulnerable',
          '#fd8d3c', // Orange
          'Near Threatened',
          '#fecc5c', // Yellow-orange
          'Least Concern',
          '#ffffb2', // Light yellow
          'Data Deficient',
          '#999999', // Grey
          'Not Evaluated',
          '#cccccc', // Light Grey
          '#cccccc' // Default - Light Grey
        ],
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          10,
          3, // Small at low zoom
          14,
          6, // Medium at middle zoom
          16,
          8 // Larger at high zoom
        ],
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.8
      }
    } as LayerSpecification
  }
]
