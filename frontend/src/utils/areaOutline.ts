/**
 * The outline of a set of communes, as the server gives it.
 *
 * It is one Polygon or a MultiPolygon (Lausanne has a piece apart from the
 * rest), with holes when a commune sits inside another. The picker cuts the
 * network canvas to it and draws it on the `bc-area` source, like the circle.
 * Pure functions here, the map calls live in the overlay.
 */
import type { AreaOutline } from '@/services/trafficAnalysis'
import type { AreaFeatureCollection } from '@/utils/areaCircle'

type Ring = [number, number][]

function polygonsOf(outline: AreaOutline): Ring[][] {
  if (outline.type === 'Polygon') return [outline.coordinates as Ring[]]
  return outline.coordinates as Ring[][]
}

/** Every ring of the outline, outer rings and holes, in lon/lat. */
export function outlineRings(outline: AreaOutline | null): Ring[] {
  if (!outline) return []
  return polygonsOf(outline).flat()
}

/** The outline as the picker source reads it. No handle: there is nothing to drag. */
export function outlineFeatures(outline: AreaOutline | null, ok: boolean): AreaFeatureCollection {
  if (!outline) return { type: 'FeatureCollection', features: [] }
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry:
          outline.type === 'Polygon'
            ? { type: 'Polygon', coordinates: outline.coordinates as Ring[] }
            : { type: 'MultiPolygon', coordinates: outline.coordinates as Ring[][] },
        properties: { role: 'ring', ok: ok ? 1 : 0 }
      }
    ]
  }
}

/** The box around the outline, null when there is none. */
export function outlineBbox(outline: AreaOutline | null): [number, number, number, number] | null {
  let box: [number, number, number, number] | null = null
  for (const ring of outlineRings(outline)) {
    for (const [lon, lat] of ring) {
      box = box
        ? [
            Math.min(box[0], lon),
            Math.min(box[1], lat),
            Math.max(box[2], lon),
            Math.max(box[3], lat)
          ]
        : [lon, lat, lon, lat]
    }
  }
  return box
}
