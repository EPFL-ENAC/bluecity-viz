/**
 * EPFL "Trait" vector basemap.
 *
 * Ported from the design handoff (design/carto/epfl-basemap.js) to an ES module.
 * "Trait" = technical ink-on-paper drawing: uniform hairlines, no colour, square
 * everything. A pure line plan is empty below ~z13, so the variants add a
 * tileable texture (hatch / cross / dots / flat tint) on buildings and landuse.
 * Textures are drawn on a canvas and registered with map.addImage(), there is no
 * image asset to ship.
 *
 * The EPFL red marker of the original file is left out on purpose: in this app
 * red only means a destructive action.
 */
import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'

const FONTS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
const ATTR = '© OpenFreeMap © OpenMapTiles · Données OpenStreetMap'

/** Lausanne, the area this app covers. */
export const CENTER: [number, number] = [6.6045, 46.5255]

export interface BasemapTheme {
  ink: string
  paper: string
  density: number
}

export const DEFAULTS: BasemapTheme = { ink: '#141414', paper: '#ffffff', density: 0.8 }

// shared vector source, tiles filled in by loadTiles()
const SRC = {
  type: 'vector' as const,
  tiles: [] as string[],
  minzoom: 0,
  maxzoom: 14,
  attribution: ATTR
}

// ---- colour helpers: every fill is the ink blended toward the paper ----
function hx(c: string): number[] {
  let s = c.replace('#', '')
  if (s.length === 3)
    s = s
      .split('')
      .map((x) => x + x)
      .join('')
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)]
}

function mix(a: string, b: string, t: number): string {
  const A = hx(a)
  const B = hx(b)
  return (
    '#' +
    [0, 1, 2]
      .map((i) =>
        Math.round(A[i] + (B[i] - A[i]) * t)
          .toString(16)
          .padStart(2, '0')
      )
      .join('')
  )
}

/** Merge a partial theme onto the defaults. */
export function theme(t?: Partial<BasemapTheme>): BasemapTheme {
  const clean: Partial<BasemapTheme> = {}
  if (t) {
    for (const k of Object.keys(t) as (keyof BasemapTheme)[]) {
      const v = t[k]
      if (v != null) Object.assign(clean, { [k]: v })
    }
  }
  return { ...DEFAULTS, ...clean }
}

/** texture lines on ground / water */
function lite(T: BasemapTheme): string {
  return mix(T.ink, T.paper, 0.58)
}

/** flat tints */
function faint(T: BasemapTheme, t: number): string {
  return mix(T.ink, T.paper, t)
}

// ---------- tileable texture images (canvas -> ImageData) ----------
export const PATTERN_IDS = [
  'hatch-bld',
  'hatch-land',
  'hatch-wood',
  'hatch-water',
  'cross-bld',
  'dot-bld',
  'dot-land'
]

function cv(s: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = c.height = s
  return c
}

function diagImg(s: number, gap: number, lw: number, color: string, cross = false): ImageData {
  const x = cv(s).getContext('2d') as CanvasRenderingContext2D
  x.strokeStyle = color
  x.lineWidth = lw
  x.lineCap = 'square'
  for (let i = -s; i <= 2 * s; i += gap) {
    x.beginPath()
    x.moveTo(i, 0)
    x.lineTo(i + s, s)
    x.stroke()
  }
  if (cross) {
    for (let j = -s; j <= 2 * s; j += gap) {
      x.beginPath()
      x.moveTo(j, s)
      x.lineTo(j + s, 0)
      x.stroke()
    }
  }
  return x.getImageData(0, 0, s, s)
}

function horizImg(s: number, gap: number, lw: number, color: string): ImageData {
  const x = cv(s).getContext('2d') as CanvasRenderingContext2D
  x.strokeStyle = color
  x.lineWidth = lw
  x.lineCap = 'square'
  for (let y = gap / 2; y < s; y += gap) {
    x.beginPath()
    x.moveTo(0, y + 0.5)
    x.lineTo(s, y + 0.5)
    x.stroke()
  }
  return x.getImageData(0, 0, s, s)
}

function dotImg(s: number, r: number, color: string): ImageData {
  const x = cv(s).getContext('2d') as CanvasRenderingContext2D
  x.fillStyle = color
  const d = (cx: number, cy: number) => {
    x.beginPath()
    x.arc(cx, cy, r, 0, 7)
    x.fill()
  }
  d(s / 2, s / 2)
  d(0, 0)
  d(s, 0)
  d(0, s)
  d(s, s)
  return x.getImageData(0, 0, s, s)
}

function genPattern(id: string, T: BasemapTheme): ImageData | undefined {
  const g = T.density
  const G = (v: number) => Math.max(3, Math.round(v / g))
  const S = (v: number) => Math.max(7, Math.round(v / g))
  const ink = T.ink
  const l = lite(T)
  switch (id) {
    case 'hatch-bld':
      return diagImg(16, G(6), 1.6, ink)
    case 'hatch-land':
      return diagImg(18, G(7), 1.3, l)
    case 'hatch-wood':
      return diagImg(16, G(6), 1.2, l)
    case 'hatch-water':
      return horizImg(12, G(5), 1.2, l)
    case 'cross-bld':
      return diagImg(18, G(7), 1.4, ink, true)
    case 'dot-bld':
      return dotImg(S(14), 1.5, ink)
    case 'dot-land':
      return dotImg(S(15), 1.3, l)
  }
  return undefined
}

/**
 * Generate a texture the first time the style asks for it. Call once per map,
 * the map keeps its theme in `__epflTheme`.
 */
export function wirePatterns(map: MapLibreMap): void {
  map.on('styleimagemissing', (e: { id: string }) => {
    if (PATTERN_IDS.indexOf(e.id) >= 0 && !map.hasImage(e.id)) {
      const img = genPattern(e.id, getMapTheme(map))
      if (!img) return
      try {
        map.addImage(e.id, img, { pixelRatio: 2 })
      } catch {
        // the image can already be there after a fast style swap
      }
    }
  })
}

/** Drop the generated textures so they are rebuilt with the new ink. */
export function clearPatterns(map: MapLibreMap): void {
  PATTERN_IDS.forEach((id) => {
    try {
      if (map.hasImage(id)) map.removeImage(id)
    } catch {
      // ignore
    }
  })
}

interface MapWithTheme extends MapLibreMap {
  __epflTheme?: BasemapTheme
}

export function getMapTheme(map: MapLibreMap): BasemapTheme {
  return (map as MapWithTheme).__epflTheme ?? DEFAULTS
}

export function setMapTheme(map: MapLibreMap, T: BasemapTheme): void {
  ;(map as MapWithTheme).__epflTheme = T
}

// ---------- variants ----------
// bld:  outline | hatch | cross | dot | solid | ink
// land / wood: none | tint | hatch | dot   ·   water: line | tint | hatch
interface Variant {
  wood: string
  land: string
  water: string
  bld: string
}

export const VARIANTS: Record<string, Variant> = {
  contour: { wood: 'none', land: 'none', water: 'line', bld: 'outline' },
  hachure: { wood: 'hatch', land: 'hatch', water: 'line', bld: 'hatch' },
  croisillon: { wood: 'none', land: 'dot', water: 'line', bld: 'cross' },
  trame: { wood: 'dot', land: 'dot', water: 'line', bld: 'dot' },
  aplat: { wood: 'tint', land: 'tint', water: 'tint', bld: 'solid' },
  gravure: { wood: 'hatch', land: 'hatch', water: 'hatch', bld: 'hatch' }
}

export const ORDER = ['contour', 'hachure', 'croisillon', 'trame', 'aplat', 'gravure']

const fade = ['interpolate', ['linear'], ['zoom'], 13, 0, 14, 1]

/** Build a MapLibre style for one variant and theme. */
export function buildStyle(key: string, t?: Partial<BasemapTheme>): StyleSpecification {
  const T = theme(t)
  const v = VARIANTS[key] || VARIANTS.contour
  const INK = T.ink
  const PAPER = T.paper
  // MapLibre's own types for hand-written layer arrays are very strict, the
  // shapes below come straight from the design engine and are known good.
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const L: any[] = [{ id: 'bg', type: 'background', paint: { 'background-color': PAPER } }]

  const woodF = ['in', 'class', 'wood', 'grass', 'scrub']
  if (v.wood === 'tint')
    L.push({
      id: 'wood',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landcover',
      filter: woodF,
      paint: { 'fill-color': faint(T, 0.9) }
    })
  if (v.wood === 'hatch')
    L.push({
      id: 'wood',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landcover',
      filter: woodF,
      paint: { 'fill-pattern': 'hatch-wood', 'fill-opacity': 0.9 }
    })
  if (v.wood === 'dot')
    L.push({
      id: 'wood',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landcover',
      filter: woodF,
      paint: { 'fill-pattern': 'dot-land', 'fill-opacity': 0.9 }
    })

  const landF = [
    'in',
    'class',
    'residential',
    'commercial',
    'retail',
    'industrial',
    'neighbourhood'
  ]
  if (v.land === 'tint')
    L.push({
      id: 'land',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landuse',
      filter: landF,
      paint: {
        'fill-color': [
          'match',
          ['get', 'class'],
          'industrial',
          faint(T, 0.86),
          'commercial',
          faint(T, 0.9),
          'retail',
          faint(T, 0.9),
          faint(T, 0.93)
        ]
      }
    })
  if (v.land === 'hatch')
    L.push({
      id: 'land',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landuse',
      filter: landF,
      paint: { 'fill-pattern': 'hatch-land', 'fill-opacity': 0.85 }
    })
  if (v.land === 'dot')
    L.push({
      id: 'land',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landuse',
      filter: landF,
      paint: { 'fill-pattern': 'dot-land', 'fill-opacity': 0.9 }
    })

  L.push({
    id: 'park',
    type: 'fill',
    source: 'openmaptiles',
    'source-layer': 'park',
    paint: {
      'fill-color': v.wood === 'tint' ? faint(T, 0.9) : faint(T, 0.94),
      'fill-opacity': 0.6
    }
  })

  if (v.water === 'hatch') {
    L.push({
      id: 'water',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'fill-pattern': 'hatch-water' }
    })
    L.push({
      id: 'water-line',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'line-color': INK, 'line-width': 0.7 }
    })
  } else if (v.water === 'tint') {
    L.push({
      id: 'water',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'fill-color': faint(T, 0.9) }
    })
    L.push({
      id: 'water-line',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'line-color': INK, 'line-width': 0.6 }
    })
  } else {
    L.push({
      id: 'water-line',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'line-color': INK, 'line-width': 0.6 }
    })
  }
  L.push({
    id: 'waterway',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'waterway',
    paint: { 'line-color': INK, 'line-width': 0.6 }
  })

  const W = 0.6
  L.push({
    id: 'rd-minor',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    filter: ['in', 'class', 'minor', 'service'],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': INK, 'line-width': W }
  })
  L.push({
    id: 'rd-sec',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    filter: ['in', 'class', 'secondary', 'tertiary'],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': INK, 'line-width': W }
  })
  L.push({
    id: 'rd-path',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    filter: ['in', 'class', 'path', 'track', 'pedestrian'],
    minzoom: 14,
    paint: { 'line-color': INK, 'line-width': W, 'line-dasharray': [2, 2] }
  })
  L.push({
    id: 'rd-major',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    filter: ['in', 'class', 'motorway', 'trunk', 'primary'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': INK, 'line-width': W }
  })
  L.push({
    id: 'rail',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    filter: ['==', 'class', 'rail'],
    minzoom: 13,
    paint: { 'line-color': INK, 'line-width': W, 'line-dasharray': [3, 2] }
  })

  const bldFill: Record<string, Record<string, unknown>> = {
    hatch: { 'fill-pattern': 'hatch-bld', 'fill-opacity': fade },
    cross: { 'fill-pattern': 'cross-bld', 'fill-opacity': fade },
    dot: { 'fill-pattern': 'dot-bld', 'fill-opacity': fade },
    solid: { 'fill-color': faint(T, 0.85), 'fill-opacity': fade },
    ink: { 'fill-color': INK, 'fill-opacity': fade }
  }
  if (bldFill[v.bld])
    L.push({
      id: 'bld-fill',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 13,
      paint: bldFill[v.bld]
    })
  L.push({
    id: 'bld-line',
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'building',
    minzoom: 13,
    paint: { 'line-color': INK, 'line-width': 0.7, 'line-opacity': fade }
  })

  L.push({
    id: 'rd-label',
    type: 'symbol',
    source: 'openmaptiles',
    'source-layer': 'transportation_name',
    minzoom: 14,
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'name'],
      'text-font': ['Noto Sans Regular'],
      'text-size': 10,
      'text-letter-spacing': 0.02
    },
    paint: { 'text-color': INK, 'text-halo-color': PAPER, 'text-halo-width': 1.4 }
  })
  L.push({
    id: 'place-label',
    type: 'symbol',
    source: 'openmaptiles',
    'source-layer': 'place',
    filter: ['in', 'class', 'suburb', 'neighbourhood', 'quarter', 'town', 'village'],
    layout: {
      'text-field': ['get', 'name'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11,
      'text-letter-spacing': 0.08,
      'text-transform': 'uppercase'
    },
    paint: { 'text-color': INK, 'text-halo-color': PAPER, 'text-halo-width': 1.6 }
  })

  return {
    version: 8,
    glyphs: FONTS,
    sources: { openmaptiles: { ...SRC } },
    layers: L
  } as StyleSpecification
  /* eslint-enable @typescript-eslint/no-explicit-any */
}

// ---------- tilejson fetch (memoised) ----------
let tilesPromise: Promise<void> | null = null

/** Resolve the OpenFreeMap tile URLs once, before the first buildStyle(). */
export function loadTiles(): Promise<void> {
  if (tilesPromise) return tilesPromise
  tilesPromise = fetch('https://tiles.openfreemap.org/planet')
    .then((r) => r.json())
    .then((j) => {
      SRC.tiles = j.tiles
      SRC.maxzoom = j.maxzoom || 14
    })
    .catch(() => {
      SRC.tiles = ['https://tiles.openfreemap.org/planet/{z}/{x}/{y}.pbf']
    })
  return tilesPromise
}
