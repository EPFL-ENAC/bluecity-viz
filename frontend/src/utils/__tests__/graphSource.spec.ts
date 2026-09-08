import type { EdgeGeometry } from '@/services/trafficAnalysis'
import {
  buildGraphSource,
  classFactor,
  classLabel,
  pathMidpoint,
  pickLane,
  sideOfTravel
} from '@/utils/graphSource'
import { describe, expect, it } from 'vitest'

function edge(u: number, v: number, extra: Partial<EdgeGeometry> = {}): EdgeGeometry {
  return {
    u,
    v,
    coordinates: [
      [0, 0],
      [1, 0]
    ],
    ...extra
  }
}

/** The same street the other way: reversed coordinates, as the data has it. */
function reversed(e: EdgeGeometry): EdgeGeometry {
  return { ...e, u: e.v, v: e.u, coordinates: [...e.coordinates].reverse() }
}

describe('classFactor', () => {
  it('follows the design widths', () => {
    expect(classFactor('motorway')).toBe(1.6)
    expect(classFactor('primary')).toBe(1.6)
    expect(classFactor('secondary')).toBe(1.3)
    expect(classFactor('tertiary')).toBe(1)
    expect(classFactor('busway')).toBe(1)
  })

  it('treats every other road, and a missing one, as minor', () => {
    for (const value of ['residential', 'unclassified', 'living_street', 'service', undefined]) {
      expect(classFactor(value)).toBe(0.7)
    }
  })

  it('gives the hover card a readable class', () => {
    expect(classLabel('primary')).toBe('PRIMARY')
    expect(classLabel('residential')).toBe('MINOR')
  })
})

describe('pathMidpoint', () => {
  it('is halfway along the path, not the middle vertex', () => {
    expect(
      pathMidpoint([
        [0, 0],
        [10, 0]
      ])
    ).toEqual([5, 0])

    // a long first span and a short second one: the midpoint sits in the first
    expect(
      pathMidpoint([
        [0, 0],
        [10, 0],
        [11, 0]
      ])
    ).toEqual([5.5, 0])
  })

  it('survives an empty, single or zero-length path', () => {
    expect(pathMidpoint([])).toEqual([0, 0])
    expect(pathMidpoint([[3, 4]])).toEqual([3, 4])
    expect(
      pathMidpoint([
        [3, 4],
        [3, 4]
      ])
    ).toEqual([3, 4])
  })
})

describe('buildGraphSource', () => {
  it('keeps one feature per directed edge, with the id it was given', () => {
    const a = edge(1, 2, { name: 'Avenue de Cour', highway: 'secondary', speed_kph: 50 })
    const { collection } = buildGraphSource([a, reversed(a)])

    expect(collection.features).toHaveLength(2)
    expect(collection.features.map((f) => f.id)).toEqual([0, 1])
    expect(collection.features[0].properties).toMatchObject({
      u: 1,
      v: 2,
      sk: '1-2',
      name: 'Avenue de Cour',
      cls: 1.3,
      two: 1,
      side: 1,
      speed: 50
    })
  })

  it('marks a street with no reverse as one-way', () => {
    const { collection, streets } = buildGraphSource([edge(1, 2)])
    expect(collection.features[0].properties.two).toBe(0)
    expect(streets.get('1-2')?.oneway).toBe(true)
    expect(streets.get('1-2')?.bwdId).toBeUndefined()
  })

  it('pairs the two directions under one street key', () => {
    const a = edge(5, 3, { name: 'Rue X' })
    const { streets } = buildGraphSource([a, reversed(a)])

    expect(streets.size).toBe(1)
    const street = streets.get('3-5')!
    expect(street.oneway).toBe(false)
    // fwd is lo -> hi, which here is the second feature (3 -> 5)
    expect(street.fwdId).toBe(1)
    expect(street.bwdId).toBe(0)
    expect(street.lo).toBe(3)
    expect(street.hi).toBe(5)
  })

  it('splits a reverse twin that kept the same coordinates', () => {
    const a = edge(1, 2)
    const twin: EdgeGeometry = { ...a, u: 2, v: 1 } // same coordinates on purpose
    const { collection } = buildGraphSource([a, twin])

    // 1->2 is the fwd side, 2->1 must go the other way or they overlap
    expect(collection.features[0].properties.side).toBe(1)
    expect(collection.features[1].properties.side).toBe(-1)
  })

  it('keeps every parallel edge but names the street once', () => {
    const a = edge(1, 2, { name: 'First' })
    const parallel = edge(1, 2, { name: 'Second' })
    const { collection, streets } = buildGraphSource([a, parallel])

    expect(collection.features).toHaveLength(2)
    expect(streets.get('1-2')?.name).toBe('First')
  })

  it('treats a self loop as one-way', () => {
    const { streets } = buildGraphSource([edge(7, 7)])
    expect(streets.get('7-7')?.oneway).toBe(true)
  })

  it('drops the Unknown placeholder name', () => {
    const { collection, streets } = buildGraphSource([edge(1, 2, { name: 'Unknown' })])
    expect(collection.features[0].properties.name).toBe('')
    expect(streets.get('1-2')?.name).toBe('')
  })

  it('lists the streets that meet at a node, for the popover labels', () => {
    const cour = edge(1, 2, { name: 'Avenue de Cour' })
    const ouchy = edge(2, 3, { name: "Avenue d'Ouchy" })
    const { nodeStreets } = buildGraphSource([cour, ouchy])

    expect(nodeStreets.get(2)).toEqual(['Avenue de Cour', "Avenue d'Ouchy"])
    expect(nodeStreets.get(1)).toEqual(['Avenue de Cour'])
  })

  it('flags an edge served by a bus line', () => {
    const { collection } = buildGraphSource([edge(1, 2, { bus_route_count: 2 }), edge(3, 4)])
    expect(collection.features[0].properties.bus).toBe(1)
    expect(collection.features[1].properties.bus).toBe(0)
  })

  it('gives the corners of everything it draws', () => {
    const { bounds } = buildGraphSource([
      edge(1, 2, {
        coordinates: [
          [6.6, 46.5],
          [6.8, 46.4]
        ]
      }),
      edge(3, 4, {
        coordinates: [
          [6.5, 46.6],
          [6.7, 46.55]
        ]
      })
    ])

    expect(bounds).toEqual([
      [6.5, 46.4],
      [6.8, 46.6]
    ])
  })

  it('says nowhere for an empty network', () => {
    expect(buildGraphSource([]).bounds).toEqual([
      [0, 0],
      [0, 0]
    ])
  })
})

describe('sideOfTravel', () => {
  // screen pixels: y grows downward
  it('is positive to the right of the way', () => {
    const a: [number, number] = [0, 0]
    const b: [number, number] = [10, 0] // heading right
    expect(sideOfTravel(a, b, [5, 5])).toBe(1) // below on screen = right of travel
    expect(sideOfTravel(a, b, [5, -5])).toBe(-1)
    expect(sideOfTravel(a, b, [5, 0])).toBe(0)
  })

  it('flips when the way heads the other way', () => {
    const a: [number, number] = [10, 0]
    const b: [number, number] = [0, 0]
    expect(sideOfTravel(a, b, [5, 5])).toBe(-1)
  })
})

describe('pickLane', () => {
  const identity = (p: [number, number]): [number, number] => p
  const path: [number, number][] = [
    [0, 0],
    [10, 0]
  ]

  it('picks the lane the cursor sits on', () => {
    expect(pickLane(path, [5, 4], identity)).toBe('fwd')
    expect(pickLane(path, [5, -4], identity)).toBe('bwd')
  })

  it('reads the other way round on a bwd geometry', () => {
    expect(pickLane(path, [5, 4], identity, false)).toBe('bwd')
  })

  it('falls back to fwd on a degenerate path', () => {
    expect(pickLane([[0, 0]], [5, 5], identity)).toBe('fwd')
  })

  it('uses the nearest segment of a bent street', () => {
    const bent: [number, number][] = [
      [0, 0],
      [10, 0],
      [10, 10]
    ]
    // nearest is the second segment, heading down the screen. Right of that
    // way is the smaller x, so a cursor at x 6 is on the fwd lane and one at
    // x 14 is on the bwd lane. The first segment would answer the other way.
    expect(pickLane(bent, [6, 5], identity)).toBe('fwd')
    expect(pickLane(bent, [14, 5], identity)).toBe('bwd')
  })
})
