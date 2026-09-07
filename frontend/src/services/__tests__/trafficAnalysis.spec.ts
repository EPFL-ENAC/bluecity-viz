import { fetchBaseline, fetchGraphInfo, recalculateRoutes } from '@/services/trafficAnalysis'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A minimal response, enough for the service: it only reads ok and json().
function okResponse(body: unknown) {
  return { ok: true, status: 200, statusText: 'OK', json: async () => body }
}

function errorResponse(status: number, body: unknown, statusText = 'Error') {
  return { ok: false, status, statusText, json: async () => body }
}

function fetchMock() {
  return vi.mocked(globalThis.fetch as unknown as ReturnType<typeof vi.fn>)
}

/** The URL of the nth call. */
function calledUrl(index = 0): string {
  return fetchMock().mock.calls[index][0] as string
}

/** The parsed JSON body of the nth call. */
function calledBody(index = 0): Record<string, unknown> {
  const init = fetchMock().mock.calls[index][1] as { body: string }
  return JSON.parse(init.body)
}

describe('traffic analysis service', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('asks recalculate for a pair count and without the baseline', async () => {
    fetchMock().mockResolvedValue(okResponse({ od_pairs: 20000, new_edge_usage: [] }))

    await recalculateRoutes([{ u: 1, v: 2, action: 'remove' }], {
      useCongestionModel: true,
      congestionIterations: 3,
      elasticDemand: true,
      odPairs: 20000
    })

    expect(calledUrl()).toBe('/api/v1/routes/recalculate')
    expect(calledBody()).toEqual({
      edge_modifications: [{ u: 1, v: 2, action: 'remove' }],
      weight: 'travel_time',
      include_geometry: true,
      use_congestion: true,
      congestion_iterations: 3,
      resample_destinations: true,
      od_pairs: 20000,
      include_baseline: false
    })
  })

  it('sends a null pair count when the caller has none', async () => {
    fetchMock().mockResolvedValue(okResponse({ od_pairs: 20000, new_edge_usage: [] }))

    await recalculateRoutes([])

    const body = calledBody()
    expect(body.od_pairs).toBeNull()
    expect(body.include_baseline).toBe(false)
    expect(body.resample_destinations).toBe(false)
  })

  it('puts the pair count in the baseline query, and omits it when there is none', async () => {
    fetchMock().mockResolvedValue(okResponse({ total_routes: 10, od_pairs: 20000, edge_usage: [] }))

    await fetchBaseline(20000)
    expect(calledUrl()).toBe('/api/v1/routes/baseline?od_pairs=20000')

    await fetchBaseline()
    expect(calledUrl(1)).toBe('/api/v1/routes/baseline')
  })

  it('reads the graph info', async () => {
    fetchMock().mockResolvedValue(
      okResponse({ od_pairs: 76200, od_pairs_default: 20000, od_pairs_max: 76400 })
    )

    const info = await fetchGraphInfo()

    expect(calledUrl()).toBe('/api/v1/routes/graph-info')
    expect(info.od_pairs_max).toBe(76400)
  })

  it('reports the server message, string detail or pydantic list', async () => {
    fetchMock().mockResolvedValue(errorResponse(422, { detail: 'od_pairs must be at most 76400' }))
    await expect(fetchBaseline(99999)).rejects.toThrow('od_pairs must be at most 76400')

    fetchMock().mockResolvedValue(
      errorResponse(422, { detail: [{ msg: 'ensure this value is at most 3' }] })
    )
    await expect(recalculateRoutes([])).rejects.toThrow('ensure this value is at most 3')
  })

  it('falls back to the status text when there is no readable body', async () => {
    fetchMock().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new Error('not json')
      }
    })

    await expect(fetchGraphInfo()).rejects.toThrow('Internal Server Error')
  })
})
