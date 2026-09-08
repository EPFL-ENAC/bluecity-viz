/**
 * How dense the road network is under the circle, without asking the server.
 *
 * The backend writes one small file with the node and edge counts of every
 * grid cell of the country (about 15 kB, see graph_store.py). The picker sums
 * the cells the circle touches and tells the user right away whether the tool
 * can run there. The exact answer, connectivity included, still comes from
 * POST /areas/preview when the drag stops.
 */

import { baseUrl } from '@/config/layerTypes'
import { useApiKeyStore } from '@/stores/apiKey'

const isDev = import.meta.env.DEV

/** The grid the backend cut the country in. Plain lon/lat, no projection. */
export interface DensityGrid {
  lon0: number
  lat0: number
  dlon: number
  dlat: number
  ncols: number
  nrows: number
}

export interface Density {
  format_version: number
  grid: DensityGrid
  coverage_bbox: [number, number, number, number] | null
  /** junctions (3 streets or more) per cell, row-major */
  nodes_sc3: number[]
  /** streets per cell, row-major */
  edges: number[]
}

export interface DensityEstimate {
  /** junctions under the circle, the number the min rule reads */
  junctions: number
  /** streets under the circle, the number the max rule reads */
  edges: number
}

const M_PER_DEG_LAT = 111320

export function mPerDegLon(lat: number): number {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180)
}

function densityUrl(): string {
  const url = `${baseUrl}/swiss_graph_density.json`
  if (isDev) return url
  return `${url}?apikey=${useApiKeyStore().apiKey}`
}

let cached: Promise<Density | null> | null = null

/**
 * The file, fetched once per session. null when the deployment has no Swiss
 * network, and then the picker falls back to the server preview alone.
 */
export function loadDensity(): Promise<Density | null> {
  if (!cached) {
    cached = fetch(densityUrl())
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null)
      .then((data: Density | null) => {
        if (!data || !Array.isArray(data.nodes_sc3)) return null
        return data
      })
  }
  return cached
}

/** Tests only. */
export function resetDensity(): void {
  cached = null
}

/**
 * How much of one cell the circle covers, between 0 and 1.
 *
 * A 4 by 4 sub-sample: the cells are 5 km and the circle a few km, so a cell
 * is rarely all in or all out, and counting it whole would be far too
 * generous on the border.
 */
function coverage(
  lon: number,
  lat: number,
  radiusM: number,
  minLon: number,
  minLat: number,
  dlon: number,
  dlat: number
): number {
  const perLon = mPerDegLon(lat)
  const r2 = radiusM * radiusM
  const steps = 4
  let inside = 0
  for (let i = 0; i < steps; i++) {
    const sampleLat = minLat + ((i + 0.5) / steps) * dlat
    const dy = (sampleLat - lat) * M_PER_DEG_LAT
    for (let j = 0; j < steps; j++) {
      const sampleLon = minLon + ((j + 0.5) / steps) * dlon
      const dx = (sampleLon - lon) * perLon
      if (dx * dx + dy * dy <= r2) inside++
    }
  }
  return inside / (steps * steps)
}

/** An estimate of what a circle holds. Rounded, it is shown as a number. */
export function estimateCircle(
  density: Density,
  lon: number,
  lat: number,
  radiusM: number
): DensityEstimate {
  const { grid } = density
  const dLatDeg = radiusM / M_PER_DEG_LAT
  const dLonDeg = radiusM / Math.max(mPerDegLon(lat), 1)

  const col0 = Math.max(0, Math.floor((lon - dLonDeg - grid.lon0) / grid.dlon))
  const col1 = Math.min(grid.ncols - 1, Math.floor((lon + dLonDeg - grid.lon0) / grid.dlon))
  const row0 = Math.max(0, Math.floor((lat - dLatDeg - grid.lat0) / grid.dlat))
  const row1 = Math.min(grid.nrows - 1, Math.floor((lat + dLatDeg - grid.lat0) / grid.dlat))

  let junctions = 0
  let edges = 0
  for (let row = row0; row <= row1; row++) {
    for (let col = col0; col <= col1; col++) {
      const cell = row * grid.ncols + col
      const cellJunctions = density.nodes_sc3[cell] ?? 0
      const cellEdges = density.edges[cell] ?? 0
      if (cellJunctions === 0 && cellEdges === 0) continue

      const share = coverage(
        lon,
        lat,
        radiusM,
        grid.lon0 + col * grid.dlon,
        grid.lat0 + row * grid.dlat,
        grid.dlon,
        grid.dlat
      )
      junctions += cellJunctions * share
      edges += cellEdges * share
    }
  }
  return { junctions: Math.round(junctions), edges: Math.round(edges) }
}

/** Is the point inside the part of the country the store covers. */
export function insideCoverage(
  bbox: [number, number, number, number] | null,
  lon: number,
  lat: number
): boolean {
  if (!bbox) return true
  return lon >= bbox[0] && lon <= bbox[2] && lat >= bbox[1] && lat <= bbox[3]
}
