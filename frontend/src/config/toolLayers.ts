/**
 * Layers a tool puts on the map for itself.
 *
 * They are not datasets: they never show in the datasets panel, they are not
 * saved in an investigation, and `mapConfig.ts` does not know about them. The
 * tool adds them through the raw MapLibre map and removes them when it closes.
 */

import { baseUrl } from '@/config/layerTypes'
import type { LayerSpecification, SourceSpecification } from 'maplibre-gl'

export interface ToolLayer {
  sourceId: string
  source: SourceSpecification
  layer: LayerSpecification
}

/**
 * The Swiss road network, so the user can see where the tool has streets
 * before picking a circle. Ink hairlines, no colour: it is a backdrop.
 */
export const swissNetworkLayer: ToolLayer = {
  sourceId: 'tool-swiss-network',
  source: {
    type: 'vector',
    url: `pmtiles://${baseUrl}/swiss_drive.pmtiles`,
    attribution: '© OpenStreetMap contributors'
  } as SourceSpecification,
  layer: {
    id: 'tool-swiss-network-line',
    type: 'line',
    source: 'tool-swiss-network',
    'source-layer': 'graph_edges',
    paint: {
      'line-color': '#8a8a8a',
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.3, 10, 0.5, 14, 1],
      'line-opacity': 0.7
    }
  } as LayerSpecification
}
