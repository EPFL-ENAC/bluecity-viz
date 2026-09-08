import {
  DEFAULT_AREA_ID,
  fetchAreaEdges,
  fetchEdgeGeometries,
  type EdgeGeometry
} from '@/services/trafficAnalysis'
import { shallowRef } from 'vue'

/**
 * The road network geometry of the area on screen.
 *
 * The default city comes from a static file of about 6 MB, an area the user
 * drew comes from the backend. Both are kept in module scope, so closing a
 * tool and opening it again does not fetch anything a second time, and going
 * back to an area seen before is instant.
 *
 * Both refs are shallow: deep reactivity over 10k edges would cost more than
 * everything else on this page.
 */
interface Network {
  edges: EdgeGeometry[]
  edgeMap: Map<string, EdgeGeometry>
}

// A few areas is plenty: the user goes back and forth between two or three.
const NETWORK_CACHE_SIZE = 3

const networks = new Map<string, Network>()
const pending = new Map<string, Promise<void>>()

const edges = shallowRef<EdgeGeometry[]>([])
const edgeMap = shallowRef<Map<string, EdgeGeometry>>(new Map())
const currentAreaId = shallowRef<string>(DEFAULT_AREA_ID)

// The area the map is going to. Building and fetching take time, and the user
// can pick another one meanwhile, so every step checks this before it draws:
// the last area asked for is the one that ends up on screen.
let wanted: string = DEFAULT_AREA_ID

export function edgeKey(u: number, v: number): string {
  return `${u}-${v}`
}

function areaOf(areaId: string | null | undefined): string {
  return areaId || DEFAULT_AREA_ID
}

async function load(areaId: string): Promise<void> {
  const loaded =
    areaId === DEFAULT_AREA_ID ? await fetchEdgeGeometries() : await fetchAreaEdges(areaId)

  const map = new Map<string, EdgeGeometry>()
  for (const edge of loaded) {
    map.set(edgeKey(edge.u, edge.v), edge)
  }
  networks.set(areaId, { edges: loaded, edgeMap: map })

  while (networks.size > NETWORK_CACHE_SIZE) {
    const oldest = networks.keys().next().value as string
    if (oldest === areaId) break
    networks.delete(oldest)
  }
}

/**
 * Put one network on screen.
 *
 * With nothing cached under that name this blanks the map, which is what we
 * want while an area is being built: the streets of the old place must not
 * stay under the new circle, or the user could click one the tool does not
 * have any more.
 */
function show(areaId: string): void {
  const network = networks.get(areaId)
  // move it to the end, so the one we drop is the one nobody came back to
  if (network) {
    networks.delete(areaId)
    networks.set(areaId, network)
  }
  // assign both, a new Map so the shallow ref fires
  edges.value = network?.edges ?? []
  edgeMap.value = network?.edgeMap ?? new Map()
  currentAreaId.value = areaId
}

/** Fetch one network into the cache, once, however many callers ask. */
function fetchInto(id: string): Promise<void> {
  let request = pending.get(id)
  if (!request) {
    request = load(id)
      .catch((error) => {
        // let a later call try again
        console.warn('Failed to load the road network', error)
      })
      .finally(() => {
        pending.delete(id)
      })
    pending.set(id, request)
  }
  return request
}

export function useGraphEdges() {
  /**
   * Show the streets of an area, building it on the server first if needed.
   *
   * The circle names the network, so this is the one road from "the user
   * picked here" to "these streets are on the map". The server only keeps a
   * drawn area for a while, so a network that is gone after a build is asked
   * for once more with a fresh id.
   *
   * `build` mints the area and gives back its id (the store's `ensureArea`),
   * `rebuild` forgets the id we had (the store's `forgetAreaId`). A build that
   * fails leaves the map empty, and the dock says why.
   */
  async function showArea(
    key: string,
    build: () => Promise<string | null>,
    rebuild: () => void
  ): Promise<void> {
    const id = areaOf(key)
    wanted = id

    if (networks.has(id)) {
      show(id)
      return
    }

    // Nothing cached, so this empties the map while we go and get it.
    show(id)
    if (id === DEFAULT_AREA_ID) {
      await fetchInto(id)
      if (wanted === id) show(id)
      return
    }

    for (let attempt = 0; attempt < 2; attempt++) {
      // The server answers from its own cache when it still has the circle,
      // so asking again costs one round trip and no rebuild.
      try {
        await build()
      } catch {
        // areaError carries the reason, the dock shows it
        return
      }
      if (wanted !== id) return

      await fetchInto(id)
      if (wanted !== id) return
      if (networks.has(id)) break

      // Built and already gone (a restart, an eviction). Mint it again, once.
      if (attempt === 0) rebuild()
    }

    show(id)
  }

  function getEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(u, v))
  }

  /** The same street the other way round, when the network has it. */
  function getReverseEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(v, u))
  }

  return { edges, edgeMap, currentAreaId, showArea, getEdge, getReverseEdge }
}

/** Tests only: forget every network so the next call fetches again. */
export function resetGraphEdges(): void {
  networks.clear()
  pending.clear()
  edges.value = []
  edgeMap.value = new Map()
  currentAreaId.value = DEFAULT_AREA_ID
  wanted = DEFAULT_AREA_ID
}
