import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

// Shared source configuration for SP6 materials layers
const buildingsSource: VectorSourceSpecification = {
  type: 'vector',
  attribution:
    'Registre fédéral des bâtiments et des logements (RegBL), Office Fédéral de la Statistique (OFS); Swiss Map Vector 10, Federal Office of Topography swisstopo',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

const buildingsArchetypeSource: VectorSourceSpecification = {
  type: 'vector',
  attribution:
    'Registre fédéral des bâtiments et des logements (RegBL), Office Fédéral de la Statistique (OFS); Swiss Map Vector 10, Federal Office of Topography swisstopo; own calculations',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

const buildingsOutlineSource: VectorSourceSpecification = {
  type: 'vector',
  attribution: 'Swiss Map Vector 10, Federal Office of Topography swisstopo',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

export const sp6MaterialsSources: VectorSourceSpecification[] = [
  buildingsSource,
  buildingsArchetypeSource,
  buildingsOutlineSource
]

export const sp6MaterialsLayers: MapLayerConfig[] = [
  // Buildings colored by Era
  {
    id: 'buildings_by_era',
    label: 'Buildings by Era',
    unit: 'era',
    info: 'Buildings in Lausanne colored by construction era',
    source: buildingsSource,
    layer: {
      id: 'buildings_by_era-layer',
      type: 'fill',
      source: 'buildings_by_era',
      'source-layer': 'buildings',
      paint: {
        // Fill color based on Era attribute
        'fill-color': [
          'match',
          ['get', 'Era'],
          'Before 1919',
          '#440154',
          '1920 – 1945',
          '#481f70',
          '1946 – 1960',
          '#443983',
          '1961 – 1970',
          '#3b528b',
          '1971 – 1980',
          '#31688e',
          '1981 – 1985',
          '#287c8e',
          '1986 – 1990',
          '#21918c',
          '1991 – 1995',
          '#20a486',
          '1996 – 2000',
          '#35b779',
          '2001 – 2005',
          '#5ec962',
          '2006 - 2010',
          '#90d743',
          '2011 – 2015',
          '#c8e020',
          'After 2015',
          '#fde725',
          '#bdbdbd' // Default color for unknown/null values
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Buildings colored by Function
  {
    id: 'buildings_by_function',
    label: 'Buildings by Function',
    unit: 'function',
    info: 'Buildings in Lausanne colored by their functional use',
    source: buildingsSource,
    layer: {
      id: 'buildings_by_function-layer',
      type: 'fill',
      source: 'buildings_by_function',
      'source-layer': 'buildings',
      paint: {
        // Fill color based on Function attribute
        'fill-color': [
          'match',
          ['get', 'Function'],
          'Housing',
          '#2196F3', // Blue
          'Business',
          '#4CAF50', // Green
          'Industry',
          '#FF9800', // Orange
          'Health',
          '#F44336', // Red
          'Culture',
          '#9C27B0', // Purple
          '#757575' // Default color for unknown/null values
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Buildings colored by Archetype
  {
    id: 'buildings_by_archetype',
    label: 'Buildings by Archetype',
    unit: 'archetype',
    info: 'Buildings in Lausanne colored by their architectural archetype',
    source: buildingsArchetypeSource,
    layer: {
      id: 'buildings_by_archetype-layer',
      type: 'fill',
      source: 'buildings_by_archetype',
      'source-layer': 'buildings',
      paint: {
        // Fill color based on Archetype attribute
        'fill-color': [
          'match',
          ['get', 'Archetype'],
          // Housing archetypes - blues to purples
          'Housing before 1919',
          '#0d47a1',
          'Housing 1920 - 1945',
          '#1565c0',
          'Housing 1946 - 1960',
          '#1976d2',
          'Housing 1961 - 1980',
          '#1e88e5',
          'Housing 1981 - 1990',
          '#42a5f5',
          'Housing 1991 - 2015',
          '#90caf9',
          'Housing after 2015',
          '#bbdefb',
          'Housing high',
          '#673ab7',

          // Business archetypes - greens
          'Bus Large',
          '#2e7d32',
          'Bus Small',
          '#66bb6a',

          // Industry archetypes - oranges
          'Ind Large',
          '#e65100',
          'Ind Small',
          '#ff9800',

          // Health archetypes - reds
          'Heal Large',
          '#b71c1c',
          'Heal Small',
          '#ef5350',

          // Culture archetypes - purples/pinks
          'Cult before 1919',
          '#6a1b9a',
          'Cult 1920 - 1990',
          '#9c27b0',
          'Cult 1991 - 2024',
          '#e1bee7',

          '#bdbdbd' // Default color for unknown/null values
        ],
        'fill-opacity': 0.8
      }
    } as LayerSpecification
  },

  // Add a buildings outline layer to show building boundaries clearly
  {
    id: 'buildings_outline',
    label: 'Buildings Outline',
    unit: 'outline',
    info: 'Outline of all buildings in Lausanne',
    source: buildingsOutlineSource,
    layer: {
      id: 'buildings_outline-layer',
      type: 'line',
      source: 'buildings_outline',
      'source-layer': 'buildings',
      paint: {
        'line-color': '#000000',
        'line-width': 1,
        'line-opacity': 0.5
      },
      layout: {
        visibility: 'visible' // This can be toggled off by default if desired
      }
    } as LayerSpecification
  }
]
