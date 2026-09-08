/**
 * Layers a tool puts on the map for itself.
 *
 * They are not datasets: they never show in the datasets panel, they are not
 * saved in an investigation, and `mapConfig.ts` does not know about them. The
 * tool adds them through the raw MapLibre map and removes them when it closes.
 */

import { baseUrl } from '@/config/layerTypes'
import type { LayerSpecification, SourceSpecification, StyleSpecification } from 'maplibre-gl'

export interface ToolLayer {
  sourceId: string
  source: SourceSpecification
  layer: LayerSpecification
}

/**
 * The Swiss road network, the preview of the area being picked.
 *
 * The picker draws it on a canvas of its own, cut to the circle, so on screen
 * it is the streets the tool would take, not a backdrop of the whole country.
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
      // The picker sets the colour: accent when the tool can run in the
      // circle, grey when it cannot.
      'line-color': '#8a8a8a',
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.5, 10, 0.8, 14, 1.2]
    }
  } as LayerSpecification
}

/** A style with nothing but the network, for a map that draws only that. */
export function swissNetworkStyle(): StyleSpecification {
  return {
    version: 8,
    sources: { [swissNetworkLayer.sourceId]: swissNetworkLayer.source },
    layers: [swissNetworkLayer.layer]
  }
}
