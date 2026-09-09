/**
 * How a MapLibre map reaches the EPFL CDN.
 *
 * Every file under /bluecity/ needs the API key on the query string, or the
 * CDN answers 404. A map asks for two different things and both have to carry
 * it:
 *
 * - the tiles of a pmtiles source, `pmtiles://https://…/x.pmtiles/{z}/{x}/{y}`
 * - the archive itself, when MapLibre opens the source. That request is not a
 *   Tile, and the key has to be on it: the pmtiles protocol keeps the query
 *   string of the source url on every range request it then makes for the
 *   header and the directories. Without it the archive never opens and the
 *   only sign is a 404 from FetchSource in the console.
 *
 * In dev `baseUrl` is `/geodata`, the files are read from the checkout and no
 * key is needed, so this only ever fires in production.
 */
import type { RequestParameters, ResourceType } from 'maplibre-gl'

/** The key is read on every request: the map outlives the dialog that sets it. */
export function cdnRequest(
  apiKey: () => string | null
): (url: string, resourceType?: ResourceType) => RequestParameters {
  return (url: string, resourceType?: ResourceType): RequestParameters => {
    const tile = resourceType === 'Tile' && url.includes('pmtiles://')
    if (tile || url.includes('/bluecity/')) {
      return { url: `${url}?apikey=${apiKey() ?? ''}`, credentials: 'include' }
    }
    return { url }
  }
}
