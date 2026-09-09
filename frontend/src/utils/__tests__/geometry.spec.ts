import {
  type Pt,
  bbox,
  convexHull,
  pointInPolygon,
  pointToSegmentDistance,
  polylineIntersectsPolygon,
  polylineNearSegment,
  segmentsDistance,
  segmentsIntersect
} from '@/utils/geometry'
import { describe, expect, it } from 'vitest'

const SQUARE: Pt[] = [
  [0, 0],
  [10, 0],
  [10, 10],
  [0, 10]
]

// a C shape: the notch on the right is outside
const NOTCHED: Pt[] = [
  [0, 0],
  [10, 0],
  [10, 4],
  [4, 4],
  [4, 6],
  [10, 6],
  [10, 10],
  [0, 10]
]

describe('bbox', () => {
  it('holds every point', () => {
    expect(
      bbox([
        [2, 5],
        [8, 1]
      ])
    ).toEqual([
      [2, 1],
      [8, 5]
    ])
  })

  it('grows by the padding', () => {
    expect(bbox([[5, 5]], 3)).toEqual([
      [2, 2],
      [8, 8]
    ])
  })
})

describe('pointInPolygon', () => {
  it('says yes inside and no outside', () => {
    expect(pointInPolygon([5, 5], SQUARE)).toBe(true)
    expect(pointInPolygon([15, 5], SQUARE)).toBe(false)
    expect(pointInPolygon([5, -1], SQUARE)).toBe(false)
  })

  it('leaves the notch of a concave shape out', () => {
    expect(pointInPolygon([2, 5], NOTCHED)).toBe(true)
    expect(pointInPolygon([7, 5], NOTCHED)).toBe(false)
  })

  it('needs three points to be a shape', () => {
    expect(
      pointInPolygon(
        [0, 0],
        [
          [0, 0],
          [1, 1]
        ]
      )
    ).toBe(false)
  })
})

describe('segmentsIntersect', () => {
  it('sees a crossing', () => {
    expect(segmentsIntersect([0, 0], [10, 10], [0, 10], [10, 0])).toBe(true)
  })

  it('sees a T, where one end lands on the other segment', () => {
    expect(segmentsIntersect([0, 0], [10, 0], [5, 0], [5, 5])).toBe(true)
  })

  it('says no for parallel segments', () => {
    expect(segmentsIntersect([0, 0], [10, 0], [0, 2], [10, 2])).toBe(false)
  })

  it('sees segments that lie on each other', () => {
    expect(segmentsIntersect([0, 0], [10, 0], [5, 0], [15, 0])).toBe(true)
  })

  it('says no when they are apart', () => {
    expect(segmentsIntersect([0, 0], [1, 1], [5, 5], [6, 6])).toBe(false)
  })
})

describe('polylineIntersectsPolygon', () => {
  it('catches a street with a point inside', () => {
    expect(
      polylineIntersectsPolygon(
        [
          [5, 5],
          [50, 50]
        ],
        SQUARE
      )
    ).toBe(true)
  })

  it('catches a street that only passes through', () => {
    // both ends are outside, the middle crosses the square
    expect(
      polylineIntersectsPolygon(
        [
          [-5, 5],
          [15, 5]
        ],
        SQUARE
      )
    ).toBe(true)
  })

  it('leaves a street that stays outside', () => {
    expect(
      polylineIntersectsPolygon(
        [
          [20, 20],
          [30, 30]
        ],
        SQUARE
      )
    ).toBe(false)
  })

  it('leaves a street crossing the notch of a concave shape', () => {
    expect(
      polylineIntersectsPolygon(
        [
          [5, 5],
          [9, 5]
        ],
        NOTCHED
      )
    ).toBe(false)
  })

  it('says no for an empty line', () => {
    expect(polylineIntersectsPolygon([], SQUARE)).toBe(false)
  })
})

describe('pointToSegmentDistance', () => {
  it('drops a perpendicular when the foot is on the segment', () => {
    expect(pointToSegmentDistance([5, 3], [0, 0], [10, 0])).toBe(3)
  })

  it('takes the nearest end when the foot is past it', () => {
    expect(pointToSegmentDistance([13, 4], [0, 0], [10, 0])).toBe(5)
  })

  it('handles a segment of no length', () => {
    expect(pointToSegmentDistance([3, 4], [0, 0], [0, 0])).toBe(5)
  })
})

describe('segmentsDistance', () => {
  it('is zero when they cross', () => {
    expect(segmentsDistance([0, 0], [10, 10], [0, 10], [10, 0])).toBe(0)
  })

  it('is the gap between parallel segments', () => {
    expect(segmentsDistance([0, 0], [10, 0], [0, 4], [10, 4])).toBe(4)
  })
})

describe('polylineNearSegment', () => {
  it('catches a street under the brush', () => {
    const street: Pt[] = [
      [5, 12],
      [15, 12]
    ]
    expect(polylineNearSegment(street, [10, 0], [10, 10], 3)).toBe(true)
  })

  it('leaves a street the brush did not reach', () => {
    const street: Pt[] = [
      [5, 30],
      [15, 30]
    ]
    expect(polylineNearSegment(street, [10, 0], [10, 10], 3)).toBe(false)
  })

  it('catches a street between two samples of a fast stroke', () => {
    // the brush jumps from x=0 to x=100, the street sits in the middle
    const street: Pt[] = [
      [50, -20],
      [50, 20]
    ]
    expect(polylineNearSegment(street, [0, 0], [100, 0], 4)).toBe(true)
    // the same street is far from either end on its own
    expect(pointToSegmentDistance([50, -20], [0, 0], [0, 0])).toBeGreaterThan(4)
  })

  it('takes a single point line', () => {
    expect(polylineNearSegment([[10, 2]], [0, 0], [20, 0], 3)).toBe(true)
    expect(polylineNearSegment([], [0, 0], [20, 0], 3)).toBe(false)
  })
})

describe('convexHull', () => {
  it('drops the point inside the square', () => {
    const hull = convexHull([
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [5, 5]
    ])
    expect(hull).toHaveLength(4)
    expect(hull).not.toContainEqual([5, 5])
  })

  it('gives back the two ends of a flat line', () => {
    expect(
      convexHull([
        [0, 0],
        [5, 0],
        [10, 0]
      ])
    ).toHaveLength(2)
  })

  it('folds the duplicates', () => {
    expect(
      convexHull([
        [1, 1],
        [1, 1],
        [1, 1]
      ])
    ).toEqual([[1, 1]])
  })
})
