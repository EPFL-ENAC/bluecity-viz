/**
 * The Swiss communes, what the picker needs to know before the server answers.
 *
 * The processing pipeline writes one small file with, for every commune, its
 * name, its bbox and the communes it shares a border with (build_municipalities.py).
 * With it the picker names the selection, frames the camera on it and tells
 * right away when the communes do not touch. The exact answer (counts,
 * connectivity, the outline) still comes from POST /areas/preview.
 */

import { baseUrl } from '@/config/layerTypes'
import { normaliseIds } from '@/services/trafficAnalysis'
import { useApiKeyStore } from '@/stores/apiKey'

const isDev = import.meta.env.DEV

/** The longest name an area gets, same cut as the backend and the dock. */
export const MAX_LABEL = 60

export interface CommuneEntry {
  name: string
  /** the BFS numbers of the communes it shares a border with */
  nb: number[]
  /** [minLon, minLat, maxLon, maxLat] */
  bbox: [number, number, number, number]
}

export interface CommuneIndex {
  format_version: number
  source: string
  /** by BFS number, as a string: JSON keys are strings */
  communes: Record<string, CommuneEntry>
}

function indexUrl(): string {
  const url = `${baseUrl}/swiss_communes.json`
  if (isDev) return url
  return `${url}?apikey=${useApiKeyStore().apiKey}`
}

let cached: Promise<CommuneIndex | null> | null = null

/**
 * The file, fetched once per session. null when the deployment has none, and
 * then the picker waits for the server on every click.
 */
export function loadMunicipalities(): Promise<CommuneIndex | null> {
  if (!cached) {
    cached = fetch(indexUrl())
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null)
      .then((data: CommuneIndex | null) => {
        if (!data || !data.communes || typeof data.communes !== 'object') return null
        return data
      })
  }
  return cached
}

/** Tests only. */
export function resetMunicipalities(): void {
  cached = null
}

/**
 * Do these communes form one region, border to border.
 *
 * True for a single commune, false for none. An id the index does not know
 * counts as apart: the server would refuse it anyway.
 */
export function contiguous(ids: readonly number[], index: CommuneIndex): boolean {
  const wanted = new Set(ids)
  if (wanted.size === 0) return false
  for (const id of wanted) {
    if (!index.communes[id]) return false
  }

  const start = wanted.values().next().value as number
  const seen = new Set([start])
  const queue = [start]
  while (queue.length) {
    const here = queue.shift() as number
    for (const there of index.communes[here].nb) {
      if (wanted.has(there) && !seen.has(there)) {
        seen.add(there)
        queue.push(there)
      }
    }
  }
  return seen.size === wanted.size
}

/** The box around the communes, null when none is known. */
export function municipalityBbox(
  ids: readonly number[],
  index: CommuneIndex
): [number, number, number, number] | null {
  let box: [number, number, number, number] | null = null
  for (const id of ids) {
    const entry = index.communes[id]
    if (!entry) continue
    const [minLon, minLat, maxLon, maxLat] = entry.bbox
    box = box
      ? [
          Math.min(box[0], minLon),
          Math.min(box[1], minLat),
          Math.max(box[2], maxLon),
          Math.max(box[3], maxLat)
        ]
      : [minLon, minLat, maxLon, maxLat]
  }
  return box
}

/** "Lausanne", "Lausanne + Pully", "Lausanne, Pully + 2 more". Same as the backend. */
export function areaLabelOf(names: readonly string[]): string {
  if (names.length === 0) return ''
  let text: string
  if (names.length === 1) text = names[0]
  else if (names.length === 2) text = `${names[0]} + ${names[1]}`
  else text = `${names[0]}, ${names[1]} + ${names.length - 2} more`
  if (text.length > MAX_LABEL) text = text.slice(0, MAX_LABEL - 1).trimEnd() + '…'
  return text
}

/**
 * The name of a selection, in the order of the area id, so the same communes
 * always get the same name. Unknown ids are skipped.
 */
export function municipalityLabel(ids: readonly number[], index: CommuneIndex): string {
  const names = normaliseIds(ids)
    .map((id) => index.communes[id]?.name)
    .filter((name): name is string => !!name)
  return areaLabelOf(names)
}

/** The name of one commune, or its number when the index does not know it. */
export function communeName(id: number, index: CommuneIndex | null): string {
  return index?.communes[id]?.name ?? `Municipality ${id}`
}
