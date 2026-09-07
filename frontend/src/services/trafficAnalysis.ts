import { baseUrl } from '@/config/layerTypes'
import { useApiKeyStore } from '@/stores/apiKey'
import type { EdgeUsageStats } from '@/stores/trafficAnalysis'

const isDev = import.meta.env.DEV

// Relative in dev too: vite proxies /api to this checkout's own backend, whose
// port changes per git worktree (see vite.config.ts and docs/worktree-env/).
const API_BASE_URL = '/api/v1/routes'

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

/**
 * Read the error out of a failed response. FastAPI sends `detail` as a string
 * for our own HTTPException, and as a list of {msg} when pydantic rejects a
 * field (od_pairs above the max, for one).
 */
async function throwHttpError(response: Response, what: string): Promise<never> {
  let detail: unknown = null
  try {
    detail = (await response.json())?.detail
  } catch {
    // no body, or not json
  }

  let message: string
  if (typeof detail === 'string') {
    message = detail
  } else if (Array.isArray(detail)) {
    message = detail
      .map((item: { msg?: string }) => item?.msg)
      .filter(Boolean)
      .join('; ')
  } else {
    message = response.statusText
  }

  throw new Error(`${what}: ${message || response.status}`)
}

export async function fetchGraphInfo(): Promise<GraphInfo> {
  const response = await fetch(`${API_BASE_URL}/graph-info`)
  if (!response.ok) await throwHttpError(response, 'Failed to fetch graph info')
  return response.json()
}

/**
 * Edge usage of the unmodified network. It never changes while the server
 * runs, so it is served with an ETag: a plain fetch does the conditional
 * request by itself and gets a 304 on the second load.
 */
export async function fetchBaseline(odPairs?: number): Promise<BaselineResponse> {
  const url =
    odPairs === undefined || odPairs === null
      ? `${API_BASE_URL}/baseline`
      : `${API_BASE_URL}/baseline?od_pairs=${odPairs}`

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
  }
): Promise<RecalculateResponse> {
  const response = await fetch(`${API_BASE_URL}/recalculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
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
