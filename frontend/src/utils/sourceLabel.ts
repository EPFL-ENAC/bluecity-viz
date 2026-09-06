/**
 * Source labels are written "<Domain> - <SPn>", for example
 * "Urban Accessibility Atlas - SP2". The Add sources dialog shows the SP code
 * in its own column, so the suffix is stripped from the name.
 */
export interface SplitSourceLabel {
  name: string
  /** the SP code, or an em dash when the source has none */
  sp: string
}

const SP_SUFFIX = /\s-\sSP(\d+)$/

export function splitSourceLabel(label: string): SplitSourceLabel {
  const match = label.match(SP_SUFFIX)
  if (match) {
    return { name: label.replace(SP_SUFFIX, ''), sp: `SP${match[1]}` }
  }
  // "Habitat Density - Biodiversity" has no SP code, keep the qualifier in the
  // name so nothing is lost.
  const dash = label.lastIndexOf(' - ')
  if (dash > 0) {
    const name = label.slice(0, dash)
    const qualifier = label.slice(dash + 3)
    return { name: `${name} (${qualifier})`, sp: '—' }
  }
  return { name: label, sp: '—' }
}
