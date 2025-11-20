import type { EdgeUsageStats, NodePair } from '@/stores/trafficAnalysis'

const API_BASE_URL = 'http://localhost:8000/api/v1/routes'

export interface EdgeGeometry {
  u: number
  v: number
  coordinates: [number, number][]
  travel_time?: number
  length?: number
  name?: string
  highway?: string
}

export function getGraphTilesUrl(): string {
  return '/geodata/lausanne_drive.pmtiles'
}

/**
 * Fetch edge geometries from the backend
 * This endpoint needs to be implemented in the backend to return all edges with coordinates
 */
export async function fetchEdgeGeometries(limit?: number): Promise<EdgeGeometry[]> {
  try {
    const url = limit
      ? `${API_BASE_URL}/edge-geometries?limit=${limit}`
      : `${API_BASE_URL}/edge-geometries`

    const response = await fetch(url)
    if (!response.ok) {
      console.warn('Edge geometries endpoint not available, using empty dataset')
      return []
    }
    return response.json()
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

export async function recalculateRoutes(
  pairs: NodePair[],
  edgesToRemove: { u: number; v: number }[]
): Promise<{
  removed_edges: { u: number; v: number }[]
  original_edge_usage: EdgeUsageStats[]
  new_edge_usage: EdgeUsageStats[]
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
