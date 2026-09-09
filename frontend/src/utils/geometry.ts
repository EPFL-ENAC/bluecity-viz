/**
 * Flat geometry on screen pixels, for the selection tools.
 *
 * The lasso and the brush are drawn in pixels and the streets are projected
 * into pixels before the test, so everything here is plain 2D maths. No
 * geodesy, no library: the map has already done the projection.
 */

/** A point in screen pixels. */
export type Pt = [number, number]

/** The box that holds the points, grown by `pad` on every side. */
export function bbox(points: Pt[], pad = 0): [Pt, Pt] {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  for (const [x, y] of points) {
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
  }

  return [
    [minX - pad, minY - pad],
    [maxX + pad, maxY + pad]
  ]
}

/** Ray casting: count the polygon edges a ray to the right crosses. */
export function pointInPolygon(point: Pt, polygon: Pt[]): boolean {
  if (polygon.length < 3) return false
  const [x, y] = point
  let inside = false

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    const crosses = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
    if (crosses) inside = !inside
  }

  return inside
}

/** Which side of o->a the point b falls on. Zero when the three are in line. */
function cross(o: Pt, a: Pt, b: Pt): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
}

/** For a point already known to be in line with a-b: is it between them? */
function between(a: Pt, b: Pt, p: Pt): boolean {
  return (
    Math.min(a[0], b[0]) <= p[0] &&
    p[0] <= Math.max(a[0], b[0]) &&
    Math.min(a[1], b[1]) <= p[1] &&
    p[1] <= Math.max(a[1], b[1])
  )
}

/** Do the two segments touch? Touching at one end counts. */
export function segmentsIntersect(a: Pt, b: Pt, c: Pt, d: Pt): boolean {
  const d1 = cross(a, b, c)
  const d2 = cross(a, b, d)
  const d3 = cross(c, d, a)
  const d4 = cross(c, d, b)

  const straddles =
    ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
  if (straddles) return true

  if (d1 === 0 && between(a, b, c)) return true
  if (d2 === 0 && between(a, b, d)) return true
  if (d3 === 0 && between(c, d, a)) return true
  if (d4 === 0 && between(c, d, b)) return true
  return false
}

/**
 * Is any part of the line inside the polygon?
 *
 * A street counts when one of its points falls inside, and also when it only
 * crosses the lasso from one side to the other with both ends outside.
 */
export function polylineIntersectsPolygon(line: Pt[], polygon: Pt[]): boolean {
  if (line.length === 0 || polygon.length < 3) return false

  for (const point of line) {
    if (pointInPolygon(point, polygon)) return true
  }

  for (let i = 1; i < line.length; i++) {
    for (let j = 0, k = polygon.length - 1; j < polygon.length; k = j++) {
      if (segmentsIntersect(line[i - 1], line[i], polygon[k], polygon[j])) return true
    }
  }

  return false
}

/** How far the point is from the segment, the ends included. */
export function pointToSegmentDistance(point: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const length = dx * dx + dy * dy
  if (length === 0) return Math.hypot(point[0] - a[0], point[1] - a[1])

  const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length))
  return Math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))
}

/** The gap between two segments, zero when they touch. */
export function segmentsDistance(a: Pt, b: Pt, c: Pt, d: Pt): number {
  if (segmentsIntersect(a, b, c, d)) return 0
  return Math.min(
    pointToSegmentDistance(a, c, d),
    pointToSegmentDistance(b, c, d),
    pointToSegmentDistance(c, a, b),
    pointToSegmentDistance(d, a, b)
  )
}

/**
 * Does the line pass under the brush as it moves from c0 to c1?
 *
 * The brush is tested against the whole step, not against the two ends, so a
 * fast stroke leaves no gap between two samples.
 */
export function polylineNearSegment(line: Pt[], c0: Pt, c1: Pt, radius: number): boolean {
  if (line.length === 0) return false
  if (line.length === 1) return pointToSegmentDistance(line[0], c0, c1) <= radius

  for (let i = 1; i < line.length; i++) {
    if (segmentsDistance(line[i - 1], line[i], c0, c1) <= radius) return true
  }
  return false
}
