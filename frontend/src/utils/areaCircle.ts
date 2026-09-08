/**
 * The circle the user drags to pick an area.
 *
 * Its own source, like the pointer: it holds two features and it is redrawn on
 * every mouse move, so it must never sit on the graph source. Pure functions
 * here, the map calls live in components/map/AreaPickerOverlay.vue.
 */
import type { TrafficAreaSelection } from '@/stores/layers/types'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import type { GraphColors } from '@/utils/epflBasemap'
import type { LayerSpecification } from 'maplibre-gl'

export const AREA_SOURCE = 'bc-area'

// Enough for a circle of a few km to read as round at any zoom the picker uses.
const STEPS = 64

export interface AreaFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry:
      | { type: 'Polygon'; coordinates: [number, number][][] }
      | { type: 'Point'; coordinates: [number, number] }
    properties: { role: 'ring' | 'handle'; ok: number }
  }>
}

export function emptyArea(): AreaFeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

/**
 * The ring and its centre handle.
 *
 * The radius is in metres, so the ring is built in degrees with the metres per
 * degree of its own latitude. Over a few km the difference with a true geodesic
 * circle is under a metre, and the backend cuts the area with the same flat
 * approximation.
 */
export function areaFeatures(circle: TrafficAreaSelection, ok: boolean): AreaFeatureCollection {
  const dLat = circle.radiusM / mPerDegLat
  const dLon = circle.radiusM / Math.max(mPerDegLon(circle.lat), 1)

  const ring: [number, number][] = []
  for (let i = 0; i <= STEPS; i++) {
    const angle = (i / STEPS) * 2 * Math.PI
    ring.push([circle.lon + dLon * Math.cos(angle), circle.lat + dLat * Math.sin(angle)])
  }

  const flag = ok ? 1 : 0
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [ring] },
        properties: { role: 'ring', ok: flag }
      },
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [circle.lon, circle.lat] },
        properties: { role: 'handle', ok: flag }
      }
    ]
  }
}

export const AREA_FILL_LAYER = 'bc-area-fill'
const AREA_LINE_LAYER = 'bc-area-line'
const AREA_HANDLE_LAYER = 'bc-area-handle'

export function areaLayerIds(): string[] {
  return [AREA_FILL_LAYER, AREA_LINE_LAYER, AREA_HANDLE_LAYER]
}

/**
 * Accent when the tool can run here, grey when it cannot. Red would be the
 * design's delete colour, and refusing an area is not a delete.
 */
export function areaLayers(colors: GraphColors): LayerSpecification[] {
  const tint = ['case', ['==', ['get', 'ok'], 1], colors.accent, colors.grey] as never
  return [
    {
      id: AREA_FILL_LAYER,
      type: 'fill',
      source: AREA_SOURCE,
      filter: ['==', ['get', 'role'], 'ring'],
      paint: { 'fill-color': tint, 'fill-opacity': 0.12 }
    },
    {
      id: AREA_LINE_LAYER,
      type: 'line',
      source: AREA_SOURCE,
      filter: ['==', ['get', 'role'], 'ring'],
      paint: { 'line-color': tint, 'line-width': 1.5 }
    },
    {
      id: AREA_HANDLE_LAYER,
      type: 'circle',
      source: AREA_SOURCE,
      filter: ['==', ['get', 'role'], 'handle'],
      paint: {
        'circle-radius': 4,
        'circle-color': colors.paper,
        'circle-stroke-color': tint,
        'circle-stroke-width': 1.5
      }
    }
  ]
}
