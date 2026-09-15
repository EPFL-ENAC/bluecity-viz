/**
 * Short numbers for the impact table: the unit grows with the value, so a
 * number never has more than 3 or 4 digits.
 */

/** "4.2" under 10, "42" above, "4.2k" from 1000. No sign. */
function digits(abs: number): string {
  if (abs >= 1000) return `${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`
  return abs < 10 ? abs.toFixed(1).replace(/\.0$/, '') : abs.toFixed(0)
}

function signed(value: number, unit: string): string {
  const text = digits(Math.abs(value))
  if (text === '0') return `0 ${unit}`
  return `${value > 0 ? '+' : '-'}${text} ${unit}`
}

/** Kilometres, as m under 1 km. */
export function formatDistance(km: number): string {
  if (Math.abs(km) < 1) return signed(km * 1000, 'm')
  return signed(km, 'km')
}

/** Minutes, as s under 1 min and h from 1 h. */
export function formatTime(minutes: number): string {
  const abs = Math.abs(minutes)
  if (abs < 1) return signed(minutes * 60, 's')
  if (abs < 60) return signed(minutes, 'min')
  return signed(minutes / 60, 'h')
}

/** Grams, as kg from 1 kg and t from 1 t. */
export function formatCo2(grams?: number): string {
  if (grams == null) return '—'
  const abs = Math.abs(grams)
  if (abs < 1000) return signed(grams, 'g')
  if (abs < 1_000_000) return signed(grams / 1000, 'kg')
  return signed(grams / 1_000_000, 't')
}

/** A count of people, "13.6k" from 1000. */
export function formatCount(count: number): string {
  if (count < 1000) return String(Math.round(count))
  return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}k`
}
