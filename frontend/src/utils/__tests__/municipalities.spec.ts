import {
  areaLabelOf,
  communeName,
  contiguous,
  loadMunicipalities,
  municipalityBbox,
  municipalityLabel,
  resetMunicipalities,
  type CommuneIndex
} from '@/utils/municipalities'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A chain 1 - 2 - 3, and 4 on its own. 10 borders 1, to check the ids sort
// as numbers.
const INDEX: CommuneIndex = {
  format_version: 1,
  source: 'test',
  communes: {
    '1': { name: 'A', nb: [2, 10], bbox: [7.0, 46.0, 7.1, 46.1] },
    '2': { name: 'B', nb: [1, 3], bbox: [7.1, 46.0, 7.2, 46.1] },
    '3': { name: 'C', nb: [2], bbox: [7.2, 46.05, 7.3, 46.2] },
    '4': { name: 'D', nb: [], bbox: [8.0, 47.0, 8.1, 47.1] },
    '10': { name: 'J', nb: [1], bbox: [6.9, 45.9, 7.0, 46.0] }
  }
}

describe('contiguous', () => {
  it('is true for one commune and false for none', () => {
    expect(contiguous([4], INDEX)).toBe(true)
    expect(contiguous([], INDEX)).toBe(false)
  })

  it('follows shared borders, in any order, through a chain', () => {
    expect(contiguous([1, 2], INDEX)).toBe(true)
    expect(contiguous([3, 1, 2], INDEX)).toBe(true)
    expect(contiguous([10, 1, 2, 3], INDEX)).toBe(true)
  })

  it('is false when a commune is apart, or when the link in the middle is missing', () => {
    expect(contiguous([1, 4], INDEX)).toBe(false)
    expect(contiguous([1, 3], INDEX)).toBe(false)
  })

  it('counts an unknown id as apart', () => {
    expect(contiguous([1, 999], INDEX)).toBe(false)
  })
})

describe('municipalityBbox', () => {
  it('is the box around every commune', () => {
    expect(municipalityBbox([1, 3], INDEX)).toEqual([7.0, 46.0, 7.3, 46.2])
  })

  it('skips unknown ids, and is null when none is known', () => {
    expect(municipalityBbox([2, 999], INDEX)).toEqual([7.1, 46.0, 7.2, 46.1])
    expect(municipalityBbox([999], INDEX)).toBeNull()
    expect(municipalityBbox([], INDEX)).toBeNull()
  })
})

describe('the name of a selection', () => {
  it('reads the same as the backend label', () => {
    expect(areaLabelOf([])).toBe('')
    expect(areaLabelOf(['Lausanne'])).toBe('Lausanne')
    expect(areaLabelOf(['Lausanne', 'Pully'])).toBe('Lausanne + Pully')
    expect(areaLabelOf(['A', 'B', 'C', 'D', 'E'])).toBe('A, B + 3 more')
  })

  it('cuts at 60 characters with an ellipsis', () => {
    const label = areaLabelOf(['x'.repeat(80)])
    expect(label).toHaveLength(60)
    expect(label.endsWith('…')).toBe(true)
  })

  it('uses the id order, as numbers, whatever the click order', () => {
    expect(municipalityLabel([10, 2, 1], INDEX)).toBe('A, B + 1 more')
    expect(municipalityLabel([2, 1], INDEX)).toBe('A + B')
  })

  it('skips an id the index does not know', () => {
    expect(municipalityLabel([2, 999], INDEX)).toBe('B')
  })

  it('names one commune by its number when the index is missing', () => {
    expect(communeName(3, INDEX)).toBe('C')
    expect(communeName(3, null)).toBe('Municipality 3')
  })
})

describe('loadMunicipalities', () => {
  beforeEach(() => {
    resetMunicipalities()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetMunicipalities()
  })

  it('fetches the index once', async () => {
    const fetchMock = vi.mocked(globalThis.fetch as unknown as ReturnType<typeof vi.fn>)
    fetchMock.mockResolvedValue({ ok: true, json: async () => INDEX })

    const first = await loadMunicipalities()
    const second = await loadMunicipalities()

    expect(first).toEqual(INDEX)
    expect(second).toBe(first)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toMatch(/swiss_communes\.json/)
  })

  it('is null when the deployment has no index', async () => {
    const fetchMock = vi.mocked(globalThis.fetch as unknown as ReturnType<typeof vi.fn>)
    fetchMock.mockResolvedValue({ ok: false, json: async () => ({}) })
    expect(await loadMunicipalities()).toBeNull()
  })
})
