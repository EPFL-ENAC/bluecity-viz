import { graphLegendRows } from '@/utils/graphLegend'
import { describe, expect, it } from 'vitest'

describe('graphLegendRows', () => {
  it('names the graph, the pointer and the lanes with no modification', () => {
    const rows = graphLegendRows({ mode: 'scenario', hasModifications: false })
    expect(rows.map((row) => row.mark)).toEqual(['hairline', 'accent', 'lanes'])
    expect(rows[0].label).toBe('Street graph · unaffected')
  })

  it('adds the closed and the speed rows once a street is modified', () => {
    const rows = graphLegendRows({ mode: 'scenario', hasModifications: true })
    expect(rows.map((row) => row.mark)).toEqual(['hairline', 'dashed', 'arrows', 'accent', 'lanes'])
    expect(rows[1].label).toBe('Closed edge')
    expect(rows[2].label).toBe('Speed limit · arrows = direction')
  })

  it('says what the shape means in result mode, where colour owns the stroke', () => {
    const rows = graphLegendRows({ mode: 'result', hasModifications: true })
    expect(rows.map((row) => row.mark)).toEqual(['hairline', 'dashed', 'arrows', 'accent', 'lanes'])
    expect(rows[1].label).toBe('Closed · no traffic')
    expect(rows[2].label).toBe('Speed limit · ink arrows on colour')
  })
})
