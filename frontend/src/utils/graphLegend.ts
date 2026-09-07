/**
 * The key to the graph vocabulary, shown under the data ramp.
 *
 * The map says three things at once, so the legend names them: the graph is a
 * grey hairline, the data is colour and width, a modification is ink and shape.
 * The accent blue is only the pointer, never a value.
 */

export type GraphMapMode = 'scenario' | 'result'

/** How the sample on the left of a row is drawn. */
export type GraphLegendMark =
  | 'hairline'
  | 'dashed'
  | 'arrows'
  | 'accent'
  | 'lanes'

export interface GraphLegendRow {
  mark: GraphLegendMark
  label: string
}

export interface GraphLegendOptions {
  mode: GraphMapMode
  /** the two modification rows only make sense once there is one */
  hasModifications: boolean
}

export function graphLegendRows(options: GraphLegendOptions): GraphLegendRow[] {
  const rows: GraphLegendRow[] = [{ mark: 'hairline', label: 'Street graph · unaffected' }]

  if (options.hasModifications) {
    // In result mode the colour owns the stroke, so the two rows say what the
    // shape means there instead of what it means on the ink scenario.
    const result = options.mode === 'result'
    rows.push({ mark: 'dashed', label: result ? 'Closed · no traffic' : 'Closed edge' })
    rows.push({
      mark: 'arrows',
      label: result ? 'Speed limit · ink arrows on colour' : 'Speed limit · arrows = direction'
    })
  }

  rows.push({ mark: 'accent', label: 'Hover / selection' })
  rows.push({ mark: 'lanes', label: 'Two lanes = two directed edges' })

  return rows
}
