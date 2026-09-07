import { buildPaint, colorKey, defineGroup, defineLayer } from '@/config/defineLayer'
import type { CustomSourceSpecification } from '@/config/layerTypes'
import { describe, expect, it } from 'vitest'

const source: CustomSourceSpecification = {
  type: 'vector',
  id: 'test_source',
  label: 'Test source',
  url: 'pmtiles:///geodata/test.pmtiles'
}

describe('buildPaint', () => {
  it('builds the same interpolate ramp as a hand written one', () => {
    expect(
      buildPaint({
        kind: 'sequential',
        property: 'pop_mean',
        domain: [200, 400],
        scheme: ['#e3f2fd', '#90caf9']
      })
    ).toEqual([
      'interpolate',
      ['linear'],
      ['to-number', ['get', 'pop_mean']],
      200,
      '#e3f2fd',
      400,
      '#90caf9'
    ])
  })

  it('builds the same match expression as a hand written one', () => {
    expect(
      buildPaint({
        kind: 'categorical',
        property: 'Era',
        categories: [
          { value: 'Before 1919', color: '#440154' },
          { value: 'After 2015', color: '#fde725' }
        ],
        defaultColor: '#bdbdbd'
      })
    ).toEqual([
      'match',
      ['get', 'Era'],
      'Before 1919',
      '#440154',
      'After 2015',
      '#fde725',
      '#bdbdbd'
    ])
  })

  it('refuses a ramp with as many colours as stops missing', () => {
    expect(() =>
      buildPaint({ kind: 'sequential', property: 'x', domain: [1, 2], scheme: ['#000'] })
    ).toThrow(/stops/)
  })

  it('refuses a ramp with one stop', () => {
    expect(() =>
      buildPaint({ kind: 'sequential', property: 'x', domain: [1], scheme: ['#000'] })
    ).toThrow(/two stops/)
  })

  it('refuses a match with no category', () => {
    expect(() =>
      buildPaint({ kind: 'categorical', property: 'x', categories: [], defaultColor: '#000' })
    ).toThrow(/category/)
  })
})

describe('colorKey', () => {
  it('knows the colour property of each layer type', () => {
    expect(colorKey('fill')).toBe('fill-color')
    expect(colorKey('line')).toBe('line-color')
    expect(colorKey('circle')).toBe('circle-color')
    expect(colorKey('fill-extrusion')).toBe('fill-extrusion-color')
    expect(colorKey('symbol')).toBeNull()
  })
})

describe('defineLayer', () => {
  it('fills the layer id and the source id', () => {
    const layer = defineLayer({
      id: 'test_layer',
      label: 'Test',
      unit: 'm',
      info: 'info',
      source,
      layer: { type: 'fill', 'source-layer': 'test', paint: { 'fill-color': '#000' } }
    })
    expect(layer.layer.id).toBe('test_layer-layer')
    expect((layer.layer as { source?: string }).source).toBe('test_source')
    expect(layer.source).toBe(source)
  })

  it('keeps an explicit layer id', () => {
    const layer = defineLayer({
      id: 'test_layer',
      label: 'Test',
      unit: 'm',
      info: 'info',
      source,
      layer: { id: 'other-id', type: 'fill', 'source-layer': 'test' }
    })
    expect(layer.layer.id).toBe('other-id')
  })

  it('writes the colour from the encoding and keeps the other paint keys', () => {
    const layer = defineLayer({
      id: 'test_layer',
      label: 'Test',
      unit: 'm',
      info: 'info',
      source,
      encoding: { kind: 'sequential', property: 'v', domain: [0, 1], scheme: ['#000', '#fff'] },
      layer: { type: 'fill', 'source-layer': 'test', paint: { 'fill-opacity': 0.8 } }
    })
    const paint = layer.layer.paint as Record<string, unknown>
    expect(paint['fill-color']).toEqual([
      'interpolate',
      ['linear'],
      ['to-number', ['get', 'v']],
      0,
      '#000',
      1,
      '#fff'
    ])
    expect(paint['fill-opacity']).toBe(0.8)
    expect(layer.encoding).toBeDefined()
  })

  it('leaves the layer without encoding alone', () => {
    const layer = defineLayer({
      id: 'test_layer',
      label: 'Test',
      unit: 'm',
      info: 'info',
      source,
      layer: { type: 'line', 'source-layer': 'test', paint: { 'line-color': '#000000' } }
    })
    expect(layer.encoding).toBeUndefined()
    expect((layer.layer.paint as Record<string, unknown>)['line-color']).toBe('#000000')
  })

  it('refuses a colour set twice', () => {
    expect(() =>
      defineLayer({
        id: 'test_layer',
        label: 'Test',
        unit: 'm',
        info: 'info',
        source,
        encoding: { kind: 'sequential', property: 'v', domain: [0, 1], scheme: ['#000', '#fff'] },
        layer: { type: 'fill', 'source-layer': 'test', paint: { 'fill-color': '#123456' } }
      })
    ).toThrow(/set twice/)
  })

  it('refuses an encoding on a layer type with no colour', () => {
    expect(() =>
      defineLayer({
        id: 'test_layer',
        label: 'Test',
        unit: 'm',
        info: 'info',
        source,
        encoding: { kind: 'sequential', property: 'v', domain: [0, 1], scheme: ['#000', '#fff'] },
        layer: { type: 'heatmap', 'source-layer': 'test' }
      })
    ).toThrow(/no colour encoding/)
  })
})

describe('defineGroup', () => {
  it('is closed by default', () => {
    expect(defineGroup({ id: 'g', label: 'G', multiple: false, layers: [] })).toEqual({
      id: 'g',
      label: 'G',
      multiple: false,
      expanded: false,
      layers: []
    })
  })
})
