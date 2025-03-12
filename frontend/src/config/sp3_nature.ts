import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export const sp3NatureLayers: MapLayerConfig[] = [
  // Temperature Layer
  {
    id: 'lausanne_temperature',
    label: 'Temperature (Annual Average)',
    unit: '°C',
    info: 'Annual average temperature across Lausanne using 200m x 200m grid cells.',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_temperature_yearly.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
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
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_aqi_yearly.pmtiles`,
      minzoom: 5
    } as VectorSourceSpecification,
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
  }
]
