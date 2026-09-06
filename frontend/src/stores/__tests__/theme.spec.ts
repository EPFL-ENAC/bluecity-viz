import { useThemeStore } from '@/stores/theme'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// jsdom does not expose localStorage as a global here, so we give the store a
// small in-memory one. This also lets us set a stored value before the store
// reads it.
function makeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
    clear: () => data.clear()
  }
}

describe('theme store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults to the Trait basemap', () => {
    vi.stubGlobal('localStorage', makeStorage())
    const store = useThemeStore()
    expect(store.theme).toBe('trait')
    expect(store.isDark).toBe(false)
    expect(store.isTrait).toBe(true)
    expect(store.themeLabel).toBe('Trait')
  })

  it('falls back to the default when the stored basemap is gone', () => {
    vi.stubGlobal('localStorage', makeStorage({ 'bluecity-viz-theme': 'style/dark.json' }))
    const store = useThemeStore()
    expect(store.theme).toBe('trait')
  })

  it('keeps a stored basemap that still exists', () => {
    vi.stubGlobal('localStorage', makeStorage({ 'bluecity-viz-theme': 'style/none.json' }))
    const store = useThemeStore()
    expect(store.theme).toBe('style/none.json')
  })

  it('is dark only for the dark Trait basemap', () => {
    vi.stubGlobal('localStorage', makeStorage())
    const store = useThemeStore()

    store.setTheme('trait-dark')
    expect(store.isDark).toBe(true)
    expect(store.isTrait).toBe(true)

    store.setTheme('style/light.json')
    expect(store.isDark).toBe(false)
    expect(store.isTrait).toBe(false)
  })
})
