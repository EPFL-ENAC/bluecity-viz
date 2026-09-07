/**
 * The street graph as a MapLibre source.
 *
 * The app knows the network as a list of directed edges: a two-way street is
 * two features, `(u,v)` and `(v,u)`, with reversed coordinates. That is exactly
 * what the design asks to draw, one lane per directed edge, so the source keeps
 * the features as they are and each one is offset to its own right.
 *
 * Everything here is pure: it turns the fetched edges into a FeatureCollection
 * plus two lookups, and it never touches a map.
 */
import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { streetKey, type Street } from '@/stores/scenario'

// Only the GeoJSON shapes we build. @types/geojson is not a dependency here,
// and MapLibre takes a plain object anyway.
export interface LineFeature {
  type: 'Feature'
  id: number
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  properties: Record<string, string | number | null>
}

export interface LineCollection {
  type: 'FeatureCollection'
  features: LineFeature[]
}

/** Width factor per road class, from the design (primary 1.6 … minor .7). */
const CLASS_FACTOR: Record<string, number> = {
  motorway: 1.6,
  motorway_link: 1.6,
  trunk: 1.6,
  trunk_link: 1.6,
  primary: 1.6,
  primary_link: 1.6,
  secondary: 1.3,
  secondary_link: 1.3,
  tertiary: 1,
  tertiary_link: 1,
  busway: 1
}

/** What the hover card shows instead of the raw OSM value. */
const CLASS_LABEL: Record<number, string> = {
  1.6: 'PRIMARY',
  1.3: 'SECONDARY',
  1: 'TERTIARY',
  0.7: 'MINOR'
}

export function classFactor(highway?: string): number {
  if (!highway) return 0.7
  return CLASS_FACTOR[highway] ?? 0.7
}

export function classLabel(highway?: string): string {
  return CLASS_LABEL[classFactor(highway)] ?? 'MINOR'
}

/** The point halfway along the path, by length. The badge sits there. */
export function pathMidpoint(coordinates: [number, number][]): [number, number] {
  if (coordinates.length === 0) return [0, 0]
  if (coordinates.length === 1) return coordinates[0]

  let total = 0
  const spans: number[] = []
  for (let i = 1; i < coordinates.length; i++) {
    const dx = coordinates[i][0] - coordinates[i - 1][0]
    const dy = coordinates[i][1] - coordinates[i - 1][1]
    const span = Math.hypot(dx, dy)
    spans.push(span)
    total += span
  }
  if (total === 0) return coordinates[0]

  let walked = 0
  const half = total / 2
  for (let i = 0; i < spans.length; i++) {
    if (walked + spans[i] >= half) {
      const t = spans[i] === 0 ? 0 : (half - walked) / spans[i]
      const a = coordinates[i]
      const b = coordinates[i + 1]
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    }
    walked += spans[i]
  }
  return coordinates[coordinates.length - 1]
}

export interface GraphSource {
  collection: LineCollection
  /** street key -> both of its directed edges */
  streets: Map<string, Street>
  /** feature id -> the directed edge it draws */
  edgeById: Map<number, EdgeGeometry>
  /** node -> the street names that meet there, for the popover labels */
  nodeStreets: Map<number, string[]>
}

function sameCoordinates(a: [number, number][], b: [number, number][]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (a[i][0] !== b[i][0] || a[i][1] !== b[i][1]) return false
  }
  return true
}

/**
 * Build the source once, when the network lands.
 *
 * `side` says which way to offset the lane. Normally the reverse edge has
 * reversed coordinates, so offsetting every feature to its own right already
 * puts the two lanes on opposite sides. A handful of reverse edges are stored
 * with the *same* coordinates as their twin; those get side −1 so the pair
 * still splits instead of drawing on top of each other.
 */
export function buildGraphSource(edges: EdgeGeometry[]): GraphSource {
  const byKey = new Map<string, EdgeGeometry>()
  for (const edge of edges) {
    const key = `${edge.u}-${edge.v}`
    if (!byKey.has(key)) byKey.set(key, edge)
  }

  const collection: LineCollection = { type: 'FeatureCollection', features: [] }
  const streets = new Map<string, Street>()
  const edgeById = new Map<number, EdgeGeometry>()
  const nodeStreets = new Map<number, string[]>()

  edges.forEach((edge, index) => {
    const { u, v } = edge
    const reverse = u === v ? undefined : byKey.get(`${v}-${u}`)
    const oneway = reverse === undefined
    const key = streetKey(u, v)
    const forward = u <= v

    // A reverse twin stored with identical coordinates would draw on the same
    // lane, so push it to the other side.
    const side =
      !oneway && !forward && reverse && sameCoordinates(edge.coordinates, reverse.coordinates)
        ? -1
        : 1

    const name = edge.name && edge.name !== 'Unknown' ? edge.name : ''
    const cls = classFactor(edge.highway)

    collection.features.push({
      type: 'Feature',
      id: index,
      geometry: { type: 'LineString', coordinates: edge.coordinates },
      properties: {
        u,
        v,
        sk: key,
        name,
        cls,
        two: oneway ? 0 : 1,
        side,
        speed: edge.speed_kph ?? null,
        bus: (edge.bus_route_count ?? 0) > 0 ? 1 : 0,
        len: edge.length ?? 0
      }
    })

    edgeById.set(index, edge)

    const street = streets.get(key)
    if (!street) {
      streets.set(key, {
        key,
        lo: Math.min(u, v),
        hi: Math.max(u, v),
        name,
        fwdId: forward ? index : undefined,
        bwdId: forward ? undefined : index,
        oneway,
        at: pathMidpoint(edge.coordinates),
        cls,
        speed: edge.speed_kph,
        bus: (edge.bus_route_count ?? 0) > 0
      })
    } else {
      // the other direction of a street we have already seen
      if (forward && street.fwdId === undefined) street.fwdId = index
      if (!forward && street.bwdId === undefined) street.bwdId = index
      street.oneway = street.fwdId === undefined || street.bwdId === undefined
      if (!street.name && name) street.name = name
      if ((edge.bus_route_count ?? 0) > 0) street.bus = true
    }

    if (name) {
      for (const node of [u, v]) {
        const names = nodeStreets.get(node)
        if (!names) nodeStreets.set(node, [name])
        else if (!names.includes(name)) names.push(name)
      }
    }
  })

  return { collection, streets, edgeById, nodeStreets }
}

/**
 * Which side of the travel direction a point falls on, in screen pixels.
 *
 * Screen y grows downward, so a positive cross product means the point is to
 * the right of the way. That is the lane a right-hand-traffic driver uses, so
 * it is the directed edge the user meant when shift-clicking.
 */
export function sideOfTravel(
  a: [number, number],
  b: [number, number],
  point: [number, number]
): number {
  const cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
  if (cross === 0) return 0
  return cross > 0 ? 1 : -1
}

/**
 * The lane the cursor is on: 'fwd' when it sits right of the lo -> hi
 * direction, 'bwd' otherwise. `project` turns a coordinate into screen pixels.
 */
export function pickLane(
  coordinates: [number, number][],
  cursor: [number, number],
  project: (position: [number, number]) => [number, number],
  forwardGeometry = true
): 'fwd' | 'bwd' {
  if (coordinates.length < 2) return 'fwd'

  // the segment whose midpoint is nearest the cursor
  let bestIndex = 0
  let bestDistance = Infinity
  const projected = coordinates.map(project)

  for (let i = 1; i < projected.length; i++) {
    const mx = (projected[i - 1][0] + projected[i][0]) / 2
    const my = (projected[i - 1][1] + projected[i][1]) / 2
    const distance = Math.hypot(mx - cursor[0], my - cursor[1])
    if (distance < bestDistance) {
      bestDistance = distance
      bestIndex = i
    }
  }

  const side = sideOfTravel(projected[bestIndex - 1], projected[bestIndex], cursor)
  // The geometry may be the hi -> lo feature, in which case right of *that*
  // way is the bwd lane of the street.
  const rightIsForward = forwardGeometry
  if (side === 0) return 'fwd'
  return side > 0 === rightIsForward ? 'fwd' : 'bwd'
}
