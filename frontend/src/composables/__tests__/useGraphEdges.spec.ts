import { resetGraphEdges, useGraphEdges } from '@/composables/useGraphEdges'
import { fetchAreaEdges, fetchEdgeGeometries } from '@/services/trafficAnalysis'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

/** The store side of showArea: build mints the area, rebuild drops its id. */
function server() {
  return { build: vi.fn(async () => 'built'), rebuild: vi.fn() }
}

/** A promise somebody else resolves, to hold a step open. */
function deferred<T>() {
  let settle: (value: T) => void = () => {}
  const promise = new Promise<T>((resolve) => {
    settle = resolve
  })
  return { promise, settle }
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

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads the static city file when no area is named', async () => {
    const { edges: shown, showArea, currentAreaId } = useGraphEdges()
    const { build, rebuild } = server()

    await showArea('lausanne', build, rebuild)
    await showArea('', build, rebuild)

    expect(fetchEdgeGeometries).toHaveBeenCalledTimes(1)
    expect(fetchAreaEdges).not.toHaveBeenCalled()
    // the city is always there, nothing to build
    expect(build).not.toHaveBeenCalled()
    expect(currentAreaId.value).toBe('lausanne')
    expect(shown.value[0].u).toBe(1)
  })

  it('builds an area on the server before asking for its streets', async () => {
    const { edges: shown, showArea } = useGraphEdges()
    const { build, rebuild } = server()

    await showArea('area-a', build, rebuild)

    expect(build).toHaveBeenCalledTimes(1)
    expect(rebuild).not.toHaveBeenCalled()
    expect(shown.value[0].u).toBe(10)
  })

  it('empties the map while the new area is on its way', async () => {
    const { edges: shown, showArea } = useGraphEdges()
    const { build, rebuild } = server()
    const held = deferred<string>()

    await showArea('area-a', build, rebuild)
    expect(shown.value).toHaveLength(1)

    const moving = showArea('area-b', () => held.promise, rebuild)
    // the streets of the old place are gone before the new ones arrive
    expect(shown.value).toHaveLength(0)

    held.settle('built')
    await moving
    expect(shown.value[0].u).toBe(20)
  })

  it('leaves the map empty when the area cannot be built', async () => {
    const { edges: shown, showArea } = useGraphEdges()
    const rebuild = vi.fn()
    const build = vi.fn(async () => {
      throw new Error('too sparse')
    })

    await showArea('area-a', build, rebuild)

    expect(fetchAreaEdges).not.toHaveBeenCalled()
    expect(shown.value).toHaveLength(0)
  })

  it('builds the area again when the server has dropped it', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { edges: shown, showArea } = useGraphEdges()
    const { build, rebuild } = server()
    vi.mocked(fetchAreaEdges)
      .mockRejectedValueOnce(new Error('area_not_loaded'))
      .mockResolvedValueOnce(edges(10))

    await showArea('area-a', build, rebuild)

    expect(rebuild).toHaveBeenCalledTimes(1)
    expect(build).toHaveBeenCalledTimes(2)
    expect(shown.value[0].u).toBe(10)
  })

  it('gives up after one rebuild', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { edges: shown, showArea } = useGraphEdges()
    const { build, rebuild } = server()
    vi.mocked(fetchAreaEdges).mockRejectedValue(new Error('area_not_loaded'))

    await showArea('area-a', build, rebuild)

    expect(build).toHaveBeenCalledTimes(2)
    expect(shown.value).toHaveLength(0)
  })

  it('shows the area asked for last', async () => {
    const { edges: shown, currentAreaId, showArea } = useGraphEdges()
    const { rebuild } = server()
    const slow = deferred<string>()

    const first = showArea('area-a', () => slow.promise, rebuild)
    const second = showArea('area-b', async () => 'built', rebuild)
    await second
    // the slow one lands after, and must not put its streets on the map
    slow.settle('built')
    await first

    expect(currentAreaId.value).toBe('area-b')
    expect(shown.value[0].u).toBe(20)
  })

  it('keeps one network per area and switches without fetching again', async () => {
    const { edges: shown, showArea, getEdge } = useGraphEdges()
    const { build, rebuild } = server()

    await showArea('area-a', build, rebuild)
    expect(shown.value[0].u).toBe(10)
    expect(getEdge(10, 11)).toBeDefined()

    await showArea('area-b', build, rebuild)
    expect(shown.value[0].u).toBe(20)
    // the network of the other area is not on screen any more
    expect(getEdge(10, 11)).toBeUndefined()

    await showArea('area-a', build, rebuild)
    expect(shown.value[0].u).toBe(10)
    expect(fetchAreaEdges).toHaveBeenCalledTimes(2)
    // it was still cached, so the server was not asked for it again
    expect(build).toHaveBeenCalledTimes(2)
  })

  it('asks once when two calls for the same area overlap', async () => {
    const { showArea } = useGraphEdges()
    const { build, rebuild } = server()

    await Promise.all([showArea('area-a', build, rebuild), showArea('area-a', build, rebuild)])

    expect(fetchAreaEdges).toHaveBeenCalledTimes(1)
  })

  it('drops the least recently shown network past the cache size', async () => {
    const { showArea } = useGraphEdges()
    const { build, rebuild } = server()

    await showArea('lausanne', build, rebuild)
    await showArea('area-a', build, rebuild)
    await showArea('area-b', build, rebuild)
    // the city is the oldest, back to it and it is the newest again
    await showArea('lausanne', build, rebuild)
    await showArea('area-c', build, rebuild)

    // area-a was dropped, the city was not
    await showArea('lausanne', build, rebuild)
    expect(fetchEdgeGeometries).toHaveBeenCalledTimes(1)
    await showArea('area-a', build, rebuild)
    expect(vi.mocked(fetchAreaEdges).mock.calls.filter((c) => c[0] === 'area-a')).toHaveLength(2)
  })
})
