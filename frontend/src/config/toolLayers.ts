/**
 * Layers a tool puts on the map for itself.
 *
 * They are not datasets: they never show in the datasets panel, they are not
 * saved in an investigation, and `mapConfig.ts` does not know about them. The
 * tool adds them through the raw MapLibre map and removes them when it closes.
 */

import { baseUrl } from '@/config/layerTypes'
import type {
  ExpressionSpecification,
  LayerSpecification,
  SourceSpecification,
  StyleSpecification
} from 'maplibre-gl'

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
const MAIN_ROADS = ['motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link']
const isMainRoad: ExpressionSpecification = ['in', ['get', 'highway'], ['literal', MAIN_ROADS]]

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
      // From far away the main roads are a bit wider, so the country reads as
      // a network and not as noise. By z14 every street is the same hairline
      // as the graph overlay.
      'line-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        6,
        ['case', isMainRoad, 1.1, 0.45],
        10,
        ['case', isMainRoad, 1.4, 0.8],
        14,
        1.2
      ]
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

/**
 * The Swiss communes, what the user clicks in the Municipalities mode.
 *
 * One vector source of polygons (build_municipalities.py), one layer
 * `communes`. The feature id is the BFS number: tippecanoe moves it out of the
 * properties into the id, so the picker reads `feature.id`, and the hover and
 * the selection ride feature-state on that id. The tiles start at z7, under
 * that the layer shows nothing.
 */
export const COMMUNES_SOURCE = 'tool-communes'
export const COMMUNES_SOURCE_LAYER = 'communes'
export const COMMUNES_MIN_ZOOM = 7
export const COMMUNES_HIT_LAYER = 'tool-communes-hit'
const COMMUNES_SEL_FILL_LAYER = 'tool-communes-sel-fill'
const COMMUNES_LINE_LAYER = 'tool-communes-line'
const COMMUNES_SEL_LINE_LAYER = 'tool-communes-sel-line'
const COMMUNES_HOVER_LAYER = 'tool-communes-hover'

export const swissCommunesSource: SourceSpecification = {
  type: 'vector',
  url: `pmtiles://${baseUrl}/swiss_communes.pmtiles`,
  attribution: '© swisstopo'
} as SourceSpecification

export interface CommuneColors {
  ink: string
  grey: string
  accent: string
}

export function communeLayerIds(): string[] {
  return [
    COMMUNES_HIT_LAYER,
    COMMUNES_SEL_FILL_LAYER,
    COMMUNES_LINE_LAYER,
    COMMUNES_SEL_LINE_LAYER,
    COMMUNES_HOVER_LAYER
  ]
}

/**
 * Hairline borders in faint ink, a picked commune in accent when the tool can
 * run on the selection and grey when it cannot, the hovered one in accent.
 * The accent is the pointer, like on the graph.
 */
export function communeLayers(colors: CommuneColors): LayerSpecification[] {
  const selected = ['boolean', ['feature-state', 'selected'], false]
  const hovered = ['boolean', ['feature-state', 'hover'], false]
  const tint = ['case', ['boolean', ['feature-state', 'ok'], false], colors.accent, colors.grey]
  const base = {
    source: COMMUNES_SOURCE,
    'source-layer': COMMUNES_SOURCE_LAYER,
    minzoom: COMMUNES_MIN_ZOOM
  }
  return [
    {
      ...base,
      id: COMMUNES_HIT_LAYER,
      type: 'fill',
      // Invisible: what the click and the hover point at. A hit test does not
      // care about opacity.
      paint: { 'fill-color': colors.ink, 'fill-opacity': 0 }
    },
    {
      ...base,
      id: COMMUNES_SEL_FILL_LAYER,
      type: 'fill',
      paint: {
        'fill-color': tint,
        'fill-opacity': ['case', selected, 0.1, 0]
      }
    },
    {
      ...base,
      id: COMMUNES_LINE_LAYER,
      type: 'line',
      paint: { 'line-color': colors.ink, 'line-opacity': 0.25, 'line-width': 1 }
    },
    {
      ...base,
      id: COMMUNES_SEL_LINE_LAYER,
      type: 'line',
      paint: {
        'line-color': tint,
        'line-opacity': ['case', selected, 1, 0],
        'line-width': 1.5
      }
    },
    {
      ...base,
      id: COMMUNES_HOVER_LAYER,
      type: 'line',
      paint: {
        'line-color': colors.accent,
        'line-opacity': ['case', hovered, 1, 0],
        'line-width': 1.5
      }
    }
  ] as LayerSpecification[]
}
