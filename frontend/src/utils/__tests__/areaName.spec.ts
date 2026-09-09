import type { TrafficAreaSelection } from '@/stores/layers/types'
import { mPerDegLat, mPerDegLon } from '@/utils/areaDensity'
import { areaLabel, collectPlaces, type PlacePoint } from '@/utils/areaName'
import { describe, expect, it } from 'vitest'

const LAUSANNE = { lon: 6.632, lat: 46.52 }

/** A place put east / north of Lausanne, in metres, so the cases read plainly. */
function place(name: string, kind: string, eastM = 0, northM = 0): PlacePoint {
  return {
    name,
    kind,
    lon: LAUSANNE.lon + eastM / mPerDegLon(LAUSANNE.lat),
    lat: LAUSANNE.lat + northM / mPerDegLat
  }
}

function circle(eastM = 0, northM = 0, radiusM = 3000): TrafficAreaSelection {
  const centre = place('', '', eastM, northM)
  return { kind: 'circle', lon: centre.lon, lat: centre.lat, radiusM }
}

describe('naming the picked area', () => {
  it('gives the city alone when the circle sits on it', () => {
    const places = [place('Lausanne', 'city'), place('Chailly', 'suburb', 2400)]
    expect(areaLabel(circle(), places)).toBe('Lausanne')
  })

  it('says which part of the city, when the circle is on one side', () => {
    // 3 km circle centred 2.4 km east of the city point.
    const places = [place('Lausanne', 'city'), place('Chailly', 'suburb', 2400, 300)]
    expect(areaLabel(circle(2400), places)).toBe('East Lausanne')
  })

  it('reads the other directions too', () => {
    const places = [place('Lausanne', 'city')]
    expect(areaLabel(circle(0, 2400), places)).toBe('North Lausanne')
    expect(areaLabel(circle(0, -2400), places)).toBe('South Lausanne')
    expect(areaLabel(circle(-1800, -1800), places)).toBe('South-west Lausanne')
  })

  it('keeps the city over its neighbour town, and says which side', () => {
    const places = [place('Lausanne', 'city', -1900), place('Pully', 'town', 300, -700)]
    expect(areaLabel(circle(), places)).toBe('East Lausanne')
  })

  it('names both towns when the circle straddles them', () => {
    const places = [
      place('Renens', 'town', -800),
      place('Crissier', 'town', 900, 200),
      place('Lausanne', 'city', 4200)
    ]
    expect(areaLabel(circle(0, 0, 2000), places)).toBe('Renens & Crissier')
  })

  it('takes the quarter when the circle is small and sits on it', () => {
    const places = [place('Lausanne', 'city', -2400), place('Chailly', 'suburb', 0, 200)]
    expect(areaLabel(circle(0, 0, 1000), places)).toBe('Chailly')
  })

  it('never puts a direction on a quarter', () => {
    const places = [place('Chailly', 'suburb', 700)]
    expect(areaLabel(circle(0, 0, 1000), places)).toBe('Chailly')
  })

  it('says "near" when the only town is outside the circle', () => {
    const places = [place('Morges', 'town', -6000)]
    expect(areaLabel(circle(0, 0, 3000), places)).toBe('Near Morges')
  })

  it('gives up far from everything, and on a style with no labels', () => {
    expect(areaLabel(circle(0, 0, 1000), [place('Morges', 'town', -40000)])).toBeNull()
    expect(areaLabel(circle(), [])).toBeNull()
  })
})

/** Just enough of a MapLibre map for collectPlaces. */
function fakeMap(features: unknown[] | null) {
  return {
    getSource: () => (features === null ? undefined : {}),
    querySourceFeatures: () => features ?? []
  } as unknown as Parameters<typeof collectPlaces>[0]
}

function placeFeature(name: string, kind: string, lon: number, lat: number) {
  return { properties: { name, class: kind }, geometry: { type: 'Point', coordinates: [lon, lat] } }
}

describe('reading the places off the map', () => {
  it('gives nothing on a style with no place layer', () => {
    expect(collectPlaces(fakeMap(null))).toEqual([])
  })

  it('keeps one point per place, whatever the number of tiles', () => {
    const places = collectPlaces(
      fakeMap([
        placeFeature('Lausanne', 'city', 6.632, 46.52),
        placeFeature('Lausanne', 'city', 6.632, 46.52),
        placeFeature('Renens', 'town', 6.58, 46.54)
      ])
    )
    expect(places.map((p) => p.name)).toEqual(['Lausanne', 'Renens'])
    expect(places[0]).toEqual({ name: 'Lausanne', kind: 'city', lon: 6.632, lat: 46.52 })
  })

  it('drops what is not a settlement, and what has no name', () => {
    const places = collectPlaces(
      fakeMap([
        placeFeature('Suisse', 'country', 8, 46.8),
        placeFeature('Vaud', 'state', 6.6, 46.6),
        placeFeature('', 'city', 6.6, 46.5),
        placeFeature('Pully', 'town', 6.66, 46.51)
      ])
    )
    expect(places.map((p) => p.name)).toEqual(['Pully'])
  })
})
