import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CategoricalEncoding, CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// Shared source configuration for SP4 waste layers
const wasteRoutesSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'waste_routes',
  label: 'Waste Collection Routes - SP4',
  attribution: 'Ville de Lausanne',
  url: `pmtiles://${baseUrl}/lausanne_waste_routes_2.pmtiles`
}

const wasteCentroidsSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'waste_centroids',
  label: 'Waste Collection Centroids - SP4',
  attribution: 'Ville de Lausanne',
  url: `pmtiles://${baseUrl}/lausanne_waste_centroids.pmtiles`
}

// One colour per waste type, shared by the routes and the collection points.
const WASTE_TYPE_ENCODING: CategoricalEncoding = {
  kind: 'categorical',
  property: 'type',
  categories: [
    {
      value: 'Organic Waste',
      color: '#FF8C00'
    },
    {
      value: 'Household Waste',
      color: '#2E8B57'
    },
    {
      value: 'Paper & Cardboard',
      color: '#8A2BE2'
    },
    {
      value: 'Glass',
      color: '#1E90FF'
    }
  ],
  defaultColor: '#757575'
}

export const sp4WasteGroup = defineGroup({
  id: 'sp4_waste',
  label: 'SP4 Waste',
  multiple: true,
  layers: [
    defineLayer({
      id: 'lausanne_waste_routes',
      label: 'Waste Collection Routes',
      unit: 'count',
      info: 'Waste collection routes in Lausanne with frequency counts (2023)',
      source: wasteRoutesSource,
      encoding: WASTE_TYPE_ENCODING,
      layer: {
        type: 'line',
        'source-layer': 'waste_routes',
        paint: {
          'line-width': [
            'interpolate',
            ['linear'],
            ['get', 'count'],
            0,
            1,
            100,
            2,
            500,
            3,
            1000,
            4,
            5000,
            5,
            10000,
            6
          ],
          'line-opacity': [
            'interpolate',
            ['linear'],
            ['get', 'count'],
            0,
            0.3,
            100,
            0.4,
            500,
            0.5,
            1000,
            0.7,
            5000,
            0.8,
            10000,
            1
          ]
        }
      }
    }),

    defineLayer({
      id: 'lausanne_waste_centroids',
      label: 'Waste Collection Clusters',
      unit: 'cluster',
      info: 'Clusters of waste collection points in Lausanne by waste type (2023)',
      source: wasteCentroidsSource,
      encoding: WASTE_TYPE_ENCODING,
      layer: {
        type: 'circle',
        'source-layer': 'waste_centroids',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 12, 4, 14, 6, 16, 8],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#FFFFFF',
          'circle-opacity': 0.8
        }
      }
    })
  ]
})
