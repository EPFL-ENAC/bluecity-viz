import { cdnRequest } from '@/utils/cdnRequest'
import type { ResourceType } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'

// MapLibre declares these as a const enum, which cannot be imported as a
// value, so name the two the map really sends us.
const SOURCE = 'Source' as ResourceType
const TILE = 'Tile' as ResourceType

const transform = cdnRequest(() => 'KEY')
const ARCHIVE = 'https://enacit4r-cdn.epfl.ch/bluecity/swiss_drive.pmtiles'

describe('cdnRequest', () => {
  it('puts the key on the archive when the source is opened', () => {
    // Not a Tile: this is the request that opens the pmtiles archive, and the
    // protocol keeps its query string on every range request after it.
    expect(transform(`pmtiles://${ARCHIVE}`, SOURCE)).toEqual({
      url: `pmtiles://${ARCHIVE}?apikey=KEY`,
      credentials: 'include'
    })
  })

  it('puts the key on the tiles', () => {
    expect(transform(`pmtiles://${ARCHIVE}/6/33/22`, TILE)?.url).toBe(
      `pmtiles://${ARCHIVE}/6/33/22?apikey=KEY`
    )
  })

  it('puts the key on a plain file of the cdn', () => {
    const url = 'https://enacit4r-cdn.epfl.ch/bluecity/swiss_graph_density.json'
    expect(transform(url, SOURCE)?.url).toBe(`${url}?apikey=KEY`)
  })

  it('leaves everything else alone', () => {
    // the basemap is on another host, and in dev the files are local
    for (const url of ['https://tiles.openfreemap.org/planet/1/2/3.pbf', '/geodata/x.pmtiles']) {
      expect(transform(url, TILE)).toEqual({ url })
    }
  })

  it('reads the key when the request is made, not when the map is built', () => {
    let key = ''
    const late = cdnRequest(() => key)
    key = 'LATER'
    expect(late(ARCHIVE, SOURCE)?.url).toBe(`${ARCHIVE}?apikey=LATER`)
  })
})
