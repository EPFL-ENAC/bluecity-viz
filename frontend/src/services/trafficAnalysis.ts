import { baseUrl } from '@/config/layerTypes'
import { useApiKeyStore } from '@/stores/apiKey'
import type { EdgeUsageStats, NodePair } from '@/stores/trafficAnalysis'

const isDev = import.meta.env.DEV

const API_BASE_URL = isDev ? 'http://localhost:8000/api/v1/routes' : '/api/v1/routes'

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
}

/**
 * Fetch edge geometries from pre-generated GeoJSON file
 */
export async function fetchEdgeGeometries(limit?: number): Promise<EdgeGeometry[]> {
  try {
    console.time('[Frontend] Total fetch time')

    console.time('[Frontend] Network request')
    const response = await fetch(getGeojsonUrl())
    console.timeEnd('[Frontend] Network request')

    if (!response.ok) {
      console.warn('GeoJSON file not available, using empty dataset')
      return []
    }

    // Check response size
    const contentLength = response.headers.get('content-length')
    const contentEncoding = response.headers.get('content-encoding')
    console.log(
      `[Frontend] Response size: ${
        contentLength ? (parseInt(contentLength) / 1024).toFixed(2) + ' KB' : 'unknown'
      }${contentEncoding ? ` (${contentEncoding})` : ''}`
    )

    console.time('[Frontend] JSON parsing')
    const geojson = await response.json()
    console.timeEnd('[Frontend] JSON parsing')

    // Convert GeoJSON features to EdgeGeometry format
    console.time('[Frontend] GeoJSON conversion')
    const edges: EdgeGeometry[] = geojson.features.map((feature: any) => ({
      u: feature.properties.u,
      v: feature.properties.v,
      coordinates: feature.geometry.coordinates,
      travel_time: feature.properties.travel_time,
      length: feature.properties.length,
      name: feature.properties.name,
      highway: feature.properties.highway
    }))

    if (limit) {
      edges.splice(limit)
    }
    console.timeEnd('[Frontend] GeoJSON conversion')

    console.timeEnd('[Frontend] Total fetch time')
    console.log(`[Frontend] Loaded ${edges.length} edges from GeoJSON`)

    return edges
  } catch (error) {
    console.warn('Failed to fetch edge geometries:', error)
    return []
  }
}

export async function generateRandomPairs(
  count: number = 500,
  seed?: number,
  radiusKm: number = 1
): Promise<NodePair[]> {
  const response = await fetch(`${API_BASE_URL}/random-pairs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ count, seed, radius_km: radiusKm })
  })
  if (!response.ok) {
    throw new Error('Failed to generate random pairs')
  }
  return response.json()
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

export async function recalculateRoutes(
  pairs: NodePair[],
  edgesToRemove: { u: number; v: number }[]
): Promise<{
  removed_edges: { u: number; v: number }[]
  original_edge_usage: EdgeUsageStats[]
  new_edge_usage: EdgeUsageStats[]
  impact_statistics: ImpactStatistics
}> {
  const response = await fetch(`${API_BASE_URL}/recalculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      pairs,
      edges_to_remove: edgesToRemove,
      weight: 'travel_time',
      include_geometry: false
    })
  })
  if (!response.ok) {
    throw new Error('Failed to recalculate routes')
  }
  return response.json()
}
