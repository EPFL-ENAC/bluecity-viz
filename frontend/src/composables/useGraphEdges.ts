import { fetchEdgeGeometries, type EdgeGeometry } from '@/services/trafficAnalysis'
import { shallowRef } from 'vue'

/**
 * The road network geometry, loaded once for the whole app.
 *
 * The file is about 6 MB, so it is fetched on the first call and kept in module
 * scope: closing a tool and opening it again does not fetch it a second time.
 * Both refs are shallow, deep reactivity over 10k edges would cost more than
 * everything else on this page.
 */
const edges = shallowRef<EdgeGeometry[]>([])
const edgeMap = shallowRef<Map<string, EdgeGeometry>>(new Map())
let loadPromise: Promise<void> | null = null

export function edgeKey(u: number, v: number): string {
  return `${u}-${v}`
}

async function load(): Promise<void> {
  const loaded = await fetchEdgeGeometries()
  const map = new Map<string, EdgeGeometry>()
  for (const edge of loaded) {
    map.set(edgeKey(edge.u, edge.v), edge)
  }
  // assign both, a new Map so the shallow ref fires
  edges.value = loaded
  edgeMap.value = map
}

export function useGraphEdges() {
  /** Fetch the network once. Later calls wait for the same request. */
  function loadGraphEdges(): Promise<void> {
    if (!loadPromise) {
      loadPromise = load().catch((error) => {
        // let a later call try again
        loadPromise = null
        console.warn('Failed to load the road network', error)
      })
    }
    return loadPromise
  }

  function getEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(u, v))
  }

  /** The same street the other way round, when the network has it. */
  function getReverseEdge(u: number, v: number): EdgeGeometry | undefined {
    return edgeMap.value.get(edgeKey(v, u))
  }

  return { edges, edgeMap, loadGraphEdges, getEdge, getReverseEdge }
}

/** Tests only: forget the network so the next call fetches again. */
export function resetGraphEdges(): void {
  edges.value = []
  edgeMap.value = new Map()
  loadPromise = null
}
