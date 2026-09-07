import { defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

// The three sources read the same file. They stay separate because their id
// is saved in the investigations and in the shared links.
const buildingsEraSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'buildings_era',
  label: 'Buildings Era - SP6',
  attribution:
    'Registre fédéral des bâtiments et des logements (RegBL), Office Fédéral de la Statistique (OFS); Swiss Map Vector 10, Federal Office of Topography swisstopo',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

const buildingsArchetypeSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'buildings_archetype',
  label: 'Buildings Archetype - SP6',
  attribution:
    'Registre fédéral des bâtiments et des logements (RegBL), Office Fédéral de la Statistique (OFS); Swiss Map Vector 10, Federal Office of Topography swisstopo; own calculations',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

const buildingsOutlineSource: CustomSourceSpecification = {
  type: 'vector',
  id: 'buildings_outline',
  label: 'Buildings Outline - SP6',
  attribution: 'Swiss Map Vector 10, Federal Office of Topography swisstopo',
  url: `pmtiles://${baseUrl}/buildings.pmtiles`,
  minzoom: 10
}

export const sp6MaterialsGroup = defineGroup({
  id: 'sp6_materials',
  label: 'SP6 Materials',
  multiple: false,
  layers: [
    defineLayer({
      id: 'buildings_by_era',
      label: 'Buildings by Era',
      unit: 'era',
      info: 'Buildings in Lausanne colored by construction era',
      source: buildingsEraSource,
      encoding: {
        kind: 'categorical',
        property: 'Era',
        categories: [
          {
            value: 'Before 1919',
            color: '#440154'
          },
          {
            value: '1920 – 1945',
            color: '#481f70'
          },
          {
            value: '1946 – 1960',
            color: '#443983'
          },
          {
            value: '1961 – 1970',
            color: '#3b528b'
          },
          {
            value: '1971 – 1980',
            color: '#31688e'
          },
          {
            value: '1981 – 1985',
            color: '#287c8e'
          },
          {
            value: '1986 – 1990',
            color: '#21918c'
          },
          {
            value: '1991 – 1995',
            color: '#20a486'
          },
          {
            value: '1996 – 2000',
            color: '#35b779'
          },
          {
            value: '2001 – 2005',
            color: '#5ec962'
          },
          {
            value: '2006 - 2010',
            color: '#90d743'
          },
          {
            value: '2011 – 2015',
            color: '#c8e020'
          },
          {
            value: 'After 2015',
            color: '#fde725'
          }
        ],
        defaultColor: '#bdbdbd'
      },
      layer: {
        type: 'fill',
        'source-layer': 'buildings',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'buildings_by_function',
      label: 'Buildings by Function',
      unit: 'function',
      info: 'Buildings in Lausanne colored by their functional use',
      source: buildingsEraSource,
      encoding: {
        kind: 'categorical',
        property: 'Function',
        categories: [
          {
            value: 'Housing',
            color: '#2196F3'
          },
          {
            value: 'Business',
            color: '#4CAF50'
          },
          {
            value: 'Industry',
            color: '#FF9800'
          },
          {
            value: 'Health',
            color: '#F44336'
          },
          {
            value: 'Culture',
            color: '#9C27B0'
          }
        ],
        defaultColor: '#757575'
      },
      layer: {
        type: 'fill',
        'source-layer': 'buildings',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'buildings_by_archetype',
      label: 'Buildings by Archetype',
      unit: 'archetype',
      info: 'Buildings in Lausanne colored by their architectural archetype',
      source: buildingsArchetypeSource,
      encoding: {
        kind: 'categorical',
        property: 'Archetype',
        categories: [
          {
            value: 'Housing before 1919',
            color: '#0d47a1'
          },
          {
            value: 'Housing 1920 - 1945',
            color: '#1565c0'
          },
          {
            value: 'Housing 1946 - 1960',
            color: '#1976d2'
          },
          {
            value: 'Housing 1961 - 1980',
            color: '#1e88e5'
          },
          {
            value: 'Housing 1981 - 1990',
            color: '#42a5f5'
          },
          {
            value: 'Housing 1991 - 2015',
            color: '#90caf9'
          },
          {
            value: 'Housing after 2015',
            color: '#bbdefb'
          },
          {
            value: 'Housing high',
            color: '#673ab7'
          },
          {
            value: 'Bus Large',
            color: '#2e7d32'
          },
          {
            value: 'Bus Small',
            color: '#66bb6a'
          },
          {
            value: 'Ind Large',
            color: '#e65100'
          },
          {
            value: 'Ind Small',
            color: '#ff9800'
          },
          {
            value: 'Heal Large',
            color: '#b71c1c'
          },
          {
            value: 'Heal Small',
            color: '#ef5350'
          },
          {
            value: 'Cult before 1919',
            color: '#6a1b9a'
          },
          {
            value: 'Cult 1920 - 1990',
            color: '#9c27b0'
          },
          {
            value: 'Cult 1991 - 2024',
            color: '#e1bee7'
          }
        ],
        defaultColor: '#bdbdbd'
      },
      layer: {
        type: 'fill',
        'source-layer': 'buildings',
        paint: {
          'fill-opacity': 0.8
        }
      }
    }),

    defineLayer({
      id: 'buildings_outline',
      label: 'Buildings Outline',
      unit: 'outline',
      info: 'Outline of all buildings in Lausanne',
      source: buildingsOutlineSource,
      layer: {
        type: 'line',
        'source-layer': 'buildings',
        layout: {
          visibility: 'visible'
        },
        paint: {
          'line-color': '#000000',
          'line-width': 1,
          'line-opacity': 0.5
        }
      }
    })
  ]
})
