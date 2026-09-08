import { resetAreaPicker, useAreaPicker } from '@/composables/useAreaPicker'
import { ApiError, previewArea } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { loadDensity, resetDensity, type Density } from '@/utils/areaDensity'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

vi.mock('@/services/trafficAnalysis', async () => ({
  ...(await vi.importActual<typeof import('@/services/trafficAnalysis')>(
    '@/services/trafficAnalysis'
  )),
  previewArea: vi.fn(),
  fetchAreaLimits: vi.fn().mockResolvedValue({
    min_nodes: 1000,
    max_nodes: 10000,
    max_edges: 20000,
    min_scc_fraction: 0.9,
    min_radius_m: 500,
    max_radius_m: 10000,
    coverage_bbox: [5.9, 45.8, 10.6, 47.9]
  })
}))

vi.mock('@/utils/areaDensity', async () => {
  const actual = await vi.importActual<typeof import('@/utils/areaDensity')>('@/utils/areaDensity')
  return { ...actual, loadDensity: vi.fn() }
})

// Real cell size (about 5 km), one dense cell in the middle, nothing around.
function density(): Density {
  const nodes = new Array(9).fill(0)
  const edges = new Array(9).fill(0)
  nodes[4] = 4000
  edges[4] = 8000
  return {
    format_version: 1,
    grid: { lon0: 7.4, lat0: 46.9, dlon: 0.064, dlat: 0.045, ncols: 3, nrows: 3 },
    coverage_bbox: [5.9, 45.8, 10.6, 47.9],
    nodes_sc3: nodes,
    edges
  }
}

// The middle of the dense cell, and a corner of the grid with no streets.
const DENSE = { lon: 7.496, lat: 46.9675 }
const EMPTY = { lon: 7.42, lat: 46.91 }

/** The layer the picker draws for the circle, by id. */
function circleLayer(layers: any[]) {
  return layers.find((layer) => layer.id === 'area-picker-circle')
}

describe('useAreaPicker', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    resetAreaPicker()
    resetDensity()
    vi.mocked(previewArea).mockReset()
    vi.mocked(loadDensity).mockResolvedValue(density())
  })

  it('draws nothing until the picker is open', () => {
    const picker = useAreaPicker()
    expect(picker.layers.value).toHaveLength(0)
  })

  it('draws the circle where the draft is', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    store.enterPickMode(DENSE)
    await nextTick()

    const layer = circleLayer(picker.layers.value)
    expect(layer).toBeDefined()
    expect(layer.props.getRadius).toBe(3000)
    expect(layer.props.data[0].position).toEqual([DENSE.lon, DENSE.lat])
  })

  it('moves the circle on a drag', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    store.enterPickMode(DENSE)
    await nextTick()

    circleLayer(picker.layers.value).props.onDrag({ coordinate: [7.5, 46.98] })

    expect(store.draftArea).toEqual({ kind: 'circle', lon: 7.5, lat: 46.98, radiusM: 3000 })
  })

  it('moves the circle on a click with nothing under it', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    store.enterPickMode(DENSE)
    await nextTick()

    expect(picker.handleMapClick({ coordinate: [7.5, 46.96] })).toBe(true)
    expect(store.draftArea?.lon).toBe(7.5)

    // outside the picker a click belongs to the streets, not to us
    store.exitPickMode(false)
    expect(picker.handleMapClick({ coordinate: [7.5, 46.96] })).toBe(false)
  })

  it('says the tool can run over a dense cell', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    await store.loadAreaLimits()
    await Promise.resolve()
    store.enterPickMode(DENSE)
    await nextTick()

    expect(picker.feedback.value.status).toBe('ok')
    expect(picker.feedback.value.estimate?.junctions).toBeGreaterThan(1000)
    expect(picker.canUse.value).toBe(true)
  })

  it('says an empty spot is too sparse', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    await store.loadAreaLimits()
    await Promise.resolve()
    store.enterPickMode(EMPTY)
    await nextTick()

    expect(picker.feedback.value.status).toBe('too_sparse')
    expect(picker.canUse.value).toBe(false)
  })

  it('refuses a spot outside the country', async () => {
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    await store.loadAreaLimits()
    await Promise.resolve()
    store.enterPickMode({ lon: 2.35, lat: 48.85 })
    await nextTick()

    expect(picker.feedback.value.status).toBe('outside_coverage')
  })

  it('shows the server answer once the drag stops', async () => {
    vi.useFakeTimers()
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    store.enterPickMode(DENSE)
    await nextTick()

    vi.mocked(previewArea).mockResolvedValue({
      ok: false,
      code: 'disconnected',
      message: 'the streets here are in pieces',
      node_count: 4000,
      edge_count: 8000,
      junction_count: 2500,
      scc_fraction: 0.4,
      bbox: null
    })

    circleLayer(picker.layers.value).props.onDragEnd()
    await vi.advanceTimersByTimeAsync(300)
    vi.useRealTimers()
    await nextTick()

    expect(previewArea).toHaveBeenCalledTimes(1)
    expect(picker.feedback.value.status).toBe('disconnected')
    expect(picker.feedback.value.estimate?.junctions).toBe(2500)
    expect(picker.canUse.value).toBe(false)
  })

  it('says so when the server has no Swiss network', async () => {
    vi.useFakeTimers()
    const store = useTrafficAnalysisStore()
    const picker = useAreaPicker()
    store.enterPickMode(DENSE)
    await nextTick()

    vi.mocked(previewArea).mockRejectedValue(
      new ApiError('no Swiss road network here', 503, 'no_swiss_graph')
    )

    circleLayer(picker.layers.value).props.onDragEnd()
    await vi.advanceTimersByTimeAsync(300)
    vi.useRealTimers()
    await nextTick()

    expect(picker.feedback.value.status).toBe('unavailable')
    expect(picker.canUse.value).toBe(false)
  })
})
