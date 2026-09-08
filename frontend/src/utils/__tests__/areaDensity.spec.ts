import { estimateCircle, insideCoverage, mPerDegLon, type Density } from '@/utils/areaDensity'
import { describe, expect, it } from 'vitest'

// A 3 by 3 grid of one-degree cells starting at (0, 0), so the arithmetic in
// the test is easy to follow. The middle cell is the dense one.
function grid(nodes: number[], edges: number[]): Density {
  return {
    format_version: 1,
    grid: { lon0: 0, lat0: 0, dlon: 1, dlat: 1, ncols: 3, nrows: 3 },
    coverage_bbox: [0, 0, 3, 3],
    nodes_sc3: nodes,
    edges
  }
}

const ONLY_MIDDLE = grid([0, 0, 0, 0, 900, 0, 0, 0, 0], [0, 0, 0, 0, 1800, 0, 0, 0, 0])

describe('areaDensity', () => {
  it('counts a cell in full when the circle covers it', () => {
    // 1 degree of latitude is about 111 km, so 200 km covers the whole grid
    const all = estimateCircle(ONLY_MIDDLE, 1.5, 1.5, 200_000)
    expect(all.junctions).toBe(900)
    expect(all.edges).toBe(1800)
  })

  it('counts nothing far from any cell with streets', () => {
    const none = estimateCircle(ONLY_MIDDLE, 0.5, 0.5, 10_000)
    expect(none.junctions).toBe(0)
    expect(none.edges).toBe(0)
  })

  it('counts a share of the cell on the border', () => {
    // a small circle on the corner of the dense cell takes a quarter of it
    const corner = estimateCircle(ONLY_MIDDLE, 1, 1, 60_000)
    expect(corner.junctions).toBeGreaterThan(100)
    expect(corner.junctions).toBeLessThan(500)
  })

  it('adds up the cells the circle touches', () => {
    const spread = grid([100, 100, 100, 100, 100, 100, 100, 100, 100], new Array(9).fill(200))
    const all = estimateCircle(spread, 1.5, 1.5, 300_000)
    expect(all.junctions).toBe(900)
    expect(all.edges).toBe(1800)
  })

  it('shrinks a degree of longitude as it goes north', () => {
    expect(mPerDegLon(0)).toBeCloseTo(111320, 0)
    expect(mPerDegLon(47)).toBeLessThan(80_000)
    expect(mPerDegLon(47)).toBeGreaterThan(75_000)
  })

  it('knows what the store covers', () => {
    expect(insideCoverage([5.9, 45.8, 10.6, 47.9], 7.44, 46.95)).toBe(true)
    expect(insideCoverage([5.9, 45.8, 10.6, 47.9], 2.35, 48.85)).toBe(false)
    // half over the border still touches it, and the server accepts that
    expect(insideCoverage([5.9, 45.8, 10.6, 47.9], 5.88, 46.5, 3000)).toBe(true)
    // no bbox yet: do not block the user on a rule we have not read
    expect(insideCoverage(null, 2.35, 48.85)).toBe(true)
  })
})
