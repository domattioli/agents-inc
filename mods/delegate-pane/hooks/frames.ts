// Spec 039 motion: the terminal Raster frames of the mission map. Pure: (stations, returns, dispatches, time, size) -> cells.
// No engine nouns. Vertical layout (2026-11-12): one spine down the left third of the pane: the CoS (the main session) at
// the top, the Lead hub in the middle, the primary Worker hub below it, so the map fits a narrow pane. Six task stations
// stand in a column on each side of the spine: Plan, Scout, Write on the left, Other, Review, Build on the right. Permanent
// lines: a thin spoke from the Lead down or up the spine to the station's row, then across (one bend), and the CoS-Lead
// link while a Lead exists. Hub labels sit to the right of their node. The Lead and the primary Worker show only on their
// hubs, never again under their station (the station stays lit). Every other line is a real event drawn only while its
// pulse travels: a dispatch when a delegate starts, a result when it ends, each along the route of whoever started it
// (routeOf): Lead spokes, the CoS-Lead link, a CoS-to-station edge for a delegate the main session started while a Lead
// runs, or a station-to-station curve for a child of a non-Lead delegate. Results go back to the starter; only the Lead,
// or a delegate the CoS started, reaches the CoS. Running delegates on Lead spokes send a heartbeat pulse every SEND_MS;
// nothing else repeats. A station with an unacknowledged failure holds a steady red mark and its count. Palette: one
// activity colour, pale grey for event edges, red for failure. Motion design after lot-map
// (https://github.com/alexeyw/lot-map, MIT); no code or art reused.
import { hierarchy } from './mission'
import type { Category, Delegate, Hierarchy, State, Station } from './mission'

// 12.5 frames a second.
export const FRAME_MS = 80
// An outward pulse crosses its route in ROUTE_MS; each running delegate on a Lead spoke sends one every SEND_MS.
export const ROUTE_MS = 600
export const SEND_MS = 2400
// A return pulse crosses in RETURN_MS; a ripple where a pulse lands lasts RIPPLE_MS.
export const RETURN_MS = 600
export const RIPPLE_MS = 400
// A dispatch event (pulse and ripple) lasts EVENT_MS after the delegate starts.
export const EVENT_MS = ROUTE_MS + RIPPLE_MS
export const PULSE_CAP = 3
export const TRAIL = 3
export const RASTER_ROWS = 16
export const RASTER_MAX_COLUMNS = 56
export const RASTER_MIN_COLUMNS = 34

const DEFAULT = 0x01000000
const BLANK = 0x20
const GLYPH = { hub: 0x25c9, lit: 0x25cf, idle: 0x25cb, paused: 0x25d0, done: 0x2713, alert: 0x2717 }

// Colours: a hue at a level 0..7 (0 faint, 7 full). Five hues times eight levels keeps a frame far under 1024 pairs.
export type Hue = 'edge' | 'work' | 'arc' | 'alert' | 'text'
const FULL: Record<Hue, [number, number, number]> = {
  edge: [120, 124, 136], work: [240, 172, 72], arc: [205, 208, 218], alert: [235, 80, 72], text: [228, 228, 232],
}
const FAINT: [number, number, number] = [34, 36, 42]
export function colour(hue: Hue, level: number): number {
  const f = Math.max(0, Math.min(7, Math.round(level))) / 7
  const [r, g, b] = FULL[hue].map((c, i) => Math.round(FAINT[i]! + (c - FAINT[i]!) * f))
  return (r! << 16) | (g! << 8) | b!
}

const working = (s: State | undefined) => s === 'running' || s === 'review'

// Who started a delegate, and so the line its dispatch and result travel (delegation model, Chains):
// up: the Lead itself, on the CoS-Lead link (CoS dispatches only the Lead; Lead reports to CoS).
// spoke: a child of the Lead, or any delegate when there is no Lead (the main session then does the Lead's job).
// cos: no parent while a Lead exists: the main session started it itself; it reports straight to the CoS.
// child: a child of a delegate that is not the Lead (Workhorse -> Grunt), on a curve between the two stations.
// none: a parent that is not on the map, or parent and child on one station: nothing is drawn, no relation invented.
export type Route = { kind: 'up' | 'spoke' | 'cos' | 'child' | 'none'; parent?: Category }
export function routeOf(d: Delegate, all: Delegate[], h: Hierarchy = hierarchy(all)): Route {
  if (h.lead && d.id === h.lead.id) return { kind: 'up' }
  const p = d.parentId ? all.find(x => x.id === d.parentId) : undefined
  if (d.parentId && !p) return { kind: 'none' }
  if (p) {
    if (h.lead && p.id === h.lead.id) return { kind: 'spoke' }
    return p.category === d.category ? { kind: 'none' } : { kind: 'child', parent: p.category }
  }
  return h.lead ? { kind: 'cos' } : { kind: 'spoke' }
}

// A return pulse: delegate `id` on `category` ended at `at` (failed: a failure or lost result).
export type Return = { id: string; category: Category; at: number; failed?: boolean }
// A dispatch event: delegate `id` started at `at`.
export type Dispatch = { id: string; at: number }

// Which delegates ended since the last look: the ones seen working before and done, failed or lost now. Pure; the
// caller keeps `seen` and the returned list. Landed returns and delegates with no drawable route are dropped.
export function landings(seen: Record<string, State>, delegates: Delegate[], returns: Return[], t: number): { seen: Record<string, State>; returns: Return[] } {
  const next: Record<string, State> = {}
  const out = returns.filter(r => t - r.at < RETURN_MS + RIPPLE_MS)
  const h = hierarchy(delegates)
  for (const d of delegates) {
    next[d.id] = d.state
    const ended = d.state === 'done' || d.state === 'failed' || d.state === 'lost'
    if (working(seen[d.id]) && ended && routeOf(d, delegates, h).kind !== 'none')
      out.push({ id: d.id, category: d.category, at: t, ...(d.state === 'done' ? {} : { failed: true }) })
  }
  return { seen: next, returns: out }
}

// The live dispatch events at t: delegates working now that started less than EVENT_MS ago, with a known start and a
// drawable route. A delegate first seen already ended draws no dispatch (and, never seen working, no result).
export function dispatchesOf(delegates: Delegate[], t: number): Dispatch[] {
  const h = hierarchy(delegates)
  return delegates
    .filter(d => working(d.state) && d.startedAt !== undefined && t - d.startedAt >= 0 && t - d.startedAt < EVENT_MS && routeOf(d, delegates, h).kind !== 'none')
    .map(d => ({ id: d.id, at: d.startedAt! }))
}

// Something moves while a running delegate sits on a Lead spoke (its heartbeat), a return is in flight or a dispatch
// event lives. A failure mark, a lit station with only CoS-started work, and the hubs stand still.
export function needsMotion(sts: Station[], returns: Return[] = [], t = 0, dispatches: Dispatch[] = []): boolean {
  const all = sts.flatMap(s => s.delegates)
  const h = hierarchy(all)
  return (
    all.some(d => working(d.state) && routeOf(d, all, h).kind === 'spoke') ||
    returns.some(r => t - r.at >= 0 && t - r.at < RETURN_MS + RIPPLE_MS) ||
    dispatches.some(e => t - e.at >= 0 && t - e.at < EVENT_MS)
  )
}

type Pt = { x: number; y: number }
// Geometry in cells. Fixed whatever the data, so a hub that comes and goes never moves anything. The spine is the column
// `x`: CoS at row 0, Lead at row 5, Worker at row 11. Stations (in the order of mission.CATEGORIES: Review, Build, Write,
// Scout, Plan, Other) stand SPOKE cells off the spine: left Plan 2, Scout 5, Write 8; right Other 2, Review 8, Build 14.
// Scout sits on the Lead row, so its spoke is straight; the others bend once, at the spine. `centre` is the middle of
// the spine (curves bow away from it).
export const SPOKE = 5
const SIDE: Array<['L' | 'R', number]> = [['R', 8], ['R', 14], ['L', 8], ['L', 5], ['L', 2], ['R', 2]]
export function geometry(columns: number): { centre: Pt; cos: Pt; lead: Pt; worker: Pt; stations: Pt[] } {
  const x = Math.max(14, Math.round(columns * 0.3))
  return {
    centre: { x, y: 8 },
    cos: { x, y: 0 },
    lead: { x, y: 5 },
    worker: { x, y: 11 },
    stations: SIDE.map(([side, y]) => ({ x: side === 'R' ? x + SPOKE : x - SPOKE, y })),
  }
}

const dotOf = (c: Pt): Pt => ({ x: c.x * 2 + 1, y: c.y * 4 + 2 })
const inCell = (p: Pt, c: Pt) => Math.floor(p.x / 2) === c.x && Math.floor(p.y / 4) === c.y
function trace(a: Pt | undefined, b: Pt | undefined, at: (t: number) => Pt, n: number): Pt[] {
  const out: Pt[] = []
  for (let k = 0; k <= n; k++) {
    const q = at(k / n)
    const p = { x: Math.round(q.x), y: Math.round(q.y) }
    const last = out[out.length - 1]
    if ((a && inCell(p, a)) || (b && inCell(p, b)) || (last && last.x === p.x && last.y === p.y)) continue
    out.push(p)
  }
  return out
}

// A straight line of braille dots from cell a to cell b, in order from a. Dots inside the two end cells are left out.
export function edge(a: Pt, b: Pt, keepA = false, keepB = false): Pt[] {
  const A = dotOf(a)
  const B = dotOf(b)
  const n = Math.max(Math.abs(B.x - A.x), Math.abs(B.y - A.y))
  return trace(keepA ? undefined : a, keepB ? undefined : b, t => ({ x: A.x + (B.x - A.x) * t, y: A.y + (B.y - A.y) * t }), Math.max(1, n))
}

// A curve between two stations: a quadratic bowed away from the centre of the pair, in order from a to b.
export function arc(a: Pt, b: Pt, centre: Pt): Pt[] {
  const A = dotOf(a)
  const B = dotOf(b)
  const O = dotOf(centre)
  const mx = (A.x + B.x) / 2
  const my = (A.y + B.y) / 2
  // bend sideways by a quarter of the chord or more, to the side away from the centre (either side when the chord crosses it)
  const len = Math.hypot(B.x - A.x, B.y - A.y) || 1
  let px = -(B.y - A.y) / len
  let py = (B.x - A.x) / len
  if (px * (mx - O.x) + py * (my - O.y) < 0) (px = -px), (py = -py)
  // a chord through the centre (opposite stations) bends further, so the arc does not lie along the spokes
  const k = 0.25 + 0.25 * (1 - Math.min(1, Math.hypot(mx - O.x, my - O.y) / (len * 0.5)))
  const C = { x: mx + px * len * k, y: my + py * len * k * 0.6 }
  const n = Math.ceil(Math.hypot(B.x - A.x, B.y - A.y) * 1.6) + 2
  return trace(a, b, t => {
    const u = 1 - t
    return { x: u * u * A.x + 2 * u * t * C.x + t * t * B.x, y: u * u * A.y + 2 * u * t * C.y + t * t * B.y }
  }, n)
}

// The outward pulses of one spoke at t: for each running delegate (at most PULSE_CAP) its send phase; a pulse is on the
// spoke during the first ROUTE_MS of each SEND_MS period and its ripple runs RIPPLE_MS after that. `head` is a dot index
// from the centre, `ripple` the ripple age in ms.
export function pulses(len: number, running: number, t: number, stagger = 0): Array<{ head?: number; ripple?: number }> {
  const n = Math.min(running, PULSE_CAP)
  const out: Array<{ head?: number; ripple?: number }> = []
  for (let k = 0; k < n; k++) {
    const phase = (((t + stagger + (k * SEND_MS) / n) % SEND_MS) + SEND_MS) % SEND_MS
    if (phase < ROUTE_MS) out.push({ head: Math.min(len - 1, Math.floor((phase / ROUTE_MS) * len)) })
    else if (phase < ROUTE_MS + RIPPLE_MS) out.push({ ripple: phase - ROUTE_MS })
  }
  return out
}

// What a station says under or beside its mark: delegate names (working ones, or the newest one when none works) that
// fit in `room` columns, and an `xN` badge when not all of them fit.
export function stationNames(s: Station, room: number, skip: ReadonlySet<string> = new Set()): string {
  const ds = s.delegates.filter(d => !skip.has(d.id))
  const live = ds.filter(d => working(d.state))
  const names = (live.length ? live : ds.slice(-1)).map(d => d.nickname)
  if (!names.length || room < 3) return ''
  let out = ''
  let shown = 0
  for (const nm of names) {
    const next = out ? `${out} ${nm}` : nm
    const badge = names.length - shown - 1 > 0 ? ` x${names.length}` : ''
    if (next.length + badge.length > room) break
    out = next
    shown++
  }
  if (shown === names.length) return out
  const badge = `x${names.length}`
  if (!out) {
    const keep = room - badge.length - 2
    return keep >= 2 ? `${names[0]!.slice(0, keep)}… ${badge}` : badge.slice(0, room)
  }
  return `${out} ${badge}`
}

// The Lead's spoke to station i: straight along the Lead row, else along the spine to the station's row and across.
export function spokePath(g: ReturnType<typeof geometry>, i: number): Pt[] {
  const st = g.stations[i]!
  if (st.y === g.lead.y) return edge(g.lead, st)
  const bend = { x: g.lead.x, y: st.y }
  return [...edge(g.lead, bend, false, true), ...edge(bend, st, true).slice(1)]
}

export type Extra = { cos?: string; dispatches?: Dispatch[] }

// One frame: columns * rows triplets [codePoint, fg, bg], row-major. `extra.cos`: the CoS node's label (glossary term and
// the main session's model); `extra.dispatches`: the live dispatch events (dispatchesOf).
export function frame(sts: Station[], t: number, columns: number, rows = RASTER_ROWS, returns: Return[] = [], extra: Extra = {}): Uint32Array {
  const n = columns * rows
  const bits = new Uint8Array(n)
  const lvl = new Int8Array(n).fill(-1)
  const hue: Hue[] = new Array(n).fill('edge')
  const text = new Uint32Array(n)
  const tfg = new Uint32Array(n)
  const BIT = [[0x01, 0x02, 0x04, 0x40], [0x08, 0x10, 0x20, 0x80]]
  const dot = (p: Pt, h: Hue, level: number) => {
    const cx = Math.floor(p.x / 2)
    const cy = Math.floor(p.y / 4)
    if (p.x < 0 || p.y < 0 || cx >= columns || cy >= rows) return
    const i = cy * columns + cx
    bits[i]! |= BIT[p.x % 2]![p.y % 4]!
    if (level > lvl[i]!) (lvl[i] = level), (hue[i] = h)
  }
  const put = (x: number, y: number, ch: number, fg: number) => {
    if (x < 0 || y < 0 || x >= columns || y >= rows) return
    text[y * columns + x] = ch
    tfg[y * columns + x] = fg
  }
  const write = (x: number, y: number, s: string, fg: number) => {
    for (let k = 0; k < s.length; k++) put(x + k, y, s.charCodeAt(k), fg)
  }
  // a ring of dots around a cell that grows and fades over RIPPLE_MS
  const ripple = (c: Pt, age: number, h: Hue) => {
    const f = age / RIPPLE_MS
    const r = 2.5 + 3 * f
    const P = dotOf(c)
    for (let k = 0; k < 20; k++) {
      const a = (k * Math.PI) / 10
      dot({ x: Math.round(P.x + r * Math.cos(a) * 1.4), y: Math.round(P.y + r * Math.sin(a)) }, h, Math.round(5 - 4 * f))
    }
  }
  // a pulse head with a shrinking tail: the head a small cross, then TRAIL single dots dimming behind it
  const pulse = (path: Pt[], head: number, dir: 1 | -1, h: Hue) => {
    for (let k = TRAIL; k >= 1; k--) {
      const p = path[head - dir * k * 2]
      if (p) dot(p, h, 6 - k * 1.5)
    }
    const p = path[head]
    if (!p) return
    dot(p, h, 7)
    for (const [ox, oy] of [[0, -1], [0, 1], [1, 0], [-1, 0]]) dot({ x: p.x + ox!, y: p.y + oy! }, h, 7)
  }
  const g = geometry(columns)
  const shown = sts.slice(0, 6)
  const all = shown.flatMap(s => s.delegates)
  const h = hierarchy(all)
  const byId = new Map(all.map(d => [d.id, d] as const))
  const slot = new Map(shown.map((s, i) => [s.category, i] as const))
  const right = (i: number) => g.stations[i]!.x > g.centre.x
  const hubIds = new Set([h.lead?.id, h.worker?.id].filter((x): x is string => !!x))
  const spoke = (i: number): Pt[] => spokePath(g, i)
  const link = h.lead ? edge(g.cos, g.lead) : []
  // a route's path from the starter to the delegate, and where it ends at each side
  const routeOfId = (id: string) => {
    const d = byId.get(id)
    if (!d) return undefined
    const i = slot.get(d.category)
    if (i === undefined) return undefined
    const r = routeOf(d, all, h)
    if (r.kind === 'up') return { path: link, from: g.cos, to: g.lead, temp: false }
    if (r.kind === 'spoke') return { path: spoke(i), from: g.lead, to: g.stations[i]!, temp: false }
    if (r.kind === 'cos') return { path: edge(g.cos, g.stations[i]!), from: g.cos, to: g.stations[i]!, temp: true }
    const pi = r.kind === 'child' ? slot.get(r.parent!) : undefined
    if (pi === undefined) return undefined
    return { path: arc(g.stations[pi]!, g.stations[i]!, g.centre), from: g.stations[pi]!, to: g.stations[i]!, temp: true }
  }
  // permanent lines: the spokes (dim, brighter while a Lead-started delegate on them runs, red-tinted while a failure is
  // unacknowledged) and the CoS-Lead link
  const beats = shown.map(s => s.delegates.filter(d => working(d.state) && routeOf(d, all, h).kind === 'spoke').length)
  shown.forEach((s, i) => {
    const alert = s.unacked.length > 0
    for (const p of spoke(i)) dot(p, alert && !beats[i] ? 'alert' : beats[i] ? 'work' : 'edge', beats[i] ? 3 : alert ? 2 : 1)
  })
  for (const p of link) dot(p, 'edge', 2)
  // heartbeats on Lead spokes
  shown.forEach((s, i) => {
    const path = spoke(i)
    if (!path.length) return
    for (const p of pulses(path.length, beats[i]!, t, (i * SEND_MS) / 6)) {
      if (p.head !== undefined) pulse(path, p.head, 1, 'work')
      if (p.ripple !== undefined) ripple(g.stations[i]!, p.ripple, 'work')
    }
  })
  // real events: a dispatch out along its route, a result back to the starter; a CoS edge or a curve exists only meanwhile
  const ripples: Array<[Pt, number, Hue]> = []
  for (const e of extra.dispatches ?? []) {
    const age = t - e.at
    const r = routeOfId(e.id)
    if (!r || !r.path.length || age < 0 || age >= EVENT_MS) continue
    if (r.temp) for (const p of r.path) dot(p, 'arc', 2)
    if (age < ROUTE_MS) pulse(r.path, Math.min(r.path.length - 1, Math.floor((age / ROUTE_MS) * r.path.length)), 1, 'work')
    else ripples.push([r.to, age - ROUTE_MS, 'work'])
  }
  for (const ret of returns) {
    const age = t - ret.at
    const r = routeOfId(ret.id)
    if (!r || !r.path.length || age < 0 || age >= RETURN_MS + RIPPLE_MS) continue
    const hu: Hue = ret.failed ? 'alert' : 'work'
    if (r.temp) for (const p of r.path) dot(p, 'arc', 2)
    if (age < RETURN_MS) pulse(r.path, Math.max(0, r.path.length - 1 - Math.floor((age / RETURN_MS) * r.path.length)), -1, hu)
    else ripples.push([r.from, age - RETURN_MS, hu])
  }
  for (const [c, age, hu] of ripples) ripple(c, age, hu)
  // stations: mark, category label with a steady red failure count, names line
  shown.forEach((s, i) => {
    const at = g.stations[i]!
    const alert = s.unacked.length > 0
    const paused = s.delegates.some(d => d.state === 'paused')
    const done = s.delegates.some(d => d.state === 'done')
    const [mark, fg] = alert
      ? [GLYPH.alert, colour('alert', 7)]
      : s.lit
        ? [GLYPH.lit, colour('work', 7)]
        : paused
          ? [GLYPH.paused, colour('edge', 6)]
          : done
            ? [GLYPH.done, colour('text', 4)]
            : [GLYPH.idle, colour('edge', 3)]
    put(at.x, at.y, mark, fg)
    const rt = right(i)
    const room = rt ? columns - at.x - 2 : at.x - 1
    const count = alert ? ` ${s.unacked.length}` : ''
    const label = (s.category + count).slice(0, Math.max(0, room))
    const lfg = s.lit ? colour('text', 7) : s.delegates.length ? colour('text', 5) : colour('edge', 4)
    const lx = rt ? at.x + 2 : at.x - 1 - label.length
    write(lx, at.y, s.category.slice(0, label.length), lfg)
    if (label.length > s.category.length) write(lx + s.category.length, at.y, label.slice(s.category.length), colour('alert', 7))
    const names = stationNames(s, room, hubIds)
    if (names) write(rt ? at.x + 2 : at.x - 1 - names.length, at.y + 1, names, s.lit ? colour('work', 6) : colour('edge', 4))
  })
  // the three role nodes. The hub labels sit to the right of the hubs, on rows no right-hand station uses.
  const beside = (c: Pt, s: string, fg: number) => write(c.x + 2, c.y, s.slice(0, Math.max(0, columns - c.x - 2)), fg)
  const nodeMark = (d: Delegate): [number, number] =>
    isAlertState(d.state) ? [GLYPH.alert, colour('alert', 7)] : working(d.state) ? [GLYPH.hub, colour('work', 7)] : [GLYPH.hub, colour('text', 5)]
  put(g.cos.x, g.cos.y, GLYPH.hub, colour('text', 6))
  if (extra.cos) beside(g.cos, extra.cos, colour('text', 6))
  if (h.lead) {
    const [m, fg] = nodeMark(h.lead)
    put(g.lead.x, g.lead.y, m, fg)
    beside(g.lead, `Lead · ${h.lead.nickname}`, colour('text', 6))
  } else {
    // no delegate has started delegates of its own: the main session (the CoS) is doing the Lead's job itself
    put(g.lead.x, g.lead.y, GLYPH.idle, colour('edge', 5))
    beside(g.lead, 'CoS as Lead', colour('edge', 5))
  }
  if (h.worker) {
    put(g.worker.x, g.worker.y, GLYPH.lit, colour('work', 7))
    beside(g.worker, `Worker · ${h.worker.nickname}`, colour('text', 6))
  }
  const cells = new Uint32Array(n * 3)
  for (let i = 0; i < n; i++) {
    const ch = text[i] ? text[i]! : bits[i] ? 0x2800 + bits[i]! : BLANK
    cells[i * 3] = ch
    cells[i * 3 + 1] = text[i] ? tfg[i]! : bits[i] ? colour(hue[i]!, lvl[i]!) : DEFAULT
    cells[i * 3 + 2] = DEFAULT
  }
  return cells
}
const isAlertState = (s: State) => s === 'failed' || s === 'lost'

// The distinct [fg, bg] pairs of a frame (the terminal paints 1024 at once).
export function colourPairs(cells: Uint32Array): number {
  const s = new Set<string>()
  for (let i = 0; i < cells.length; i += 3) s.add(`${cells[i + 1]}:${cells[i + 2]}`)
  return s.size
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
// Standard padded base64 of the little-endian bytes (RasterProps.cells).
export function encodeCells(words: Uint32Array): string {
  const bytes = new Uint8Array(words.length * 4)
  words.forEach((w, i) => {
    bytes[i * 4] = w & 0xff
    bytes[i * 4 + 1] = (w >>> 8) & 0xff
    bytes[i * 4 + 2] = (w >>> 16) & 0xff
    bytes[i * 4 + 3] = (w >>> 24) & 0xff
  })
  let out = ''
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i]!
    const b = i + 1 < bytes.length ? bytes[i + 1]! : 0
    const c = i + 2 < bytes.length ? bytes[i + 2]! : 0
    const v = (a << 16) | (b << 8) | c
    out += B64[(v >>> 18) & 63]! + B64[(v >>> 12) & 63]!
    out += i + 1 < bytes.length ? B64[(v >>> 6) & 63]! : '='
    out += i + 2 < bytes.length ? B64[v & 63]! : '='
  }
  return out
}

// The Raster width for a pane body; 0 when the pane is too narrow for the grid map (the static map stands alone).
export const rasterColumns = (bodyColumns: number): number =>
  bodyColumns >= RASTER_MIN_COLUMNS ? Math.min(bodyColumns, RASTER_MAX_COLUMNS) : 0

// The room the CoS label has on a Raster of `columns` cells.
export const cosRoom = (columns: number): number => columns - geometry(columns).cos.x - 2
