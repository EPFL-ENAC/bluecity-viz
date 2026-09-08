import { createUrlSharingComposable } from '@/stores/layers/urlSharing'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import type { Investigation } from '../types'

const BERN = { kind: 'circle' as const, lon: 7.44, lat: 46.95, radiusM: 3000 }

function trafficInputs(area: unknown) {
  return {
    isOpen: true,
    edgeModifications: [{ u: 1, v: 2, action: 'remove', name: 'Rue X' }],
    activeVisualization: 'frequency',
    useCongestionModel: true,
    congestionIterations: 3,
    elasticDemand: false,
    filterBusRoutes: false,
    odPairs: 76200,
    area
  } as any
}

function makeSharing(investigation: Investigation | null) {
  const projects = ref<any[]>([])
  const switched: string[] = []
  const sharing = createUrlSharingComposable(
    ref(investigation),
    ref('2020-2023'),
    projects,
    (id: string) => switched.push(id)
  )
  return { sharing, projects, switched }
}

/** Read the link back into a fresh store, the way another browser would. */
function receive(url: string) {
  const query = new URL(url).search
  vi.stubGlobal('location', { search: query, origin: 'http://x', pathname: '/', href: url })
  vi.stubGlobal('history', { replaceState: vi.fn() })
  const received = makeSharing(null)
  const ok = received.sharing.loadStateFromUrl()
  vi.unstubAllGlobals()
  return { ok, projects: received.projects }
}

describe('share link', () => {
  it('carries the traffic inputs, the area included', () => {
    const investigation: Investigation = {
      id: 'inv-1',
      name: 'Bern closure',
      selectedSources: ['src'],
      selectedLayers: ['layer'],
      createdAt: new Date(),
      trafficAnalysis: trafficInputs(BERN)
    }

    vi.stubGlobal('location', { origin: 'http://x', pathname: '/', search: '' })
    const url = makeSharing(investigation).sharing.generateShareableUrl()
    vi.unstubAllGlobals()

    const { ok, projects } = receive(url)
    expect(ok).toBe(true)

    const shared = projects.value[0].investigations[0]
    expect(shared.name).toBe('Bern closure (Shared)')
    expect(shared.trafficAnalysis.area).toEqual(BERN)
    expect(shared.trafficAnalysis.odPairs).toBe(76200)
    // The link was made before the scenario moved out of the traffic inputs,
    // so the edges arrive in the old shape and come back as street keys.
    expect(shared.scenario.edgeModifications).toEqual([
      { key: '1-2', action: 'remove', dir: 'fwd', name: 'Rue X' }
    ])
  })

  it('carries the scenario of a link made today', () => {
    const investigation: Investigation = {
      id: 'inv-1',
      name: 'Bern closure',
      selectedSources: [],
      selectedLayers: [],
      createdAt: new Date(),
      trafficAnalysis: trafficInputs(BERN),
      scenario: { edgeModifications: [{ key: '4-9', action: '30', dir: 'both', name: 'Rue Y' }] }
    }

    vi.stubGlobal('location', { origin: 'http://x', pathname: '/', search: '' })
    const url = makeSharing(investigation).sharing.generateShareableUrl()
    vi.unstubAllGlobals()

    const shared = receive(url).projects.value[0].investigations[0]
    expect(shared.scenario.edgeModifications).toEqual([
      { key: '4-9', action: '30', dir: 'both', name: 'Rue Y' }
    ])
  })

  it('reads a broken area back as the default city', () => {
    const investigation: Investigation = {
      id: 'inv-1',
      name: 'Broken',
      selectedSources: [],
      selectedLayers: [],
      createdAt: new Date(),
      trafficAnalysis: trafficInputs({ kind: 'circle', lon: 2.35, lat: 48.85, radiusM: 3000 })
    }

    vi.stubGlobal('location', { origin: 'http://x', pathname: '/', search: '' })
    const url = makeSharing(investigation).sharing.generateShareableUrl()
    vi.unstubAllGlobals()

    const { projects } = receive(url)
    expect(projects.value[0].investigations[0].trafficAnalysis.area).toBeNull()
  })

  it('shares an investigation with no traffic analysis', () => {
    const investigation: Investigation = {
      id: 'inv-1',
      name: 'Plain',
      selectedSources: [],
      selectedLayers: [],
      createdAt: new Date()
    }

    vi.stubGlobal('location', { origin: 'http://x', pathname: '/', search: '' })
    const url = makeSharing(investigation).sharing.generateShareableUrl()
    vi.unstubAllGlobals()

    const { ok, projects } = receive(url)
    expect(ok).toBe(true)
    expect(projects.value[0].investigations[0].trafficAnalysis).toBeUndefined()
  })
})
