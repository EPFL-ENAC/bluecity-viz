/**
 * The street graph overlay.
 *
 * The Substrat basemap draws no line, so this owns every line on the map.
 * Ported from the design handoff (design/carto/bluecity-graph.js), but fed by
 * our own edge GeoJSON instead of OpenMapTiles: the design filtered by street
 * name, we filter by feature id, which is exact.
 *
 * Vocabulary (Bertin):
 *  - the graph is one grey hairline. From z14.5 a two-way street splits into
 *    two parallel hairlines, one per directed edge.
 *  - data is colour and width.
 *  - a modification is ink and shape, never colour: a closed edge is ink cut
 *    by paper dashes, a speed limit is ink with direction arrows. A square
 *    badge sits at the middle of the street.
 *  - the accent blue is only ever the pointer: hover and selection.
 */
import type { GraphColors } from '@/utils/epflBasemap'
import type { ExpressionSpecification, LayerSpecification, Map as MapLibreMap } from 'maplibre-gl'

export const GRAPH_SOURCE = 'bc-edges'
export const BADGE_SOURCE = 'bc-badges'
export const CVRP_SOURCE = 'bc-cvrp-routes'
export const CVRP_POINT_SOURCE = 'bc-cvrp-pts'

export const BADGE_PAPER = 'bc-badge-paper'
export const BADGE_INK = 'bc-badge-ink'
export const ARROW_PAPER = 'bc-arrow'
export const ARROW_INK = 'bc-arrow-ink'
export const DEPOT_BADGE = 'bc-depot'

/** The layer the basemap puts street names in. Everything goes under it. */
export const BEFORE_LAYER = 'rd-label'

type Stop = [number, number]

/** Zoom interpolation, with the arithmetic done on the stop values.
 *  MapLibre only allows ["zoom"] as the input of a top level interpolate. */
function zi(stops: Stop[], fn?: (value: number) => unknown): ExpressionSpecification {
  const out: unknown[] = ['interpolate', ['linear'], ['zoom']]
  for (const [zoom, value] of stops) {
    out.push(zoom, fn ? fn(value) : value)
  }
  return out as unknown as ExpressionSpecification
}

const GRAPH_STOPS: Stop[] = [
  [12, 0.6],
  [14, 1.2],
  [16, 2.2]
]
const MOD_STOPS: Stop[] = [
  [12, 3],
  [14, 5],
  [16, 9]
]
const LANE_STOPS: Stop[] = [
  [13, 1.6],
  [15, 3.2],
  [17, 6]
]
const DATA_STOPS: Stop[] = [
  [12, 1.4],
  [14, 3],
  [16, 6]
]

/** graph hairline, times a factor */
export function wGraph(k = 1, add = 0): ExpressionSpecification {
  return zi(GRAPH_STOPS, (v) => v * k + add)
}

/** modification stroke, times a factor */
export function wMod(k = 1, add = 0): ExpressionSpecification {
  return zi(MOD_STOPS, (v) => v * k + add)
}

/** data stroke: the zoom width times the road class factor */
export function wData(k = 1, add = 0): ExpressionSpecification {
  return zi(DATA_STOPS, (v) => (add ? v * k + add : ['*', v * k, ['get', 'cls']]))
}

/**
 * The lane offset. Every feature is pushed to the right of its own travel
 * direction, so the two directed edges of a street land on opposite sides.
 * A one-way street keeps its single line on the centre.
 */
export function laneOffset(k = 1): ExpressionSpecification {
  return zi(LANE_STOPS, (v) => [
    'case',
    ['==', ['get', 'two'], 0],
    0,
    ['*', v * k, ['get', 'side']]
  ])
}

// The single centre line fades out as the two lanes fade in.
const laneFade = zi([
  [14.2, 0],
  [14.8, 1]
])
const laneHide = zi([
  [14.2, 1],
  [14.8, 0]
])

const ROUND = { 'line-cap': 'round', 'line-join': 'round' } as const
const BUTT = { 'line-cap': 'butt', 'line-join': 'round' } as const

const NOTHING: ExpressionSpecification = ['in', ['id'], ['literal', []]]

/** the lane offset of the state's own direction, for hover and selection */
function stateOffset(name: string, k = 1): ExpressionSpecification {
  return zi(LANE_STOPS, (v) => [
    'case',
    ['==', ['coalesce', ['feature-state', name], 0], 0],
    0,
    ['*', v * k, ['get', 'side']]
  ])
}

export interface GraphLayerOptions {
  colors: GraphColors
  /** 'scenario' shows ink modifications, 'result' lets the data own the colour */
  mode?: 'scenario' | 'result'
}

/**
 * Every layer of the overlay, in draw order.
 *
 * Pure: it returns specs, it does not touch a map. Filters start empty and are
 * narrowed later with setFilter, so the set of layers never changes.
 */
export function buildGraphLayers(options: GraphLayerOptions): LayerSpecification[] {
  const { colors } = options
  const result = options.mode === 'result'
  const { ink, paper, grey, accent } = colors
  const src = { source: GRAPH_SOURCE }

  const layers: LayerSpecification[] = [
    // 1 · the graph. One hairline far out, two lanes from z14.5.
    {
      ...src,
      id: 'bc-graph-one',
      type: 'line',
      filter: ['==', ['get', 'two'], 0],
      layout: ROUND,
      paint: { 'line-color': grey, 'line-width': wGraph() }
    },
    {
      ...src,
      id: 'bc-graph-two',
      type: 'line',
      filter: ['==', ['get', 'two'], 1],
      layout: ROUND,
      paint: { 'line-color': grey, 'line-width': wGraph(), 'line-opacity': laneHide }
    },
    {
      ...src,
      id: 'bc-lanes',
      type: 'line',
      filter: ['==', ['get', 'two'], 1],
      layout: ROUND,
      paint: {
        'line-color': grey,
        'line-width': wGraph(),
        'line-offset': laneOffset(),
        'line-opacity': laneFade
      }
    },

    // 2 · data. Drawn on the centre line, both directions summed, on a paper
    //     casing so it separates from the grey graph.
    {
      ...src,
      id: 'bc-data-casing',
      type: 'line',
      filter: NOTHING,
      layout: ROUND,
      paint: { 'line-color': paper, 'line-width': wData(1, 2), 'line-opacity': 0.9 }
    },
    {
      ...src,
      id: 'bc-data',
      type: 'line',
      filter: NOTHING,
      layout: ROUND,
      paint: {
        'line-color': [
          'coalesce',
          ['feature-state', 'c'],
          grey
        ] as unknown as ExpressionSpecification,
        'line-width': wData()
      }
    },

    // 3 · modifications, ink and shape. Scenario mode draws the full ink
    //     stroke; result mode lets the data colour own it and keeps the shape.
    {
      ...src,
      id: 'bc-mod-casing',
      type: 'line',
      filter: NOTHING,
      layout: BUTT,
      paint: { 'line-color': paper, 'line-width': wMod(1, 3), 'line-offset': stateOffset('ml') }
    },
    {
      ...src,
      id: 'bc-mod',
      type: 'line',
      filter: NOTHING,
      layout: BUTT,
      paint: {
        'line-color': result
          ? (['coalesce', ['feature-state', 'c'], ink] as unknown as ExpressionSpecification)
          : ink,
        'line-width': wMod(),
        'line-offset': stateOffset('ml')
      }
    },
    // a closed edge: paper dashes cut the ink, so it reads as a barrier
    {
      ...src,
      id: 'bc-mod-cut',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'butt' },
      paint: {
        'line-color': paper,
        'line-width': wMod(),
        'line-offset': stateOffset('ml'),
        'line-dasharray': [0.6, 1.2]
      }
    },
    // in result mode a closed edge carries no traffic, so it thins to a dashed
    // ink hairline instead of a full stroke
    {
      ...src,
      id: 'bc-mod-closed-result',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'butt' },
      paint: {
        'line-color': ink,
        'line-width': wGraph(1.4),
        'line-offset': stateOffset('ml'),
        'line-dasharray': [2, 2]
      }
    },
    // direction arrows, pointing with travel
    {
      ...src,
      id: 'bc-mod-arrows',
      type: 'symbol',
      filter: NOTHING,
      layout: {
        'symbol-placement': 'line',
        'symbol-spacing': 44,
        'icon-image': result ? ARROW_INK : ARROW_PAPER,
        'icon-size': zi([
          [13, 0.45],
          [16, 0.8]
        ]) as unknown as number,
        'icon-rotation-alignment': 'map',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
      }
    },

    // 4 · pointer. The accent is used for this and nothing else.
    {
      ...src,
      id: 'bc-hover-halo',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'round' },
      paint: {
        'line-color': accent,
        'line-width': wGraph(2.2, 6),
        'line-offset': stateOffset('hl'),
        'line-opacity': 0.18
      }
    },
    {
      ...src,
      id: 'bc-hover',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'round' },
      paint: {
        'line-color': accent,
        'line-width': wGraph(2.2),
        'line-offset': stateOffset('hl')
      }
    },
    {
      ...src,
      id: 'bc-selected',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'butt' },
      paint: {
        'line-color': accent,
        'line-width': wMod(1, 6),
        'line-offset': stateOffset('sl'),
        'line-opacity': 0.25
      }
    },
    // the lane left out of a one-direction selection, so the exclusion shows
    {
      ...src,
      id: 'bc-selected-ghost',
      type: 'line',
      filter: NOTHING,
      layout: { 'line-cap': 'butt' },
      paint: {
        'line-color': accent,
        'line-width': wGraph(1.4),
        'line-offset': laneOffset(),
        'line-opacity': 0.35,
        'line-dasharray': [1, 1.5]
      }
    },

    // 5 · badges. Symbol layout takes no feature state and cannot build an
    //     offset expression, so there is one layer per case: the badge sits on
    //     the centre for a both modification, and shifts onto its lane for a
    //     one-direction one.
    ...badgeLayers(colors),

    // 5 · waste collection. One hue per vehicle, braided so a shared street
    //     shows every vehicle that uses it. Same paper casing as the data.
    ...cvrpLayers(colors)
  ]

  return layers
}

const CVRP_STOPS: Stop[] = [
  [13, 1.2],
  [15, 3],
  [17, 6]
]

/** the braid: each route rides its own slot around the centre line */
export function cvrpOffset(): ExpressionSpecification {
  return zi(CVRP_STOPS, (v) => ['*', v, ['get', 'slot']])
}

export function wCvrp(k = 1, add = 0): ExpressionSpecification {
  return zi(
    [
      [12, 1.6],
      [14, 2.6],
      [16, 4]
    ],
    (v) => v * k + add
  )
}

/**
 * Route lines, collection points and the depot.
 *
 * The opacity rides feature-state `dim`: hovering one vehicle drops the others
 * to 25 % instead of hiding them, so the shared streets stay readable.
 */
function cvrpLayers(colors: GraphColors): LayerSpecification[] {
  const { ink, paper, accent } = colors
  const line = { source: CVRP_SOURCE }
  const point = { source: CVRP_POINT_SOURCE }

  return [
    {
      ...line,
      id: 'bc-cvrp-casing',
      type: 'line',
      filter: NOTHING,
      layout: ROUND,
      paint: { 'line-color': paper, 'line-width': wCvrp(1, 2), 'line-offset': cvrpOffset() }
    },
    {
      ...line,
      id: 'bc-cvrp-halo',
      type: 'line',
      filter: NOTHING,
      layout: ROUND,
      paint: {
        'line-color': accent,
        'line-width': wCvrp(1, 8),
        'line-offset': cvrpOffset(),
        'line-opacity': 0.16
      }
    },
    {
      ...line,
      id: 'bc-cvrp',
      type: 'line',
      filter: NOTHING,
      layout: ROUND,
      paint: {
        'line-color': ['get', 'color'] as unknown as ExpressionSpecification,
        'line-width': wCvrp(),
        'line-offset': cvrpOffset(),
        'line-opacity': [
          'case',
          ['==', ['coalesce', ['feature-state', 'dim'], 0], 1],
          0.25,
          1
        ] as unknown as ExpressionSpecification
      }
    },
    {
      ...point,
      id: 'bc-cvrp-point',
      type: 'circle',
      filter: ['!=', ['get', 'kind'], 'depot'],
      paint: {
        'circle-radius': zi([
          [13, 1.6],
          [16, 3.4]
        ]) as unknown as number,
        // a point the solver could not reach is hollow, not absent
        'circle-color': [
          'case',
          ['==', ['get', 'reached'], 0],
          paper,
          ink
        ] as unknown as ExpressionSpecification,
        'circle-stroke-width': 1,
        'circle-stroke-color': ink
      }
    },
    {
      ...point,
      id: 'bc-cvrp-depot',
      type: 'symbol',
      filter: ['==', ['get', 'kind'], 'depot'],
      layout: {
        'icon-image': DEPOT_BADGE,
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-size': 1
      }
    }
  ]
}

/** How far the badge shifts, in pixels, to sit on its lane. */
const BADGE_SHIFT = 10

/**
 * One symbol layer per (direction, closed) case, plus the → / ← tag layers.
 * Every offset is a constant, which is what MapLibre needs here.
 */
function badgeLayers(colors: GraphColors): LayerSpecification[] {
  const { ink, paper } = colors
  const out: LayerSpecification[] = []

  for (const dir of ['both', 'fwd', 'bwd'] as const) {
    const shift = dir === 'both' ? 0 : dir === 'fwd' ? BADGE_SHIFT : -BADGE_SHIFT

    for (const closed of [true, false]) {
      const size = closed ? 15 : 11
      out.push({
        source: BADGE_SOURCE,
        id: `bc-badge-${dir}-${closed ? 'closed' : 'speed'}`,
        type: 'symbol',
        filter: ['all', ['==', ['get', 'dir'], dir], ['==', ['get', 'closed'], closed ? 1 : 0]],
        layout: {
          'icon-image': closed ? BADGE_INK : BADGE_PAPER,
          'icon-offset': [0, shift],
          'icon-rotation-alignment': 'viewport',
          'icon-pitch-alignment': 'viewport',
          'text-field': ['get', 'glyph'],
          'text-font': ['Noto Sans Bold'],
          'text-size': size,
          'text-letter-spacing': -0.02,
          // text-offset is in ems, so the pixel shift is divided by the size
          'text-offset': [0, (closed ? -0.05 : 0.02) + shift / size],
          'text-rotation-alignment': 'viewport',
          'text-pitch-alignment': 'viewport',
          'icon-allow-overlap': true,
          'text-allow-overlap': true,
          'icon-ignore-placement': true,
          'text-ignore-placement': true
        },
        paint: { 'text-color': closed ? paper : ink }
      })
    }

    if (dir === 'both') continue

    out.push({
      source: BADGE_SOURCE,
      id: `bc-badge-tag-${dir}`,
      type: 'symbol',
      filter: ['==', ['get', 'dir'], dir],
      layout: {
        'text-field': dir === 'fwd' ? '→' : '←',
        'text-font': ['Noto Sans Bold'],
        'text-size': 11,
        'text-offset': [1.55, shift / 11],
        'text-allow-overlap': true,
        'text-ignore-placement': true
      },
      paint: { 'text-color': ink, 'text-halo-color': paper, 'text-halo-width': 1.6 }
    })
  }

  return out
}

/** Every layer id the overlay owns, in draw order. */
export function graphLayerIds(): string[] {
  return buildGraphLayers({
    colors: { ink: '#000', paper: '#fff', grey: '#888', accent: '#00f' }
  }).map((l) => l.id)
}

// ---------- canvas images: the square badges and the direction arrow ----------

function canvas(size: number): HTMLCanvasElement {
  const element = document.createElement('canvas')
  element.width = element.height = size
  return element
}

/** A 22 px square: solid ink for a closed edge, paper with an ink border for a speed limit. */
export function badgeImage(fill: string, stroke: string, dpr = 2): ImageData {
  const size = 22 * dpr
  const ctx = canvas(size).getContext('2d') as CanvasRenderingContext2D
  ctx.fillStyle = fill
  ctx.fillRect(0, 0, size, size)
  ctx.strokeStyle = stroke
  ctx.lineWidth = 1.5 * dpr
  ctx.strokeRect(0.75 * dpr, 0.75 * dpr, size - 1.5 * dpr, size - 1.5 * dpr)
  return ctx.getImageData(0, 0, size, size)
}

/** A 10 px triangle, pointing along the way. */
export function arrowImage(color: string, dpr = 2): ImageData {
  const size = 10 * dpr
  const ctx = canvas(size).getContext('2d') as CanvasRenderingContext2D
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(0, 0.5 * dpr)
  ctx.lineTo(size, size / 2)
  ctx.lineTo(0, size - 0.5 * dpr)
  ctx.lineTo(2.5 * dpr, size / 2)
  ctx.closePath()
  ctx.fill()
  return ctx.getImageData(0, 0, size, size)
}

/** The depot: an ink square with a paper D. */
export function depotImage(fill: string, text: string, dpr = 2): ImageData {
  const size = 18 * dpr
  const ctx = canvas(size).getContext('2d') as CanvasRenderingContext2D
  ctx.fillStyle = fill
  ctx.fillRect(0, 0, size, size)
  ctx.fillStyle = text
  ctx.font = `bold ${11 * dpr}px ui-monospace, monospace`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('D', size / 2, size / 2 + 0.5 * dpr)
  return ctx.getImageData(0, 0, size, size)
}

/** Register (or replace) the images the overlay draws with. */
export function addGraphImages(map: MapLibreMap, colors: GraphColors): void {
  const images: Array<[string, ImageData]> = [
    [BADGE_PAPER, badgeImage(colors.paper, colors.ink)],
    [BADGE_INK, badgeImage(colors.ink, colors.ink)],
    [ARROW_PAPER, arrowImage(colors.paper)],
    [ARROW_INK, arrowImage(colors.ink)],
    [DEPOT_BADGE, depotImage(colors.ink, colors.paper)]
  ]

  for (const [id, data] of images) {
    if (map.hasImage(id)) map.updateImage(id, data)
    else map.addImage(id, data, { pixelRatio: 2 })
  }
}

// ---------- what the scenario turns into, for the map ----------

export interface ModDraw {
  /** the directed feature ids the ink stroke covers */
  strokeIds: number[]
  /** those of them that are closed, drawn as a dashed hairline in result mode */
  closedIds: number[]
  /** those that keep a speed limit, so they get direction arrows */
  arrowIds: number[]
  /** ids that sit on one lane only, so the stroke is offset onto it */
  laneIds: number[]
  badges: BadgeFeature[]
}

export interface BadgeFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: {
    dir: string
    closed: number
    glyph: string
    key: string
  }
}

export function emptyBadges(): { type: 'FeatureCollection'; features: BadgeFeature[] } {
  return { type: 'FeatureCollection', features: [] }
}

interface StreetLike {
  key: string
  fwdId?: number
  bwdId?: number
  at: [number, number]
}

interface ModLike {
  action: string
  dir: string
}

/**
 * Turn the scenario into the ids each modification layer draws and one badge
 * per modified street.
 */
export function drawFor(
  mods: Iterable<[string, ModLike]>,
  streets: Map<string, StreetLike>
): ModDraw {
  const draw: ModDraw = {
    strokeIds: [],
    closedIds: [],
    arrowIds: [],
    laneIds: [],
    badges: []
  }

  for (const [key, mod] of mods) {
    const street = streets.get(key)
    if (!street) continue

    const ids: number[] = []
    if (mod.dir !== 'bwd' && street.fwdId !== undefined) ids.push(street.fwdId)
    if (mod.dir !== 'fwd' && street.bwdId !== undefined) ids.push(street.bwdId)
    if (ids.length === 0) continue

    const closed = mod.action === 'remove'
    const oneLane = mod.dir !== 'both'

    draw.strokeIds.push(...ids)
    if (closed) draw.closedIds.push(...ids)
    else draw.arrowIds.push(...ids)
    if (oneLane) draw.laneIds.push(...ids)

    draw.badges.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: street.at },
      properties: {
        dir: mod.dir,
        closed: closed ? 1 : 0,
        glyph: closed ? '×' : mod.action,
        key
      }
    })
  }

  return draw
}

/** `['in', ['id'], ['literal', ids]]`, the filter every modification layer uses. */
export function idFilter(ids: number[]): ExpressionSpecification {
  return ['in', ['id'], ['literal', ids]] as unknown as ExpressionSpecification
}

function setFilter(map: MapLibreMap, id: string, filter: ExpressionSpecification): void {
  if (map.getLayer(id)) map.setFilter(id, filter)
}

/** Point every modification layer at the streets the scenario changed. */
export function applyModifications(
  map: MapLibreMap,
  draw: ModDraw,
  mode: 'scenario' | 'result'
): void {
  const result = mode === 'result'
  // In result mode a closed edge is a dashed hairline, not a full ink stroke.
  const stroke = result
    ? draw.strokeIds.filter((id) => !draw.closedIds.includes(id))
    : draw.strokeIds

  setFilter(map, 'bc-mod-casing', idFilter(stroke))
  setFilter(map, 'bc-mod', idFilter(stroke))
  setFilter(map, 'bc-mod-cut', idFilter(result ? [] : draw.closedIds))
  setFilter(map, 'bc-mod-closed-result', idFilter(result ? draw.closedIds : []))
  setFilter(map, 'bc-mod-arrows', idFilter(draw.arrowIds))

  const source = map.getSource(BADGE_SOURCE)
  if (source && 'setData' in source) {
    ;(source as { setData: (data: unknown) => void }).setData({
      type: 'FeatureCollection',
      features: draw.badges
    })
  }
}

// ---------- waste collection, on the map ----------

export interface CvrpPointFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: { kind: 'point' | 'depot'; reached: number }
}

export interface CvrpDraw {
  /** the braided route lines, from routeFeatures() */
  routes: { type: 'FeatureCollection'; features: unknown[] }
  points: CvrpPointFeature[]
  /** 'routes' draws the vehicles, 'load' colours the graph by tonnage instead */
  mode: 'routes' | 'load'
  /** a stale solution answers an old scenario, so it fades */
  stale: boolean
}

export function emptyPoints(): { type: 'FeatureCollection'; features: CvrpPointFeature[] } {
  return { type: 'FeatureCollection', features: [] }
}

function setData(map: MapLibreMap, id: string, data: unknown): void {
  const source = map.getSource(id)
  if (source && 'setData' in source) {
    ;(source as { setData: (value: unknown) => void }).setData(data)
  }
}

/** Put a solution on the map, or clear it when there is none. */
export function applyCvrp(map: MapLibreMap, draw: CvrpDraw | null): void {
  if (!draw || draw.mode === 'load') {
    setData(map, CVRP_SOURCE, { type: 'FeatureCollection', features: [] })
    setData(map, CVRP_POINT_SOURCE, emptyPoints())
    return
  }

  setData(map, CVRP_SOURCE, draw.routes)
  setData(map, CVRP_POINT_SOURCE, { type: 'FeatureCollection', features: draw.points })

  const all: ExpressionSpecification = ['!=', ['get', 'route_id'], -1]
  setFilter(map, 'bc-cvrp-casing', all)
  setFilter(map, 'bc-cvrp', all)

  const opacity = draw.stale ? 0.4 : 1
  if (map.getLayer('bc-cvrp')) map.setPaintProperty('bc-cvrp', 'line-opacity', opacity)
}

/** Highlight one vehicle: an accent halo on it, the others dimmed. */
export function applyCvrpHover(map: MapLibreMap, routeId: number | null): void {
  if (!map.getLayer('bc-cvrp')) return

  if (routeId === null) {
    setFilter(map, 'bc-cvrp-halo', NOTHING)
    map.setPaintProperty('bc-cvrp', 'line-opacity', 1)
    return
  }

  setFilter(map, 'bc-cvrp-halo', ['==', ['get', 'route_id'], routeId])
  map.setPaintProperty('bc-cvrp', 'line-opacity', [
    'case',
    ['==', ['get', 'route_id'], routeId],
    1,
    0.25
  ] as unknown as number)
}
