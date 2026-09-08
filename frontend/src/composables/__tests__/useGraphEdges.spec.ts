import { resetGraphEdges, useGraphEdges } from '@/composables/useGraphEdges'
import { fetchAreaEdges, fetchEdgeGeometries } from '@/services/trafficAnalysis'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/trafficAnalysis', async () => ({
  ...(await vi.importActual<typeof import('@/services/trafficAnalysis')>(
    '@/services/trafficAnalysis'
  )),
  fetchEdgeGeometries: vi.fn(),
  fetchAreaEdges: vi.fn()
}))

function edges(u: number) {
  return [{ u, v: u + 1, coordinates: [[6, 46]] as [number, number][] }]
}

describe('useGraphEdges', () => {
  beforeEach(() => {
    resetGraphEdges()
    vi.mocked(fetchEdgeGeometries).mockReset()
    vi.mocked(fetchAreaEdges).mockReset()
    vi.mocked(fetchEdgeGeometries).mockResolvedValue(edges(1))
    vi.mocked(fetchAreaEdges).mockImplementation(async (areaId: string) =>
      edges(areaId === 'area-a' ? 10 : 20)
    )
  })

  it('reads the static city file when no area is named', async () => {
    const { edges: shown, loadGraphEdges, currentAreaId } = useGraphEdges()

    await loadGraphEdges()
    await loadGraphEdges(null)

    expect(fetchEdgeGeometries).toHaveBeenCalledTimes(1)
    expect(fetchAreaEdges).not.toHaveBeenCalled()
    expect(currentAreaId.value).toBe('lausanne')
    expect(shown.value[0].u).toBe(1)
  })

  it('keeps one network per area and switches without fetching again', async () => {
    const { edges: shown, loadGraphEdges, getEdge } = useGraphEdges()

    await loadGraphEdges('area-a')
    expect(shown.value[0].u).toBe(10)
    expect(getEdge(10, 11)).toBeDefined()

    await loadGraphEdges('area-b')
    expect(shown.value[0].u).toBe(20)
    // the network of the other area is not on screen any more
    expect(getEdge(10, 11)).toBeUndefined()

    await loadGraphEdges('area-a')
    expect(shown.value[0].u).toBe(10)
    expect(fetchAreaEdges).toHaveBeenCalledTimes(2)
  })

  it('asks once when two calls for the same area overlap', async () => {
    const { loadGraphEdges } = useGraphEdges()

    await Promise.all([loadGraphEdges('area-a'), loadGraphEdges('area-a')])

    expect(fetchAreaEdges).toHaveBeenCalledTimes(1)
  })

  it('drops the least recently shown network past the cache size', async () => {
    const { loadGraphEdges } = useGraphEdges()

    await loadGraphEdges()
    await loadGraphEdges('area-a')
    await loadGraphEdges('area-b')
    // the city is the oldest, back to it and it is the newest again
    await loadGraphEdges()
    await loadGraphEdges('area-c')

    // area-a was dropped, the city was not
    await loadGraphEdges()
    expect(fetchEdgeGeometries).toHaveBeenCalledTimes(1)
    await loadGraphEdges('area-a')
    expect(vi.mocked(fetchAreaEdges).mock.calls.filter((c) => c[0] === 'area-a')).toHaveLength(2)
  })
})
