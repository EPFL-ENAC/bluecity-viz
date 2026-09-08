/**
 * A stable fingerprint of a scenario.
 *
 * Two tools run on the same modified graph and cache their result. A result is
 * stale when the scenario changed since it ran, so we need a value that is the
 * same for the same set of modifications, whatever order they were made in.
 */

/** One line per modification, sorted, so the order of edits does not matter. */
export function scenarioSignature(
  entries: Iterable<[string, { action: string; dir: string }]>
): string {
  const lines: string[] = []
  for (const [key, mod] of entries) {
    lines.push(`${key}:${mod.action}:${mod.dir}`)
  }
  return lines.sort().join('|')
}

/** FNV-1a, 32 bits, as 8 hex chars. Short, fast, and good enough to compare. */
export function fnv1a32(text: string): string {
  let hash = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i)
    // hash * 16777619 without overflowing to a float
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

export function scenarioHash(entries: Iterable<[string, { action: string; dir: string }]>): string {
  return fnv1a32(scenarioSignature(entries))
}
