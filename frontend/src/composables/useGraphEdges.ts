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

export function useGraphEdges() {
  /**
   * Fetch the network of an area once, then show it. Later calls for the same
   * area wait for the same request.
   */
  function loadGraphEdges(areaId?: string | null): Promise<void> {
    const id = areaOf(areaId)
    if (networks.has(id)) {
      show(id)
      return Promise.resolve()
    }

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
    return request.then(() => show(id))
  }

  function getEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(u, v))
  }

  /** The same street the other way round, when the network has it. */
  function getReverseEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(v, u))
  }

  return { edges, edgeMap, currentAreaId, loadGraphEdges, getEdge, getReverseEdge }
}

/** Tests only: forget every network so the next call fetches again. */
export function resetGraphEdges(): void {
  networks.clear()
  pending.clear()
  edges.value = []
  edgeMap.value = new Map()
  currentAreaId.value = DEFAULT_AREA_ID
}
