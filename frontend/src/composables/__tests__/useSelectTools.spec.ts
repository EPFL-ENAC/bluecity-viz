import { useSelectTools, type StreetsInBox } from '@/composables/useSelectTools'
import { useScenarioStore } from '@/stores/scenario'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'

// A street running east-west at y = 12, and one far to the south.
const NEAR: [number, number][] = [
  [5, 12],
  [60, 12]
]
const FAR: [number, number][] = [
  [5, 400],
  [60, 400]
]

/**
 * The frames the composable asked for.
 *
 * requestAnimationFrame has to hand its id back before the callback runs, the
 * way the browser does: the throttle in useSelectTools reads that id, so a
 * stub that fires at once would latch it and swallow every later move.
 */
let frames: FrameRequestCallback[] = []

function flushFrames() {
  const queued = frames
  frames = []
  for (const cb of queued) cb(0)
}

function stubFrames() {
  frames = []
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {
    frames = []
  })
}

function fakeMap() {
  const handlers = new Map<string, (event: unknown) => void>()
  const canvas = { style: { cursor: '' } }
  return {
    dragPan: { disable: vi.fn(), enable: vi.fn() },
    getCanvas: () => canvas,
    // the streets are already given in screen pixels, so this is the identity
    project: (position: [number, number]) => ({ x: position[0], y: position[1] }),
    on(name: string, fn: (event: unknown) => void) {
      handlers.set(name, fn)
    },
    off(name: string) {
      handlers.delete(name)
    },
    fire(name: string, x: number, y: number) {
      handlers.get(name)?.({ point: { x, y }, preventDefault() {} })
      flushFrames()
    },
    handlers
  }
}

/** Every street, whatever the box: the box only narrows, the shape decides. */
const allStreets: StreetsInBox = () => [
  { key: '1-2', coordinates: NEAR },
  { key: '3-4', coordinates: FAR }
]

function setup(tool: 'lasso' | 'brush' | 'pointer') {
  setActivePinia(createPinia())
  const store = useScenarioStore()
  store.isOpen = true
  store.tool = tool

  const map = fakeMap()
  const done = vi.fn()
  const tools = useSelectTools(ref(map) as never, allStreets, { onDone: done })
  tools.attach(map as never)
  return { store, map, tools, done }
}

describe('the lasso', () => {
  beforeEach(stubFrames)

  it('takes the streets the shape holds, and leaves the rest', () => {
    const { store, map, done } = setup('lasso')

    // a box around the near street only
    map.fire('mousedown', 0, 0)
    map.fire('mousemove', 100, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mousemove', 0, 40)
    map.fire('mouseup', 0, 0)

    expect(store.selected?.keys).toEqual(['1-2'])
    expect(done).toHaveBeenCalledTimes(1)
  })

  it('gives the map its drag back when the stroke ends', () => {
    const { map } = setup('lasso')
    map.fire('mousedown', 0, 0)
    expect(map.dragPan.disable).toHaveBeenCalled()
    map.fire('mousemove', 100, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mouseup', 0, 40)
    expect(map.dragPan.enable).toHaveBeenCalled()
  })

  it('is not a stray click: too small a shape takes nothing', () => {
    const { store, map, done } = setup('lasso')
    map.fire('mousedown', 20, 12)
    map.fire('mousemove', 21, 12)
    map.fire('mouseup', 21, 13)
    expect(store.selected).toBeNull()
    expect(done).not.toHaveBeenCalled()
  })

  it('adds a second stroke to the first', () => {
    const { store, map } = setup('lasso')
    map.fire('mousedown', 0, 0)
    map.fire('mousemove', 100, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mouseup', 0, 40)

    map.fire('mousedown', 0, 380)
    map.fire('mousemove', 100, 380)
    map.fire('mousemove', 100, 420)
    map.fire('mouseup', 0, 420)

    expect(store.selected?.keys).toEqual(['1-2', '3-4'])
  })
})

describe('the brush', () => {
  beforeEach(stubFrames)

  it('takes the streets it passes over', () => {
    const { store, map } = setup('brush')
    store.brushRadius = 10

    map.fire('mousedown', 30, 30)
    map.fire('mousemove', 30, 18)
    map.fire('mouseup', 30, 18)

    expect(store.selected?.keys).toEqual(['1-2'])
  })

  it('leaves a street the brush never reached', () => {
    const { store, map, done } = setup('brush')
    store.brushRadius = 8

    map.fire('mousedown', 30, 200)
    map.fire('mousemove', 30, 240)
    map.fire('mouseup', 30, 240)

    expect(store.selected).toBeNull()
    expect(done).not.toHaveBeenCalled()
  })

  it('catches a street between two samples of a fast stroke', () => {
    const { store, map } = setup('brush')
    store.brushRadius = 6

    // one jump right across the street, no sample lands on it
    map.fire('mousedown', 30, 60)
    map.fire('mousemove', 30, -30)
    map.fire('mouseup', 30, -30)

    expect(store.selected?.keys).toEqual(['1-2'])
  })
})

describe('the pointer', () => {
  beforeEach(stubFrames)

  it('leaves the map alone: no stroke, no drag taken', () => {
    const { store, map } = setup('pointer')
    map.fire('mousedown', 0, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mouseup', 100, 40)
    expect(store.selected).toBeNull()
    expect(map.dragPan.disable).not.toHaveBeenCalled()
  })
})

describe('giving the map back', () => {
  beforeEach(stubFrames)

  it('drops the tool when a result lights the map', async () => {
    const { store } = setup('lasso')
    store.mapMode = 'result'
    await nextTick()
    expect(store.tool).toBe('pointer')
  })

  it('drops the tool when the workbench closes', async () => {
    const { store } = setup('brush')
    store.isOpen = false
    await nextTick()
    expect(store.tool).toBe('pointer')
  })

  it('leaves the drag to the map while Space is held', () => {
    const { store, map } = setup('lasso')
    window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space' }))

    map.fire('mousedown', 0, 0)
    map.fire('mousemove', 100, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mouseup', 0, 40)

    expect(map.dragPan.disable).not.toHaveBeenCalled()
    expect(store.selected).toBeNull()

    // and the tool is back as soon as Space goes up
    window.dispatchEvent(new KeyboardEvent('keyup', { code: 'Space' }))
    map.fire('mousedown', 0, 0)
    map.fire('mousemove', 100, 0)
    map.fire('mousemove', 100, 40)
    map.fire('mouseup', 0, 40)
    expect(store.selected?.keys).toEqual(['1-2'])
  })
})
