import type {
  ImageSourceSpecification,
  LayerSpecification,
  SourceSpecification,
  VectorSourceSpecification
} from 'maplibre-gl'

export interface MapLayerConfig {
  id: string
  label: string
  unit: string
  info: string
  source: SourceSpecification
  layer: LayerSpecification
}

const baseUrlOptions = {
  dev: '/geodata',
  prod: 'https://enacit4r-cdn.epfl.ch/urbes-viz'
}

const baseUrl = import.meta.env.DEV ? baseUrlOptions.dev : baseUrlOptions.prod

export const mapConfig = {
  // Map layers with their associated sources
  baseUrl: baseUrlOptions,
  layers: [
    {
      id: 'buildings',
      label: 'Buildings',
      unit: 'year',
      info: 'Source: Swiss Federal Office of Topography',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/buildings_swiss.pmtiles`,
        minzoom: 5 // Minimum zoom level to display buildings
      } as VectorSourceSpecification,
      layer: {
        id: 'buildings-layer',
        type: 'fill-extrusion',
        source: 'buildings',
        'source-layer': 'buildings_swiss',
        paint: {
          'fill-extrusion-height': [
            'interpolate',
            ['linear'],
            ['to-number', ['get', 'OBJORIG_YE']],
            1950,
            10,
            2000,
            50,
            2020,
            100
          ],
          'fill-extrusion-color': [
            'interpolate',
            ['linear'],
            ['to-number', ['get', 'OBJORIG_YE']],
            1950,
            '#FF0000',
            2000,
            '#FFFF00',
            2020,
            '#00FF00'
          ],
          'fill-extrusion-base': [
            'case',
            ['>=', ['get', 'zoom'], 16],
            ['get', 'render_min_height'],
            0
          ]
        }
      } as LayerSpecification
    },
    {
      id: 'wrf',
      label: 'Urban climate',
      unit: '',
      info: 'Source: Aldo Brandi, URBES',
      source: {
        type: 'image',
        url: '',
        coordinates: [
          [5.13211, 47.94587],
          [11.12701, 47.94587],
          [11.12701, 45.42068],
          [5.13211, 45.42068]
        ]
      } as ImageSourceSpecification,
      volatile: true,
      layer: {
        id: 'wrf-layer',
        type: 'raster',
        source: 'wrf',
        paint: {
          'raster-opacity': 0.5
        }
      } as LayerSpecification
    },
    {
      id: 'areas',
      unit: '',
      label: 'Cantonal boundaries',
      info: 'Source: Swiss Federal Office of Topography',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/hoheitsgebiet.pmtiles`
      } as VectorSourceSpecification,
      layer: {
        id: 'areas-layer',
        type: 'fill',
        source: 'areas',
        'source-layer': 'swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET_4326',
        paint: {
          'fill-color': '#ffffff',
          'fill-opacity': 0.8,
          'fill-outline-color': '#000000'
        }
      } as LayerSpecification
    },
    {
      id: 'roads',
      label: 'Roads',
      unit: 'year',
      info: 'Source: Swiss Federal Office of Topography',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/roads_swiss.pmtiles`,
        minzoom: 5
      } as VectorSourceSpecification,
      layer: {
        id: 'roads-layer',
        type: 'line',
        source: 'roads',
        'source-layer': 'roads_swiss',
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['to-number', ['get', 'OBJORIG_YE']],
            0,
            '#00FFFF',
            1950,
            '#FF0000',
            2000,
            '#FFFF00',
            2020,
            '#00FF00'
          ],
          'line-opacity': 0.7
        }
      } as LayerSpecification
    },
    {
      id: 'roads_swiss_statistics',
      label: 'Traffic 2017',
      unit: 'vehicles/day',
      info: 'Source: Swiss Federal Office for Spatial Development',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/roads_swiss_statistics.pmtiles`
      } as VectorSourceSpecification,
      layer: {
        id: 'roads_swiss_statistics-layer',
        type: 'line',
        source: 'roads_swiss_statistics',
        'source-layer': 'roads_swiss_statistics',
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'DWV_PW'],
            0,
            '#b0e0e6',
            5000,
            '#4682b4',
            10000,
            '#ff4500',
            20000,
            '#8b0000'
          ],
          'line-width': [
            'interpolate',
            ['linear'],
            ['get', 'DTV_PW'],
            0,
            0.5,
            5000,
            2,
            10000,
            4,
            20000,
            6
          ],
          'line-opacity': 0.8
        }
      } as LayerSpecification
    },
    {
      id: 'roads_swiss_statistics_projection',
      label: 'Traffic 2050',
      unit: 'vehicles/day',
      info: 'Source: Swiss Federal Office for Spatial Development',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/roads_swiss_statistics_projection.pmtiles`
      } as VectorSourceSpecification,
      layer: {
        id: 'roads_swiss_statistics_projection-layer',
        type: 'line',
        source: 'roads_swiss_statistics_projection',
        'source-layer': 'roads_swiss_statistics_projection',
        paint: {
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'DWV_PW'],
            0,
            '#b0e0e6',
            5000,
            '#4682b4',
            10000,
            '#ff4500',
            20000,
            '#8b0000'
          ],
          'line-width': [
            'interpolate',
            ['linear'],
            ['get', 'DTV_PW'],
            0,
            0.5,
            5000,
            2,
            10000,
            4,
            20000,
            6
          ],
          'line-opacity': 0.8
        }
      } as LayerSpecification
    },
    {
      id: 'gws_data',
      label: 'Building numbers',
      unit: '/100m²',
      info: 'Source: Swiss Federal Statistical Office',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/gws_grid.pmtiles`
      } as VectorSourceSpecification,
      layer: {
        id: 'gws_data-layer',
        type: 'fill',
        source: 'gws_data',
        'source-layer': 'gws_grid_wgs84',
        paint: {
          'fill-opacity': 0.5,
          'fill-color': [
            'interpolate',
            ['linear'],
            ['get', 'GTOT'],
            0,
            '#e0f7fa',
            10,
            '#4db6ac',
            25,
            '#00796b',
            50,
            '#004d40'
          ]
        }
      } as LayerSpecification
    },
    {
      id: 'statpop_data',
      label: 'Population',
      unit: '/100m²',
      info: 'Source: Swiss Federal Statistical Office',
      source: {
        type: 'vector',
        url: `pmtiles://${baseUrl}/statpop_grid.pmtiles`
      } as VectorSourceSpecification,
      layer: {
        id: 'statpop_data-layer',
        type: 'fill-extrusion',
        source: 'statpop_data',
        'source-layer': 'statpop_grid_wgs84',
        paint: {
          'fill-extrusion-height': ['get', 'B22BTOT'],
          'fill-extrusion-opacity': 0.8,
          'fill-extrusion-color': [
            'interpolate',
            ['linear'],
            ['get', 'B22BTOT'],
            0,
            '#e0f7fa',
            30,
            '#4db6ac',
            60,
            '#00796b',
            100,
            '#004d40'
          ]
        }
      } as LayerSpecification
    }
  ] as MapLayerConfig[]
}
