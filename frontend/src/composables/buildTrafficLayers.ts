import type { EdgeGeometry } from '@/services/trafficAnalysis'
import type { ModificationAction } from '@/stores/trafficAnalysis'
import { createHullOutline, type HullOutline, type Point } from '@/utils/geometry'
import { PathStyleExtension } from '@deck.gl/extensions'
import { PathLayer, TextLayer } from '@deck.gl/layers'

// Colors for the modification types
export const MODIFICATION_COLORS: Record<ModificationAction, [number, number, number, number]> = {
  remove: [0, 0, 0, 255], // Black for removed (#000000)
  speed50: [220, 38, 38, 255], // Red for 50 km/h (#dc2626)
  speed30: [251, 146, 60, 255], // Orange for 30 km/h (#fb923c)
  speed10: [250, 204, 21, 255] // Yellow for 10 km/h (#facc15)
}

// What the icon in the middle of a modified edge says
const SPEED_LIMIT_TEXT: Record<ModificationAction, string> = {
  remove: '✕',
  speed10: '10',
  speed30: '30',
  speed50: '50'
}

/** The only glyphs the icon layer needs. The default set stops at ASCII 127,
 *  so without this the ✕ is a missing character and draws as an empty box. */
const ICON_CHARACTER_SET = ['0', '1', '3', '5', '✕']

/** Hull width around a modified edge, in meters. */
const HULL_WIDTH = 8

const GREY_EDGE: [number, number, number, number] = [136, 136, 136, 153]
const HOVER_COLOR: [number, number, number, number] = [0, 170, 255, 200]
const OUTLINE_COLOR: [number, number, number, number] = [0, 0, 0, 120]
const WHITE: [number, number, number, number] = [255, 255, 255, 255]
const BLACK: [number, number, number, number] = [0, 0, 0, 255]
const SIGN_RED: [number, number, number, number] = [220, 38, 38, 255]

// One instance, shared: a new extension every render would make deck compare it
const DASH_EXTENSION = new PathStyleExtension({ dash: true })

// Hoisted accessors, so the layer props are the same shape on every build
const getEdgePath = (d: EdgeGeometry) => d.coordinates
const getHullPath = (d: HullPath) => d.path
const getHullColor = (d: HullPath) => d.color
const getIconPosition = (d: ModifiedIcon) => d.position
const getIconText = (d: ModifiedIcon) => d.text
const getIconColor = (d: ModifiedIcon) => d.color
const getIconBackground = (d: ModifiedIcon) => d.background
const getIconBorderColor = (d: ModifiedIcon) => d.borderColor
const getIconBorderWidth = (d: ModifiedIcon) => d.borderWidth

/** An edge with the usage numbers the six visualizations read. */
export interface RouteEdge extends EdgeGeometry {
  frequency: number
  delta_count: number
  delta_frequency: number
  co2_per_km: number
  count: number
  co2_total: number
  co2_delta: number
  betweenness_centrality: number
  delta_betweenness: number
  delta_relative: number
}

export interface ModifiedEdge {
  key: string
  edge: EdgeGeometry
  action: ModificationAction
  hull: HullOutline
}

interface HullPath {
  path: Point[]
  color: [number, number, number, number]
}

interface ModifiedIcon {
  position: [number, number]
  text: string
  color: [number, number, number, number]
  background: [number, number, number, number]
  borderColor: [number, number, number, number]
  borderWidth: number
}

const EMPTY: never[] = []

/** The whole road network in grey. Pickable, so a click can modify any edge. */
export function buildBaseLayer(edges: EdgeGeometry[]) {
  return new PathLayer({
    id: 'traffic-graph-edges',
    data: edges,
    getPath: getEdgePath,
    getColor: GREY_EDGE,
    getWidth: 2,
    widthUnits: 'meters',
    widthMinPixels: 3,
    pickable: true
  })
}

/**
 * The one edge under the cursor.
 *
 * This replaces autoHighlight on the base layer. autoHighlight redraws on every
 * pointer move, and with interleaved: true a deck redraw repaints the whole
 * basemap. Here the data only changes when the cursor enters a different edge.
 */
export function buildHoverLayer(edge: EdgeGeometry | null) {
  return new PathLayer({
    id: 'traffic-hover',
    data: edge ? [edge] : EMPTY,
    getPath: getEdgePath,
    getColor: HOVER_COLOR,
    getWidth: 4,
    widthUnits: 'pixels',
    widthMinPixels: 4,
    widthMaxPixels: 14,
    pickable: false
  })
}

const routeWidth = (d: RouteEdge) => Math.max(2, Math.min(10, d.frequency * 100 + 2))
const outlineWidth = (d: RouteEdge) => Math.max(4, Math.min(12, d.frequency * 100 + 4))

/**
 * The colored result of a calculation: a dark outline plus the colored roads.
 *
 * The colors come from a byte buffer built once per mode, so switching mode
 * only changes updateTriggers. `data` keeps the same identity, which is what
 * stops deck from tesselating the 6k paths again.
 */
export function buildRouteLayers(options: {
  edges: RouteEdge[]
  colors: Uint8Array
  mode: string
  colorVersion: number
}) {
  const { edges, colors, mode, colorVersion } = options

  // deck gives us a scratch array per object, so this allocates nothing
  const getColor = (_d: RouteEdge, info: { index: number; target: number[] }) => {
    const { index, target } = info
    const at = index * 3
    target[0] = colors[at]
    target[1] = colors[at + 1]
    target[2] = colors[at + 2]
    target[3] = 255
    return target as [number, number, number, number]
  }

  return [
    new PathLayer({
      id: 'traffic-routes-outline',
      data: edges,
      getPath: getEdgePath,
      getColor: OUTLINE_COLOR,
      getWidth: outlineWidth,
      widthUnits: 'pixels',
      widthMinPixels: 4,
      widthMaxPixels: 12,
      pickable: false
    }),
    new PathLayer({
      id: 'traffic-routes',
      data: edges,
      getPath: getEdgePath,
      getColor,
      getWidth: routeWidth,
      widthUnits: 'pixels',
      widthMinPixels: 2,
      widthMaxPixels: 10,
      pickable: true,
      updateTriggers: {
        getColor: [mode, colorVersion]
      }
    })
  ]
}

/** The hull outline is the same as long as the edge is, so cache it per edge. */
export function hullFor(
  cache: Map<string, HullOutline>,
  key: string,
  edge: EdgeGeometry
): HullOutline {
  let hull = cache.get(key)
  if (!hull) {
    hull = createHullOutline(edge.coordinates, HULL_WIDTH)
    cache.set(key, hull)
  }
  return hull
}

/**
 * The modified edges: a dashed hull, the caps that close it, and one icon in
 * the middle. The icons used to be two TextLayers, one for the speed signs and
 * one for the crosses; the colors are per object so one layer does both.
 */
export function buildModifiedEdgeLayers(modified: ModifiedEdge[]) {
  const hullPaths: HullPath[] = []
  const caps: HullPath[] = []
  const icons: ModifiedIcon[] = []

  for (const item of modified) {
    const color = MODIFICATION_COLORS[item.action]
    const { hull } = item

    hullPaths.push({ path: hull.left, color }, { path: hull.right, color })
    if (hull.startCap.length) caps.push({ path: hull.startCap, color })
    if (hull.endCap.length) caps.push({ path: hull.endCap, color })

    const removed = item.action === 'remove'
    icons.push({
      position: hull.midpoint,
      text: SPEED_LIMIT_TEXT[item.action],
      // a removed edge is a white cross on black, a speed limit is a european
      // sign: black text, white disc, red ring
      color: removed ? WHITE : BLACK,
      background: removed ? BLACK : WHITE,
      borderColor: removed ? BLACK : SIGN_RED,
      borderWidth: removed ? 2 : 3
    })
  }

  return [
    new PathLayer({
      id: 'traffic-modified-edges-hull',
      data: hullPaths,
      getPath: getHullPath,
      getColor: getHullColor,
      getWidth: 2,
      widthUnits: 'meters',
      widthMinPixels: 2,
      widthMaxPixels: 8,
      getDashArray: [6, 4],
      dashJustified: true,
      pickable: false,
      extensions: [DASH_EXTENSION]
    }),
    new PathLayer({
      id: 'traffic-modified-edges-caps',
      data: caps,
      getPath: getHullPath,
      getColor: getHullColor,
      getWidth: 2,
      widthUnits: 'meters',
      widthMinPixels: 2,
      widthMaxPixels: 8,
      pickable: false
    }),
    new TextLayer({
      id: 'traffic-modified-edges-icons',
      data: icons,
      characterSet: ICON_CHARACTER_SET,
      getPosition: getIconPosition,
      getText: getIconText,
      getColor: getIconColor,
      getBackgroundColor: getIconBackground,
      getBorderColor: getIconBorderColor,
      getBorderWidth: getIconBorderWidth,
      getSize: 12,
      fontWeight: 'bold',
      background: true,
      backgroundPadding: [6, 4, 6, 4],
      backgroundBorderRadius: 30,
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      fontFamily: 'Arial, sans-serif',
      billboard: true,
      sizeUnits: 'pixels',
      pickable: false
    })
  ]
}

/**
 * One byte triple per edge for the given mode.
 *
 * The field to read and the color scale are picked once, outside the loop. The
 * old accessor ran a seven branch if/else, a d3 scale and a d3 rgb() parse per
 * edge, on every render.
 */
export function buildEdgeColors(
  edges: RouteEdge[],
  mode: string,
  getColor: (value: number) => [number, number, number]
): Uint8Array {
  const out = new Uint8Array(edges.length * 3)
  const read = valueReader(mode)

  for (let i = 0; i < edges.length; i++) {
    const [r, g, b] = getColor(read(edges[i]))
    const at = i * 3
    out[at] = r
    out[at + 1] = g
    out[at + 2] = b
  }

  return out
}

function valueReader(mode: string): (d: RouteEdge) => number {
  switch (mode) {
    case 'delta':
      return (d) => d.delta_count
    case 'co2':
      return (d) => d.co2_per_km
    case 'co2_delta':
      return (d) => d.co2_delta
    case 'betweenness':
      return (d) => d.betweenness_centrality
    case 'betweenness_delta':
      return (d) => d.delta_betweenness
    case 'delta_relative':
      return (d) => d.delta_relative
    case 'frequency':
    default:
      return (d) => d.frequency
  }
}
