const isDev = import.meta.env.DEV

const API_BASE_URL = isDev ? 'http://localhost:8000/api/v1/cvrp' : '/api/v1/cvrp'

export interface CVRPRequest {
  waste_type: string
  n_vehicles: number
  vehicle_capacity: number
  max_runtime: number
  waste_per_centroid: number
  load_unit: string
  edge_modifications: Array<{ u: number; v: number; action: string; speed_kph?: number }>
}

export interface CVRPRouteSegment {
  route_id: number
  trip_id: number
  path_coordinates: [number, number][]
  load_kg: number
}

export interface CVRPEdgeLoad {
  u: number
  v: number
  load: number
}

export interface CVRPSolveResponse {
  n_routes: number
  n_missing_clients: number
  total_distance_m: number
  route_segments: CVRPRouteSegment[]
  edge_loads: CVRPEdgeLoad[]
  load_unit: string
  solve_time_ms: number
  centroids_used: number
}

export async function solveCVRP(req: CVRPRequest): Promise<CVRPSolveResponse> {
  const response = await fetch(`${API_BASE_URL}/solve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req)
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail ?? 'CVRP solve failed')
  }
  return response.json()
}

export async function fetchCVRPCentroids(wasteType: string): Promise<GeoJSON.FeatureCollection> {
  const response = await fetch(`${API_BASE_URL}/centroids?waste_type=${wasteType}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch centroids for ${wasteType}`)
  }
  return response.json()
}
