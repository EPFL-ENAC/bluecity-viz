// Path helpers for the traffic analysis overlay.
//
// Coordinates are [lon, lat] pairs. Offsets are given in meters and converted
// to degrees with a fixed factor for Lausanne (latitude ~46).

/** meters per degree of latitude */
const METERS_PER_DEGREE_LAT = 111000
/** meters per degree of longitude at latitude ~46 */
const METERS_PER_DEGREE_LON = 77000

export type Point = number[]

export interface HullOutline {
  /** the path offset to the left, half the width away */
  left: Point[]
  /** the path offset to the right */
  right: Point[]
  /** the short line closing the hull at the start */
  startCap: Point[]
  /** the short line closing the hull at the end */
  endCap: Point[]
  /** the point half way along the path, where the icon goes */
  midpoint: [number, number]
}

/** The point half way along the path, measured along the segments. */
export function getPathMidpoint(coordinates: Point[]): [number, number] {
  if (coordinates.length === 0) return [0, 0]
  if (coordinates.length === 1) return [coordinates[0][0], coordinates[0][1]]

  let totalLength = 0
  const segmentLengths: number[] = []

  for (let i = 1; i < coordinates.length; i++) {
    const dx = coordinates[i][0] - coordinates[i - 1][0]
    const dy = coordinates[i][1] - coordinates[i - 1][1]
    const len = Math.sqrt(dx * dx + dy * dy)
    segmentLengths.push(len)
    totalLength += len
  }

  const halfLength = totalLength / 2
  let accumulated = 0

  for (let i = 0; i < segmentLengths.length; i++) {
    if (accumulated + segmentLengths[i] >= halfLength) {
      const ratio = segmentLengths[i] > 0 ? (halfLength - accumulated) / segmentLengths[i] : 0
      const x = coordinates[i][0] + ratio * (coordinates[i + 1][0] - coordinates[i][0])
      const y = coordinates[i][1] + ratio * (coordinates[i + 1][1] - coordinates[i][1])
      return [x, y]
    }
    accumulated += segmentLengths[i]
  }

  const last = coordinates[coordinates.length - 1]
  return [last[0], last[1]]
}

/**
 * A line parallel to the given one, offsetMeters away. Positive is to the left
 * of the direction of travel, negative to the right.
 */
export function computeOffsetPath(coordinates: Point[], offsetMeters: number): Point[] {
  if (coordinates.length < 2) return coordinates

  const offsetPath: Point[] = []

  for (let i = 0; i < coordinates.length; i++) {
    let nx = 0
    let ny = 0

    if (i === 0) {
      // first point: the normal of the first segment
      const dx = coordinates[1][0] - coordinates[0][0]
      const dy = coordinates[1][1] - coordinates[0][1]
      const len = Math.sqrt(dx * dx + dy * dy)
      if (len > 0) {
        nx = -dy / len
        ny = dx / len
      }
    } else if (i === coordinates.length - 1) {
      // last point: the normal of the last segment
      const dx = coordinates[i][0] - coordinates[i - 1][0]
      const dy = coordinates[i][1] - coordinates[i - 1][1]
      const len = Math.sqrt(dx * dx + dy * dy)
      if (len > 0) {
        nx = -dy / len
        ny = dx / len
      }
    } else {
      // middle points: the average of the two normals
      const dx1 = coordinates[i][0] - coordinates[i - 1][0]
      const dy1 = coordinates[i][1] - coordinates[i - 1][1]
      const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1)

      const dx2 = coordinates[i + 1][0] - coordinates[i][0]
      const dy2 = coordinates[i + 1][1] - coordinates[i][1]
      const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2)

      if (len1 > 0 && len2 > 0) {
        const nx1 = -dy1 / len1
        const ny1 = dx1 / len1
        const nx2 = -dy2 / len2
        const ny2 = dx2 / len2
        nx = (nx1 + nx2) / 2
        ny = (ny1 + ny2) / 2
        const nlen = Math.sqrt(nx * nx + ny * ny)
        if (nlen > 0) {
          nx /= nlen
          ny /= nlen
        }
      }
    }

    const offsetLon = (offsetMeters / METERS_PER_DEGREE_LON) * nx
    const offsetLat = (offsetMeters / METERS_PER_DEGREE_LAT) * ny

    offsetPath.push([coordinates[i][0] + offsetLon, coordinates[i][1] + offsetLat])
  }

  return offsetPath
}

/** The two sides of the hull around a path, widthMeters apart. */
export function createHullPaths(coordinates: Point[], widthMeters: number): Point[][] {
  const halfWidth = widthMeters / 2
  return [computeOffsetPath(coordinates, halfWidth), computeOffsetPath(coordinates, -halfWidth)]
}

/**
 * The full outline of a modified edge: both sides, the two end caps and the
 * midpoint for the icon. Computed in one go so the caller does not walk the
 * path several times.
 */
export function createHullOutline(coordinates: Point[], widthMeters: number): HullOutline {
  const [left, right] = createHullPaths(coordinates, widthMeters)
  const midpoint = getPathMidpoint(coordinates)

  if (coordinates.length < 2) {
    return { left, right, startCap: [], endCap: [], midpoint }
  }

  return {
    left,
    right,
    startCap: [left[0], right[0]],
    endCap: [left[left.length - 1], right[right.length - 1]],
    midpoint
  }
}
