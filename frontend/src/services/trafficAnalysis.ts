import type { EdgeUsageStats, NodePair } from '@/stores/trafficAnalysis'

const API_BASE_URL = 'http://localhost:8000/api/v1/routes'

export function getGraphTilesUrl(): string {
  return '/geodata/lausanne_drive.pmtiles'
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
