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
    rows.push({ mark: 'dashed', label: 'Closed edge' })
    rows.push({ mark: 'arrows', label: 'Speed limit · arrows = direction' })
  }

  rows.push({ mark: 'accent', label: 'Hover / selection' })
  rows.push({ mark: 'lanes', label: 'Two lanes = two directed edges' })

  return rows
}
