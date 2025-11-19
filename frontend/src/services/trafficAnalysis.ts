import type { NodePair, RouteComparison } from '@/stores/trafficAnalysis'

const API_BASE_URL = 'http://localhost:8000/api/v1/routes'

export function getGraphTilesUrl(): string {
  return '/geodata/lausanne_drive.pmtiles'
}

export async function generateRandomPairs(count: number = 5, seed?: number): Promise<NodePair[]> {
  const response = await fetch(`${API_BASE_URL}/random-pairs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ count, seed })
  })
  if (!response.ok) {
    throw new Error('Failed to generate random pairs')
  }
  return response.json()
}

export async function recalculateRoutes(
  pairs: NodePair[],
  edgesToRemove: { u: number; v: number }[]
): Promise<{ comparisons: RouteComparison[]; removed_edges: { u: number; v: number }[] }> {
  const response = await fetch(`${API_BASE_URL}/recalculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      pairs,
      edges_to_remove: edgesToRemove,
      weight: 'travel_time',
      include_geometry: true
    })
  })
  if (!response.ok) {
    throw new Error('Failed to recalculate routes')
  }
  return response.json()
}
