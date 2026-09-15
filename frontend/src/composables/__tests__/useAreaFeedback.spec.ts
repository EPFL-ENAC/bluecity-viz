import { resetAreaFeedback, useAreaFeedback } from '@/composables/useAreaFeedback'
import { ApiError, previewArea, type AreaPreview } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { loadMunicipalities, type CommuneIndex } from '@/utils/municipalities'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/trafficAnalysis', async () => ({
  ...(await vi.importActual<typeof import('@/services/trafficAnalysis')>(
    '@/services/trafficAnalysis'
  )),
  previewArea: vi.fn(),
  fetchAreaLimits: vi.fn().mockRejectedValue(new Error('not in this test'))
}))

vi.mock('@/utils/areaDensity', async () => ({
  ...(await vi.importActual<typeof import('@/utils/areaDensity')>('@/utils/areaDensity')),
  loadDensity: vi.fn().mockResolvedValue(null)
}))

vi.mock('@/utils/municipalities', async () => ({
  ...(await vi.importActual<typeof import('@/utils/municipalities')>('@/utils/municipalities')),
  loadMunicipalities: vi.fn()
}))

// Lausanne and Pully touch, Fribourg is apart.
const INDEX: CommuneIndex = {
  format_version: 1,
  source: 'test',
  communes: {
    '5586': { name: 'Lausanne', nb: [5590], bbox: [6.58, 46.45, 6.72, 46.6] },
    '5590': { name: 'Pully', nb: [5586], bbox: [6.64, 46.45, 6.7, 46.54] },
    '2196': { name: 'Fribourg', nb: [], bbox: [7.13, 46.78, 7.19, 46.82] }
  }
}

const OUTLINE = {
  type: 'Polygon' as const,
  coordinates: [
    [
      [6.6, 46.5],
      [6.7, 46.5],
      [6.7, 46.6],
      [6.6, 46.5]
    ]
  ]
}

function preview(overrides: Partial<AreaPreview> = {}): AreaPreview {
  return {
    ok: true,
    code: null,
    message: '',
    node_count: 1800,
    edge_count: 4000,
    junction_count: 1400,
    scc_fraction: 0.93,
    bbox: null,
    outline: OUTLINE,
    ...overrides
  }
}

/** A picker open on communes, and the feedback of it. */
async function pick(ids: number[]) {
  const store = useTrafficAnalysisStore()
  const feedback = useAreaFeedback()
  await vi.runAllTimersAsync()
  store.enterPickMode()
  store.setDraftKind('municipalities')
  for (const id of ids) store.toggleDraftMunicipality(id)
  return { store, ...feedback }
}

describe('feedback on picked municipalities', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    resetAreaFeedback()
    vi.mocked(previewArea).mockReset()
    vi.mocked(loadMunicipalities).mockResolvedValue(INDEX)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('says nothing is selected, and asks nothing', async () => {
    const { feedback, canUse, checkNow } = await pick([])

    checkNow()
    await vi.runAllTimersAsync()

    expect(feedback.value.status).toBe('empty')
    expect(canUse.value).toBe(false)
    expect(previewArea).not.toHaveBeenCalled()
  })

  it('refuses communes that do not touch without asking the server', async () => {
    const { feedback, canUse, checkNow } = await pick([5586, 2196])

    checkNow()
    await vi.runAllTimersAsync()

    expect(feedback.value.status).toBe('not_contiguous')
    expect(canUse.value).toBe(false)
    expect(previewArea).not.toHaveBeenCalled()
  })

  it('is checking, not ok, until the server answers', async () => {
    vi.mocked(previewArea).mockResolvedValue(preview())
    const { feedback, canUse, checkNow, lastOutline } = await pick([5586, 5590])

    expect(feedback.value.status).toBe('checking')
    expect(canUse.value).toBe(false)

    checkNow()
    await vi.runAllTimersAsync()

    expect(previewArea).toHaveBeenCalledWith({ kind: 'municipalities', ofsIds: [5586, 5590] })
    expect(feedback.value.status).toBe('ok')
    expect(feedback.value.estimate).toEqual({ junctions: 1400, edges: 4000 })
    expect(canUse.value).toBe(true)
    expect(lastOutline.value).toEqual(OUTLINE)
  })

  it('shows the rejection of the server, and keeps its outline', async () => {
    vi.mocked(previewArea).mockResolvedValue(preview({ ok: false, code: 'too_large' }))
    const { feedback, checkNow, lastOutline } = await pick([5586])

    checkNow()
    await vi.runAllTimersAsync()

    expect(feedback.value.status).toBe('too_large')
    expect(lastOutline.value).toEqual(OUTLINE)
  })

  it('keeps the outline while the next click is checked, and drops it when empty', async () => {
    vi.mocked(previewArea).mockResolvedValue(preview())
    const { store, feedback, checkNow, invalidate, lastOutline } = await pick([5586])
    checkNow()
    await vi.runAllTimersAsync()

    store.toggleDraftMunicipality(5590)
    invalidate()
    expect(feedback.value.status).toBe('checking')
    expect(lastOutline.value).toEqual(OUTLINE)

    store.toggleDraftMunicipality(5586)
    store.toggleDraftMunicipality(5590)
    expect(lastOutline.value).toBeNull()
  })

  it('leaves the local check to the server when the index is missing', async () => {
    vi.mocked(loadMunicipalities).mockResolvedValue(null)
    vi.mocked(previewArea).mockResolvedValue(preview({ ok: false, code: 'not_contiguous' }))
    const { feedback, checkNow } = await pick([5586, 2196])

    expect(feedback.value.status).toBe('checking')
    checkNow()
    await vi.runAllTimersAsync()

    expect(previewArea).toHaveBeenCalled()
    expect(feedback.value.status).toBe('not_contiguous')
  })

  it('is unavailable when the server has no boundaries file', async () => {
    vi.mocked(previewArea).mockRejectedValue(
      new ApiError('no boundaries', 503, 'no_municipalities')
    )
    const { store, feedback, checkNow } = await pick([5586])

    checkNow()
    await vi.runAllTimersAsync()

    expect(feedback.value.status).toBe('unavailable')
    // the circle does not depend on that file
    store.setDraftKind('circle')
    expect(feedback.value.status).not.toBe('unavailable')
  })
})
