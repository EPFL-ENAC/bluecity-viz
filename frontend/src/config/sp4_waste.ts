import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export const sp4WasteLayers: MapLayerConfig[] = [
  {
    id: 'lausanne_waste_routes',
    label: 'Waste Collection Routes',
    unit: 'count',
    info: 'Waste collection routes in Lausanne with frequency counts (2023)',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/lausanne_waste_routes.pmtiles`,
      minzoom: 10
    } as VectorSourceSpecification,
    layer: {
      id: 'lausanne_waste_routes-layer',
      type: 'line',
      source: 'lausanne_waste_routes',
      'source-layer': 'waste_routes',
      paint: {
        // Line color based on waste collection type
        'line-color': [
          'match',
          ['get', 'type'],
          'Organic Waste',
          '#FF8C00', // Orange - Organic waste (Déchets verts)
          'Household Waste',
          '#2E8B57', // Green - Household waste (Déchets incinérables)
          'Paper & Cardboard',
          '#8A2BE2', // Purple - Paper & Cardboard (Papier/Carton)
          'Glass',
          '#1E90FF', // Blue - Glass (Verre)
          '#757575' // Gray - default for any other type
        ],
        // Line width based on count (frequency)
        'line-width': [
          'interpolate',
          ['linear'],
          ['get', 'count'],
          0,
          1, // Minimum width
          100,
          2,
          500,
          3,
          1000,
          4,
          5000,
          5,
          10000,
          6 // Maximum width
        ],
        'line-opacity': [
          'interpolate',
          ['linear'],
          ['get', 'count'],
          0,
          0.3, // Minimum width
          100,
          0.4,
          500,
          0.5,
          1000,
          0.7,
          5000,
          0.8,
          10000,
          1 // Maximum width
        ]
      }
    } as LayerSpecification
  }
]
