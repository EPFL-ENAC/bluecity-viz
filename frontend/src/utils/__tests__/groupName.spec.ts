import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import type { PlacePoint } from '@/utils/areaName'
import { groupName, localPlace, mainAxis, zoneCircle, type NamedLine } from '@/utils/groupName'
import { describe, expect, it } from 'vitest'

const LAUSANNE = { lon: 6.632, lat: 46.52 }

/** A point put east / north of Lausanne, in metres, so the cases read plainly. */
function at(eastM = 0, northM = 0): [number, number] {
  return [LAUSANNE.lon + eastM / mPerDegLon(LAUSANNE.lat), LAUSANNE.lat + northM / mPerDegLat]
}

function place(name: string, kind: string, eastM = 0, northM = 0): PlacePoint {
  const [lon, lat] = at(eastM, northM)
  return { name, kind, lon, lat }
}

/** A straight street of `lengthM`, running east, starting at the offset given. */
function line(
  name: string,
  lengthM: number,
  eastM = 0,
  northM = 0,
  over: Partial<NamedLine> = {}
): NamedLine {
  return { name, coordinates: [at(eastM, northM), at(eastM + lengthM, northM)], ...over }
}

describe('the circle a group covers', () => {
  it('has no circle without a point', () => {
    expect(zoneCircle([])).toBeNull()
  })

  it('centres on the mean of the points', () => {
    const circle = zoneCircle([line('A', 200), line('B', 200, 0, 400)])!
    // two streets 400 m apart, so the centre is 200 m north of the first
    expect(circle.lat).toBeCloseTo(at(0, 200)[1], 6)
    expect(circle.lon).toBeCloseTo(at(100)[0], 6)
  })

  it('never asks the basemap from closer than 400 m', () => {
    // a 100 m block would otherwise be too small to reach its own quarter
    expect(zoneCircle([line('A', 100)])!.radiusM).toBe(400)
  })

  it('takes the farthest point when the group is wider than that', () => {
    const circle = zoneCircle([line('A', 4000)])!
    expect(circle.radiusM).toBeCloseTo(2000, -1)
  })
})

describe('the neighbourhood a zone sits in', () => {
  const circle = { kind: 'circle' as const, lon: at()[0], lat: at()[1], radiusM: 400 }

  it('takes the closest one', () => {
    const places = [place('Valency', 'quarter', 300), place('Chailly', 'neighbourhood', 100)]
    expect(localPlace(circle, places)).toBe('Chailly')
  })

  it('never takes a city or a town: they cover far more than a zone', () => {
    const places = [place('Lausanne', 'city', 50), place('Prilly', 'town', 60)]
    expect(localPlace(circle, places)).toBeNull()
  })

  it('ignores a neighbourhood too far to mean anything', () => {
    expect(localPlace(circle, [place('Chailly', 'neighbourhood', 1400)])).toBeNull()
  })
})

describe('the main street of a group', () => {
  it('has none when nothing is named', () => {
    expect(mainAxis([{ name: '', coordinates: [at(), at(500)] }])).toBeNull()
  })

  it('takes the longest one', () => {
    expect(mainAxis([line('Small', 200), line('Rue de Genève', 900, 0, 100)])).toBe('Rue de Genève')
  })

  it('adds up the pieces of one street', () => {
    // three blocks of the same street beat one longer street
    const lines = [
      line('Rue de Genève', 400),
      line('Rue de Genève', 400, 400),
      line('Rue de Genève', 400, 800),
      line('Avenue Long', 900, 0, 200)
    ]
    expect(mainAxis(lines)).toBe('Rue de Genève')
  })

  it('prefers the avenue to the three lanes hanging off it', () => {
    const lines = [
      line('Avenue de Cour', 400, 0, 0, { cls: 1.6 }),
      line('Petite A', 300, 0, 100, { cls: 0.7 }),
      line('Petite B', 300, 0, 200, { cls: 0.7 }),
      line('Petite C', 300, 0, 300, { cls: 0.7 })
    ]
    expect(mainAxis(lines)).toBe('Avenue de Cour')
  })

  it('lets the traffic break a tie once a result is in', () => {
    const quiet = line('Quiet', 400, 0, 0, { cls: 1, volume: 10 })
    const busy = line('Busy', 400, 0, 100, { cls: 1, volume: 900 })
    expect(mainAxis([quiet, busy])).toBe('Busy')
    // without the result the two are the same length, so the first one stands
    expect(mainAxis([line('Quiet', 400), line('Busy', 400, 0, 100)])).toBe('Quiet')
  })
})

describe('naming a group', () => {
  it('takes the neighbourhood it sits in', () => {
    const places = [place('Lausanne', 'city', 3000), place('Valency', 'quarter', 100)]
    expect(groupName([line('Rue A', 200)], places)).toBe('Valency')
  })

  it('names the main street rather than a corner of the city', () => {
    // the real Lausanne case: the city point is the only one anywhere near
    const places = [place('Lausanne', 'city', 240)]
    expect(groupName([line('Petite', 100), line('Rue Centrale', 600)], places)).toBe(
      'Around Rue Centrale'
    )
  })

  it('falls back on the main street when no place is close', () => {
    expect(groupName([line('Small', 100), line('Rue de Genève', 800)], [])).toBe(
      'Around Rue de Genève'
    )
  })

  it('says how many streets when nothing has a name', () => {
    const lines: NamedLine[] = [
      { name: '', coordinates: [at(), at(100)] },
      { name: '', coordinates: [at(0, 100), at(100, 100)] }
    ]
    expect(groupName(lines, [])).toBe('2 streets')
  })
})
