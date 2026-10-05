import type { EdgeUsageStats } from '@/stores/trafficAnalysis'

// Relative in dev too: vite proxies /api to this checkout's own backend, whose
// port changes per git worktree (wtx writes the ports in .env.worktree).
const API_BASE_URL = '/api/v1/routes'
const AREAS_BASE_URL = '/api/v1/areas'

/** `null` means the default area, so the query stays out of the URL. */
function areaQuery(areaId?: string | null, separator = '?'): string {
  return areaId ? `${separator}area_id=${encodeURIComponent(areaId)}` : ''
}

export interface EdgeGeometry {
  u: number
  v: number
  coordinates: [number, number][]
  travel_time?: number
  length?: number
  name?: string
  highway?: string
  /** the posted speed, shown in the hover card and the edit popover */
  speed_kph?: number
  bus_route_count?: number
  bus_route_refs?: string
}

/**
 * What the scenario did to the trips. Every `change` is new minus old over
 * the affected trips, so a scenario that shortens trips reads negative; every
 * `increase` is the worst single trip, 0 when nothing got worse.
 */
export interface ImpactStatistics {
  total_routes: number
  affected_routes: number
  failed_routes: number
  total_distance_change_km: number
  total_time_change_minutes: number
  total_co2_change_grams: number
  avg_distance_change_km: number
  avg_time_change_minutes: number
  avg_co2_change_grams: number
  avg_distance_change_percent: number
  avg_time_change_percent: number
  avg_co2_change_percent: number
  max_distance_increase_km: number
  max_time_increase_minutes: number
  max_co2_increase_grams: number
}

export interface EdgeModification {
  u: number
  v: number
  action: 'remove' | 'modify'
  speed_kph?: number
}

export interface TimingStats {
  cache_lookup_ms: number
  apply_modifications_ms: number
  od_resampling_ms?: number
  affected_routes_ms?: number
  route_calculation_ms: number
  impact_stats_ms: number
  edge_usage_stats_ms: number
  total_ms: number
}

/** Graph and OD pair counts, from GET /graph-info. */
export interface GraphInfo {
  /** which area these numbers describe */
  area_id: string
  bbox: [number, number, number, number] | null
  /** share of the nodes in the main network, 1 when it is all one piece */
  scc_fraction: number
  node_count: number
  edge_count: number
  /** pairs really sampled at startup */
  od_pairs: number
  /** the count the server uses when the request says nothing */
  od_pairs_default: number
  /** the most the server accepts */
  od_pairs_max: number
}

export interface BaselineResponse {
  total_routes: number
  /** the count really used, the server clamps what we ask for */
  od_pairs: number
  edge_usage: EdgeUsageStats[]
}

export interface RecalculateResponse {
  od_pairs: number
  applied_modifications: EdgeModification[]
  /** only sent when include_baseline is true, we ask for false */
  original_edge_usage?: EdgeUsageStats[]
  new_edge_usage: EdgeUsageStats[]
  impact_statistics: ImpactStatistics
  timing: TimingStats
}

/** An error the server explained, with the code the UI reacts to. */
export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/**
 * Read the error out of a failed response. FastAPI sends `detail` as a string
 * for our own HTTPException, as a list of {msg} when pydantic rejects a field
 * (od_pairs above the max, for one), and as an object with a code when the
 * UI has to react (an area that is not loaded any more).
 */
async function throwHttpError(response: Response, what: string): Promise<never> {
  let detail: unknown = null
  try {
    detail = (await response.json())?.detail
  } catch {
    // no body, or not json
  }

  let message: string
  let code: string | undefined
  if (typeof detail === 'string') {
    message = detail
  } else if (Array.isArray(detail)) {
    message = detail
      .map((item: { msg?: string }) => item?.msg)
      .filter(Boolean)
      .join('; ')
  } else if (detail && typeof detail === 'object') {
    const object = detail as { code?: string; message?: string }
    code = object.code
    message = object.message ?? response.statusText
  } else {
    message = response.statusText
  }

  throw new ApiError(`${what}: ${message || response.status}`, response.status, code)
}

export async function fetchGraphInfo(areaId?: string | null): Promise<GraphInfo> {
  const response = await fetch(`${API_BASE_URL}/graph-info${areaQuery(areaId)}`)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch graph info')
  return response.json()
}

/**
 * The Model state: edge usage of the unmodified network under one model. It
 * is what the Model step draws and the left side of every run with the same
 * options. It never changes while the server runs, so it is served with an
 * ETag: a plain fetch does the conditional request by itself and gets a 304
 * on the second load.
 *
 * `congestionIterations` asks for the equilibrium model (null is the targeted
 * one). The equilibrium one costs an MSA run on the server the first time.
 * Elastic demand is not a parameter: on the untouched network it draws the
 * same trips.
 */
export async function fetchBaseline(
  odPairs?: number,
  areaId?: string | null,
  nodeWeighting: NodeWeighting = 'uniform',
  congestionIterations: number | null = null
): Promise<BaselineResponse> {
  const params = new URLSearchParams()
  if (odPairs !== undefined && odPairs !== null) params.set('od_pairs', String(odPairs))
  if (areaId) params.set('area_id', areaId)
  // uniform and free flow are the server defaults, left out so the URL stays
  // the one the browser cache already knows
  if (nodeWeighting !== 'uniform') params.set('node_weighting', nodeWeighting)
  if (congestionIterations !== null) {
    params.set('use_congestion', 'true')
    params.set('congestion_iterations', String(congestionIterations))
  }
  const query = params.toString()
  const url = `${API_BASE_URL}/baseline${query ? `?${query}` : ''}`

  const response = await fetch(url)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch baseline')
  return response.json()
}

/**
 * How the OD sampler weighs the nodes: every junction the same, or by the
 * residents and jobs around it (federal statistics, per area percentiles).
 */
export type NodeWeighting = 'uniform' | 'population'

export async function recalculateRoutes(
  edgeModifications: EdgeModification[],
  options?: {
    useCongestionModel?: boolean
    congestionIterations?: number
    elasticDemand?: boolean
    nodeWeighting?: NodeWeighting
    /** how many OD pairs, null for the server default */
    odPairs?: number | null
    /** which area to run on, null for the default one */
    areaId?: string | null
  }
): Promise<RecalculateResponse> {
  const response = await fetch(`${API_BASE_URL}/recalculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      area_id: options?.areaId ?? null,
      edge_modifications: edgeModifications,
      use_congestion: options?.useCongestionModel ?? false,
      congestion_iterations: options?.congestionIterations ?? 1,
      resample_destinations: options?.elasticDemand ?? false,
      node_weighting: options?.nodeWeighting ?? 'uniform',
      od_pairs: options?.odPairs ?? null,
      // The baseline is the Model state, the same for every run with these
      // options: GET /baseline gives it once instead of every answer.
      include_baseline: false
    })
  })
  if (!response.ok) await throwHttpError(response, 'Failed to recalculate routes')
  return response.json()
}

// ── Areas ────────────────────────────────────────────────────────────────────

// The area a scenario runs on, a circle or a set of communes. The one type
// lives with the store, this name is kept for the callers of this module.
import type { TrafficAreaSelection as AreaSelection } from '@/stores/layers/types'
export type { AreaSelection }

/**
 * The area the app opens on: a circle on Lausanne. The server builds the same
 * one at startup and keeps it (default_area_* in config.py), so asking for it
 * costs nothing. If the two ever differ, this is just one more circle.
 */
export const DEFAULT_AREA: Readonly<AreaSelection> = Object.freeze({
  kind: 'circle',
  lon: 6.633,
  lat: 46.52,
  radiusM: 6000,
  name: 'Lausanne'
})

/** Where a set of communes is, as the server gives it. EPSG:4326. */
export type AreaOutline =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

/** An area the server has in memory and can route on. */
export interface AreaInfo {
  id: string
  circle: { lon: number; lat: number; radius_m: number } | null
  // Missing from a server older than the municipalities.
  kind?: 'circle' | 'municipalities'
  name?: string
  municipalities?: { ids: number[]; names: string[] } | null
  outline?: AreaOutline | null
  bbox: [number, number, number, number] | null
  node_count: number
  edge_count: number
  scc_fraction: number
  od_pairs: number
  od_pairs_default: number
  od_pairs_max: number
  /** the waste tool runs here; missing from an older server */
  cvrp?: boolean
}

export type AreaRejectionCode =
  'too_sparse' | 'too_large' | 'disconnected' | 'outside_coverage' | 'not_contiguous'

/** Answer to "can the tool run here", without building anything. */
export interface AreaPreview {
  ok: boolean
  code: AreaRejectionCode | null
  message: string
  node_count: number
  edge_count: number
  junction_count: number
  scc_fraction: number
  bbox: [number, number, number, number] | null
  /** the union of the communes, null for a circle */
  outline?: AreaOutline | null
}

/** The rules the picker checks while the circle is dragged. */
export interface AreaLimits {
  /** junctions, not nodes: a dead end helps nobody route */
  min_junctions: number
  max_nodes: number
  max_edges: number
  min_scc_fraction: number
  min_radius_m: number
  max_radius_m: number
  coverage_bbox: [number, number, number, number] | null
  /** false when the server has no boundaries file, the picker hides the mode */
  has_municipalities?: boolean
  max_municipalities?: number
}

/** Commune ids without repeats, sorted as numbers: the order of the area id. */
export function normaliseIds(ids: readonly number[]): number[] {
  return Array.from(new Set(ids)).sort((a, b) => a - b)
}

/** Same id as the backend: `m_5586_5590`, whatever the click order. */
export function municipalityKey(ids: readonly number[]): string {
  return `m_${normaliseIds(ids).join('_')}`
}

function areaBody(area: AreaSelection): string {
  if (area.kind === 'municipalities') {
    return JSON.stringify({ municipalities: normaliseIds(area.ofsIds) })
  }
  return JSON.stringify({
    circle: { lon: area.lon, lat: area.lat, radius_m: area.radiusM }
  })
}

/**
 * The id the server gives this area. It is derived from the shape, so we can
 * ask for an area by its shape without keeping a server id around.
 */
export function areaKey(area: AreaSelection | null): string {
  // A project saved before the default was a circle has no area.
  if (!area) return areaKey(DEFAULT_AREA)
  if (area.kind === 'municipalities') return municipalityKey(area.ofsIds)
  return `c_${area.lon.toFixed(4)}_${area.lat.toFixed(4)}_${Math.round(area.radiusM)}`
}

export async function fetchAreaLimits(): Promise<AreaLimits> {
  const response = await fetch(`${AREAS_BASE_URL}/limits`)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch the area limits')
  return response.json()
}

/** Exact counts and connectivity for a shape. Builds nothing. */
export async function previewArea(area: AreaSelection): Promise<AreaPreview> {
  const response = await fetch(`${AREAS_BASE_URL}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: areaBody(area)
  })
  if (!response.ok) await throwHttpError(response, 'Failed to check the area')
  return response.json()
}

/** Build the routing graph of an area. Takes a few seconds the first time. */
export async function createArea(area: AreaSelection): Promise<AreaInfo> {
  const response = await fetch(AREAS_BASE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: areaBody(area)
  })
  if (!response.ok) await throwHttpError(response, 'Failed to create the area')
  return response.json()
}

/** The streets of an area. */
export async function fetchAreaEdges(areaId: string): Promise<EdgeGeometry[]> {
  const response = await fetch(`${AREAS_BASE_URL}/${encodeURIComponent(areaId)}/edges`)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch the area streets')
  return response.json()
}
