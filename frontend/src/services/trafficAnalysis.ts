import { baseUrl } from '@/config/layerTypes'
import { useApiKeyStore } from '@/stores/apiKey'
import type { EdgeUsageStats } from '@/stores/trafficAnalysis'

const isDev = import.meta.env.DEV

// Relative in dev too: vite proxies /api to this checkout's own backend, whose
// port changes per git worktree (wtx writes the ports in .env.worktree).
const API_BASE_URL = '/api/v1/routes'
const AREAS_BASE_URL = '/api/v1/areas'

/** The default area: the city the server loaded at startup. */
export const DEFAULT_AREA_ID = 'lausanne'

/** `null` means the default area, so the query stays out of the URL. */
function areaQuery(areaId?: string | null, separator = '?'): string {
  return areaId ? `${separator}area_id=${encodeURIComponent(areaId)}` : ''
}

function getGeojsonUrl(): string {
  const url = `${baseUrl}/lausanne.geojson`
  if (!isDev) {
    const apiKeyStore = useApiKeyStore()
    return `${url}?apikey=${apiKeyStore.apiKey}`
  }
  return url
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
 * Fetch edge geometries from pre-generated GeoJSON file
 */
export async function fetchEdgeGeometries(limit?: number): Promise<EdgeGeometry[]> {
  try {
    const response = await fetch(getGeojsonUrl())

    if (!response.ok) {
      console.warn('GeoJSON file not available, using empty dataset')
      return []
    }

    const geojson = await response.json()

    // Convert GeoJSON features to EdgeGeometry format
    const edges: EdgeGeometry[] = geojson.features.map((feature: any) => ({
      u: feature.properties.u,
      v: feature.properties.v,
      coordinates: feature.geometry.coordinates,
      travel_time: feature.properties.travel_time,
      length: feature.properties.length,
      name: feature.properties.name,
      highway: feature.properties.highway,
      speed_kph: feature.properties.speed_kph,
      bus_route_count: feature.properties.bus_route_count ?? 0,
      bus_route_refs: feature.properties.bus_route_refs ?? ''
    }))

    if (limit) {
      edges.splice(limit)
    }

    return edges
  } catch (error) {
    console.warn('Failed to fetch edge geometries:', error)
    return []
  }
}

export interface ImpactStatistics {
  total_routes: number
  affected_routes: number
  failed_routes: number
  total_distance_increase_km: number
  total_time_increase_minutes: number
  avg_distance_increase_km: number
  avg_time_increase_minutes: number
  max_distance_increase_km: number
  max_time_increase_minutes: number
  avg_distance_increase_percent: number
  avg_time_increase_percent: number
}

export interface EdgeModification {
  u: number
  v: number
  action: 'remove' | 'modify'
  speed_kph?: number
}

export interface TimingStats {
  cache_lookup_ms: number
  graph_copy_ms: number
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
 * Edge usage of the unmodified network. It never changes while the server
 * runs, so it is served with an ETag: a plain fetch does the conditional
 * request by itself and gets a 304 on the second load.
 */
export async function fetchBaseline(
  odPairs?: number,
  areaId?: string | null
): Promise<BaselineResponse> {
  const pairs = odPairs === undefined || odPairs === null ? '' : `?od_pairs=${odPairs}`
  const url = `${API_BASE_URL}/baseline${pairs}${areaQuery(areaId, pairs ? '&' : '?')}`

  const response = await fetch(url)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch baseline')
  return response.json()
}

export async function recalculateRoutes(
  edgeModifications: EdgeModification[],
  options?: {
    useCongestionModel?: boolean
    congestionIterations?: number
    elasticDemand?: boolean
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
      weight: 'travel_time',
      include_geometry: true,
      use_congestion: options?.useCongestionModel ?? false,
      congestion_iterations: options?.congestionIterations ?? 1,
      resample_destinations: options?.elasticDemand ?? false,
      od_pairs: options?.odPairs ?? null,
      // the baseline is the same for every run, we fetch it once from
      // GET /baseline instead of carrying it in every answer
      include_baseline: false
    })
  })
  if (!response.ok) await throwHttpError(response, 'Failed to recalculate routes')
  return response.json()
}

// ── Areas ────────────────────────────────────────────────────────────────────

/** A circle the user drew. This is what an investigation saves. */
export interface AreaSelection {
  kind: 'circle'
  lon: number
  lat: number
  radiusM: number
  /** The place the circle is on, for the dock. Never sent to the server. */
  name?: string
}

/** An area the server has in memory and can route on. */
export interface AreaInfo {
  id: string
  circle: { lon: number; lat: number; radius_m: number }
  bbox: [number, number, number, number] | null
  node_count: number
  edge_count: number
  scc_fraction: number
  od_pairs: number
  od_pairs_default: number
  od_pairs_max: number
}

export type AreaRejectionCode = 'too_sparse' | 'too_large' | 'disconnected' | 'outside_coverage'

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
}

function areaBody(area: AreaSelection): string {
  return JSON.stringify({
    circle: { lon: area.lon, lat: area.lat, radius_m: area.radiusM }
  })
}

/**
 * The id the server gives this circle. It is derived from the geometry, so we
 * can ask for an area by its shape without keeping a server id around.
 */
export function areaKey(area: AreaSelection | null): string {
  if (!area) return DEFAULT_AREA_ID
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

/** Build the routing graph of a circle. Takes a few seconds the first time. */
export async function createArea(area: AreaSelection): Promise<AreaInfo> {
  const response = await fetch(AREAS_BASE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: areaBody(area)
  })
  if (!response.ok) await throwHttpError(response, 'Failed to create the area')
  return response.json()
}

/** The streets of an area, same shape as the static city file. */
export async function fetchAreaEdges(areaId: string): Promise<EdgeGeometry[]> {
  const response = await fetch(`${AREAS_BASE_URL}/${encodeURIComponent(areaId)}/edges`)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch the area streets')
  return response.json()
}
