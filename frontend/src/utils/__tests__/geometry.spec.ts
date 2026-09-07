import {
  computeOffsetPath,
  createHullOutline,
  createHullPaths,
  getPathMidpoint
} from '@/utils/geometry'
import { describe, expect, it } from 'vitest'

describe('getPathMidpoint', () => {
  it('takes the middle of a straight segment', () => {
    expect(getPathMidpoint([[0, 0], [10, 0]])).toEqual([5, 0])
  })

  it('measures along the path, not between the ends', () => {
    // an L: 10 east then 10 north, so the middle is the corner
    expect(getPathMidpoint([[0, 0], [10, 0], [10, 10]])).toEqual([10, 0])
  })

  it('handles a path with one point or none', () => {
    expect(getPathMidpoint([[3, 4]])).toEqual([3, 4])
    expect(getPathMidpoint([])).toEqual([0, 0])
  })

  it('does not divide by zero on repeated points', () => {
    expect(getPathMidpoint([[1, 1], [1, 1], [1, 1]])).toEqual([1, 1])
  })
})

describe('computeOffsetPath', () => {
  it('moves a west to east line in latitude only', () => {
    const out = computeOffsetPath([[6, 46], [7, 46]], 111)
    expect(out).toHaveLength(2)
    for (const point of out) {
      expect(point[1]).toBeCloseTo(46.001, 6)
    }
    expect(out[0][0]).toBeCloseTo(6, 10)
    expect(out[1][0]).toBeCloseTo(7, 10)
  })

  it('moves a south to north line in longitude only', () => {
    const out = computeOffsetPath([[6, 46], [6, 47]], 77)
    for (const point of out) {
      expect(point[0]).toBeCloseTo(5.999, 6)
    }
    expect(out[0][1]).toBeCloseTo(46, 10)
  })

  it('offsets the other way with a negative distance', () => {
    const [a] = computeOffsetPath([[6, 46], [7, 46]], -111)
    expect(a[1]).toBeCloseTo(45.999, 6)
  })

  it('leaves a path shorter than two points alone', () => {
    const one = [[1, 2]]
    expect(computeOffsetPath(one, 50)).toBe(one)
    expect(computeOffsetPath([], 50)).toEqual([])
  })
})

describe('createHullPaths', () => {
  it('puts the two sides the same distance either side', () => {
    const line = [[6, 46], [7, 46]]
    const [left, right] = createHullPaths(line, 222)
    expect(left[0][1] - 46).toBeCloseTo(-(right[0][1] - 46), 12)
    expect(left[0][1]).toBeCloseTo(46.001, 6)
  })
})

describe('createHullOutline', () => {
  it('closes both ends and gives the midpoint', () => {
    const line = [[6, 46], [7, 46]]
    const hull = createHullOutline(line, 222)

    expect(hull.left).toHaveLength(2)
    expect(hull.right).toHaveLength(2)
    expect(hull.startCap).toEqual([hull.left[0], hull.right[0]])
    expect(hull.endCap).toEqual([hull.left[1], hull.right[1]])
    expect(hull.midpoint[0]).toBeCloseTo(6.5, 10)
  })

  it('gives the same sides as createHullPaths', () => {
    const line = [[6, 46], [6.5, 46.2], [7, 46]]
    const [left, right] = createHullPaths(line, 8)
    const hull = createHullOutline(line, 8)
    expect(hull.left).toEqual(left)
    expect(hull.right).toEqual(right)
  })

  it('skips the caps on a degenerate path', () => {
    const hull = createHullOutline([[1, 2]], 8)
    expect(hull.startCap).toEqual([])
    expect(hull.endCap).toEqual([])
    expect(hull.midpoint).toEqual([1, 2])
  })
})
