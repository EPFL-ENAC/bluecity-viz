import type { MapLayerConfig } from '@/config/layerTypes'
import { baseUrl } from '@/config/layerTypes'

import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl'

export const sp6MaterialsLayers: MapLayerConfig[] = [
  // Buildings colored by building category
  {
    id: 'buildings_by_category',
    label: 'Buildings by Category',
    unit: 'category',
    info: 'Building locations in Vaud colored by their category',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/buildings.pmtiles`,
      minzoom: 12
    } as VectorSourceSpecification,
    layer: {
      id: 'buildings_by_category-layer',
      type: 'circle',
      source: 'buildings_by_category',
      'source-layer': 'buildings',
      paint: {
        // Circle color based on building category
        'circle-color': [
          'match',
          ['get', 'buildingCategory'],
          1010,
          '#9C27B0', // Habitation provisoire (Provisional housing)
          1020,
          '#1E88E5', // Bâtiment exclusif à usage d'habitation (Exclusively residential)
          1030,
          '#43A047', // Autre bâtiment d'habitation (Other residential building)
          1040,
          '#F4511E', // Bâtiment partiellement à usage d'habitation (Partially residential)
          1060,
          '#8E24AA', // Bâtiment sans usage d'habitation (Non-residential)
          1080,
          '#FFB300', // Construction particulière (Special construction)
          '#757575' // Other/unknown categories
        ],
        // Circle size based on zoom level
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 1, 14, 3, 16, 5],
        'circle-opacity': 0.8,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff'
      },
      // Add a filter to remove any null or 0 values
      filter: ['>', ['to-number', ['get', 'buildingCategory']], 0]
    } as LayerSpecification
  },

  // Buildings colored by building status
  {
    id: 'buildings_by_status',
    label: 'Buildings by Status',
    unit: 'status',
    info: 'Building locations in Vaud colored by their status',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/buildings.pmtiles`,
      minzoom: 12
    } as VectorSourceSpecification,
    layer: {
      id: 'buildings_by_status-layer',
      type: 'circle',
      source: 'buildings_by_status',
      'source-layer': 'buildings',
      paint: {
        // Circle color based on building status
        'circle-color': [
          'match',
          ['get', 'buildingStatus'],
          1001,
          '#4CAF50', // En projet (In planning)
          1002,
          '#FFC107', // Autorisé (Authorized)
          1003,
          '#FF9800', // En construction (Under construction)
          1004,
          '#2196F3', // Existant (Existing)
          1005,
          '#9C27B0', // Non utilisable (Not usable)
          1007,
          '#F44336', // Démoli (Demolished)
          1008,
          '#795548', // Non réalisé (Not realized)
          '#9E9E9E' // Other/unknown status
        ],
        // Circle size based on zoom level
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 1, 14, 3, 16, 5],
        'circle-opacity': 0.8,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff'
      },
      // Add a filter to remove any null or 0 values
      filter: ['>', ['to-number', ['get', 'buildingStatus']], 0]
    } as LayerSpecification
  },

  // Buildings classified by building class
  {
    id: 'buildings_by_class',
    label: 'Buildings by Class',
    unit: 'class',
    info: 'Building locations in Vaud colored by their class/type',
    source: {
      type: 'vector',
      url: `pmtiles://${baseUrl}/buildings.pmtiles`,
      minzoom: 12
    } as VectorSourceSpecification,
    layer: {
      id: 'buildings_by_class-layer',
      type: 'circle',
      source: 'buildings_by_class',
      'source-layer': 'buildings',
      paint: {
        // Circle color based on building class
        'circle-color': [
          'match',
          ['get', 'buildingClass'],
          1110,
          '#3949AB', // Detached houses
          1121,
          '#EF5350', // Semi-detached houses
          1122,
          '#EC407A', // Row/terraced houses
          1130,
          '#AB47BC', // Apartment buildings
          1180,
          '#26A69A', // Buildings with mixed use
          1220,
          '#66BB6A', // Hotel, restaurant
          1230,
          '#FFA726', // Commercial buildings
          1240,
          '#FF7043', // Office buildings
          1241,
          '#78909C', // Bank/insurance buildings
          1250,
          '#8D6E63', // Retail buildings
          1260,
          '#29B6F6', // Educational buildings
          1271,
          '#FF4081', // Hospital buildings
          1272,
          '#7E57C2', // Care homes
          1273,
          '#26C6DA', // Prisons
          1274,
          '#D4E157', // Cultural buildings
          1275,
          '#FDD835', // Sports facilities
          1280,
          '#5E35B1', // Industry/factory
          1290,
          '#F44336', // Storage facilities
          '#BDBDBD' // Other/unknown class
        ],
        // Circle size based on zoom level
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 1, 14, 3, 16, 5],
        'circle-opacity': 0.8,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff'
      },
      // Add a filter to remove any null or 0 values
      filter: ['>', ['to-number', ['get', 'buildingClass']], 0]
    } as LayerSpecification
  }
]
