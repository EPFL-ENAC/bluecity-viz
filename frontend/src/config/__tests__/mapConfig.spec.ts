import { layerGroups, mapConfig } from '@/config/mapConfig'
import { describe, expect, it } from 'vitest'

// These snapshots pin the whole layer registry: ids, sources, paint stops and
// colours. They exist so the refactor to defineLayer() can prove it renders the
// same map. Update them only on purpose, and say why in the commit.
describe('map config registry', () => {
  it('keeps the same layers', () => {
    expect(mapConfig.layers).toMatchSnapshot()
  })

  it('keeps the same sources', () => {
    expect(mapConfig.sources).toMatchSnapshot()
  })

  it('keeps the same groups', () => {
    expect(
      layerGroups.map((group) => ({
        id: group.id,
        label: group.label,
        multiple: group.multiple,
        expanded: group.expanded,
        layers: group.layers.map((layer) => layer.layer.id)
      }))
    ).toMatchSnapshot()
  })

  it('has unique layer ids', () => {
    const ids = mapConfig.layers.map((layer) => layer.layer.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('has unique config ids', () => {
    const ids = mapConfig.layers.map((layer) => layer.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('has unique source ids', () => {
    const ids = mapConfig.sources.map((source) => source.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('names every layer <config id>-layer', () => {
    const odd = mapConfig.layers
      .filter((layer) => layer.layer.id !== `${layer.id}-layer`)
      .map((layer) => `${layer.id} -> ${layer.layer.id}`)
    expect(odd).toEqual([])
  })

  it('declares every source used by a layer', () => {
    const declared = new Set(mapConfig.sources.map((source) => source.id))
    const used = new Set(mapConfig.layers.map((layer) => layer.source.id))
    expect([...used].filter((id) => !declared.has(id))).toEqual([])
  })

  it('lists every group layer in mapConfig.layers', () => {
    const known = new Set(mapConfig.layers.map((layer) => layer.layer.id))
    const missing = layerGroups
      .flatMap((group) => group.layers)
      .map((layer) => layer.layer.id)
      .filter((id) => !known.has(id))
    expect(missing).toEqual([])
  })
})
