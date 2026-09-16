import { useMunicipalityPick } from '@/composables/useMunicipalityPick'
import { COMMUNES_HIT_LAYER } from '@/config/toolLayers'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, nextTick, ref } from 'vue'

type Box = [[number, number], [number, number]]

// Three communes in a row on screen, 100 px wide each: 1 | 2 | 3.
const COMMUNES = [
  { id: 1, box: [0, 0, 100, 100] },
  { id: 2, box: [100, 0, 200, 100] },
  { id: 3, box: [200, 0, 300, 100] }
]

/** The frames asked for, run by hand so the throttle behaves like a browser. */
let frames: FrameRequestCallback[] = []

function flushFrames() {
  const queued = frames
  frames = []
  for (const cb of queued) cb(0)
}

function fakeMap() {
  const handlers = new Map<string, Set<(event: unknown) => void>>()
  const layers = new Set<string>()
  const sources = new Set<string>()
  const canvas = { style: { cursor: '' } }
  return {
    dragPan: { disable: vi.fn(), enable: vi.fn() },
    getCanvas: () => canvas,
    getSource: (id: string) => (sources.has(id) ? {} : undefined),
    addSource: (id: string) => sources.add(id),
    removeSource: (id: string) => sources.delete(id),
    getLayer: (id: string) => (layers.has(id) ? {} : undefined),
    addLayer: (layer: { id: string }) => layers.add(layer.id),
    removeLayer: (id: string) => layers.delete(id),
    setFeatureState: vi.fn(),
    queryRenderedFeatures(at: Box | { x: number; y: number }, options: { layers: string[] }) {
      if (!options.layers.includes(COMMUNES_HIT_LAYER)) return []
      const [[x0, y0], [x1, y1]]: Box = Array.isArray(at)
        ? at
        : [
            [at.x, at.y],
            [at.x, at.y]
          ]
      return COMMUNES.filter(
        ({ box: [a, b, c, d] }) => x0 <= c && x1 >= a && y0 <= d && y1 >= b
      ).map(({ id }) => ({ id }))
    },
    on(name: string, fn: (event: unknown) => void) {
      if (!handlers.has(name)) handlers.set(name, new Set())
      handlers.get(name)!.add(fn)
    },
    off(name: string, fn: (event: unknown) => void) {
      handlers.get(name)?.delete(fn)
    },
    fire(name: string, x: number, y: number, altKey = false) {
      const event = { point: { x, y }, originalEvent: { altKey }, preventDefault() {} }
      for (const fn of handlers.get(name) ?? []) fn(event)
      flushFrames()
    }
  }
}

// Each test attaches one picker, and its window keys must not reach the next test.
let cleanup: (() => void) | null = null

function setup(ids: number[] = []) {
  setActivePinia(createPinia())
  const traffic = useTrafficAnalysisStore()
  const scenario = useScenarioStore()
  traffic.enterPickMode()
  traffic.setDraftKind('municipalities')
  for (const id of ids) traffic.toggleDraftMunicipality(id)
  traffic.pickTool = 'brush'
  scenario.brushRadius = 20

  const pick = useMunicipalityPick({
    colors: computed(() => ({ ink: '#000', accent: '#00f', grey: '#888' })) as never,
    canUse: computed(() => false),
    communes: ref(null),
    invalidate: vi.fn(),
    checkNow: vi.fn()
  })
  const map = fakeMap()
  pick.attach(map as never)
  cleanup = () => pick.detach(map as never)
  const picked = () => {
    const draft = traffic.draftArea
    return draft?.kind === 'municipalities' ? draft.ofsIds : []
  }
  return { traffic, scenario, pick, map, picked }
}

function key(code: string, keyName: string, type: 'keydown' | 'keyup' = 'keydown') {
  window.dispatchEvent(new KeyboardEvent(type, { code, key: keyName }))
}

describe('the municipality brush', () => {
  beforeEach(() => {
    frames = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    vi.stubGlobal('cancelAnimationFrame', () => {
      frames = []
    })
  })

  afterEach(() => {
    cleanup?.()
    cleanup = null
    vi.unstubAllGlobals()
  })

  it('adds every commune the stroke crosses, and no other', () => {
    const { map, picked } = setup()

    map.fire('mousedown', 50, 50)
    map.fire('mousemove', 150, 50)
    map.fire('mouseup', 160, 50)

    expect(picked()).toEqual([1, 2])
    expect(map.dragPan.disable).toHaveBeenCalled()
    expect(map.dragPan.enable).toHaveBeenCalled()
  })

  it('takes communes out with Alt held', () => {
    const { map, picked } = setup([1, 2, 3])

    map.fire('mousedown', 150, 50, true)
    map.fire('mouseup', 150, 50, true)

    expect(picked()).toEqual([1, 3])
  })

  it('does not toggle on the click that ends a stroke', () => {
    const { map, picked } = setup()

    map.fire('mousedown', 50, 50)
    map.fire('mouseup', 50, 50)
    map.fire('click', 50, 50)

    expect(picked()).toEqual([1])
  })

  it('shows its circle, and the trail while painting', () => {
    const { map, pick } = setup()

    map.fire('mousemove', 50, 50)
    expect(pick.brush.value).toMatchObject({ at: [50, 50], radius: 20, trail: [], erase: false })

    map.fire('mousedown', 50, 50, true)
    map.fire('mousemove', 60, 50)
    expect(pick.brush.value?.trail).toEqual([
      [50, 50],
      [60, 50]
    ])
    expect(pick.brush.value?.erase).toBe(true)
  })

  it('lets Space pan the map instead of painting', () => {
    const { map, picked } = setup()

    key('Space', ' ')
    map.fire('mousedown', 50, 50)
    map.fire('mouseup', 50, 50)
    expect(picked()).toEqual([])
    expect(map.getCanvas().style.cursor).toBe('grab')

    key('Space', ' ', 'keyup')
    expect(map.getCanvas().style.cursor).toBe('none')
  })

  it('switches tool with B and resizes with the brackets', async () => {
    const { traffic, scenario, map, picked } = setup()

    key('BracketRight', ']')
    expect(scenario.brushRadius).toBe(24)

    key('KeyB', 'b')
    expect(traffic.pickTool).toBe('pointer')
    await nextTick()

    // the pointer clicks one commune, and a second click takes it out
    map.fire('click', 250, 50)
    expect(picked()).toEqual([3])
    map.fire('click', 250, 50)
    expect(picked()).toEqual([])
  })

  it('forgets the keys and the stroke once detached', () => {
    const { traffic, map, pick, picked } = setup()

    map.fire('mousedown', 50, 50)
    pick.detach(map as never)
    expect(pick.brush.value).toBeNull()

    key('KeyB', 'b')
    expect(traffic.pickTool).toBe('brush')
    map.fire('mousemove', 150, 50)
    expect(picked()).toEqual([1])
  })
})
