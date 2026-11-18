import { expect, test } from 'claude-code/testing'

import {
  arc, colour, colourPairs, dispatchesOf, edge, encodeCells, EVENT_MS, frame, geometry, landings, needsMotion, PULSE_CAP,
  pulses, RASTER_MAX_COLUMNS, RASTER_MIN_COLUMNS, RASTER_ROWS, rasterColumns, RETURN_MS, RIPPLE_MS, routeOf, ROUTE_MS, SEND_MS, spokePath, stationNames,
} from './frames'
import { CATEGORIES, stations } from './mission'
import type { Delegate } from './mission'

const d = (id: string, category: Delegate['category'], state: Delegate['state'], extra: Partial<Delegate> = {}): Delegate => ({
  id, source: 'subagent', nickname: id, rung: '?', task: '', category, state, ...extra,
})
const COLS = 44
const glyphs = (cells: Uint32Array) => {
  const rows: string[] = []
  for (let y = 0; y < RASTER_ROWS; y++) {
    let r = ''
    for (let x = 0; x < COLS; x++) r += String.fromCharCode(cells[(y * COLS + x) * 3]!)
    rows.push(r)
  }
  return rows.join('\n')
}
const fgAt = (cells: Uint32Array, p: { x: number; y: number }) => cells[(Math.floor(p.y / 4) * COLS + Math.floor(p.x / 2)) * 3 + 1]!
const isBraille = (c: number) => c > 0x2800 && c <= 0x28ff

const rowsOf = (f: Uint32Array) => glyphs(f).split('\n')
const fgSet = (f: Uint32Array) => new Set(Array.from({ length: f.length / 3 }, (_, i) => f[i * 3 + 1]!))

test('frames: every spoke is a line of braille dots from the Lead hub along the spine to the station row and across, dim when idle', () => {
  const g = geometry(COLS)
  expect(g.stations.length).toBe(6)
  // one vertical spine: CoS, Lead, Worker, top to bottom, all in one column
  expect(g.cos.x).toBe(g.lead.x)
  expect(g.worker.x).toBe(g.lead.x)
  expect(g.cos.y).toBeLessThan(g.lead.y)
  expect(g.lead.y).toBeLessThan(g.worker.y)
  // stations: Plan, Scout, Write on the left; Other, Review, Build on the right
  const at = (c: string) => g.stations[CATEGORIES.indexOf(c as never)]!
  for (const c of ['Plan', 'Scout', 'Write']) expect(at(c).x).toBeLessThan(g.lead.x)
  for (const c of ['Other', 'Review', 'Build']) expect(at(c).x).toBeGreaterThan(g.lead.x)
  expect(at('Plan').y).toBeLessThan(at('Scout').y)
  expect(at('Scout').y).toBeLessThan(at('Write').y)
  expect(at('Other').y).toBeLessThan(at('Review').y)
  expect(at('Review').y).toBeLessThan(at('Build').y)
  expect(at('Scout').y).toBe(g.lead.y) // straight spoke
  const f = frame(stations([], {}), 0, COLS)
  for (let s = 0; s < 6; s++) {
    const path = spokePath(g, s)
    expect(path.length).toBeGreaterThan(6)
    for (let k = 1; k < path.length; k++) expect(Math.max(Math.abs(path[k]!.x - path[k - 1]!.x), Math.abs(path[k]!.y - path[k - 1]!.y))).toBeLessThanOrEqual(1)
    const i = (Math.floor(path[3]!.y / 4) * COLS + Math.floor(path[3]!.x / 2)) * 3
    expect(isBraille(f[i]!)).toBe(true)
    expect(f[i + 1]).toBe(colour('edge', 1))
    // at most one bend: every dot is on the spine column or on the station's row
    for (const p of path) expect(p.x === g.lead.x * 2 + 1 || p.y === g.stations[s]!.y * 4 + 2).toBe(true)
  }
  expect(glyphs(f)).toContain('◉')
  expect(glyphs(f)).toContain('○ Build')
  expect(glyphs(f)).toContain('Plan ○')
  // the spokes down the spine share their first dots
  expect(spokePath(g, 0).slice(0, 5)).toEqual(spokePath(g, 1).slice(0, 5))
})

test('frames: the CoS is a small node at the top edge with the glossary term and the model', () => {
  const g = geometry(COLS)
  const r = rowsOf(frame(stations([], {}), 0, COLS, RASTER_ROWS, [], { cos: 'CoS · fable' }))
  expect(r[0]![g.cos.x]).toBe('◉')
  expect(r[0]).toContain('◉ CoS · fable')
  expect(r.slice(1).join('\n')).not.toContain('CoS ·')
})

test('frames: a station names its delegates; xN when not all fit', () => {
  const two = stations([d('terra', 'Build', 'running'), d('luna', 'Build', 'running')], {})[1]!
  expect(stationNames(two, 20)).toBe('terra luna')
  expect(stationNames(two, 9)).toBe('terra x2')
  expect(stationNames(two, 6)).toBe('te… x2')
  // none working: the newest one, for history
  expect(stationNames(stations([d('a', 'Build', 'done'), d('b', 'Build', 'done')], {})[1]!, 20)).toBe('b')
  expect(glyphs(frame(stations([d('terra', 'Build', 'running'), d('luna', 'Build', 'running')], {}), 0, COLS))).toContain('terra luna')
})

test('frames: an outward pulse crosses its spoke in ROUTE_MS with a shrinking tail, then ripples at the station', () => {
  const sts = stations([d('a', 'Build', 'running')], {})
  expect(needsMotion(sts)).toBe(true)
  expect(ROUTE_MS).toBeGreaterThanOrEqual(400)
  expect(ROUTE_MS).toBeLessThanOrEqual(800)
  const g = geometry(COLS)
  const path = spokePath(g, 1) // Build is station 1, on the right: down the spine, then across
  const stagger = SEND_MS / 6
  const t0 = SEND_MS - stagger // phase 0: leaving the centre
  expect(pulses(path.length, 1, t0, stagger)).toEqual([{ head: 0 }])
  const at14 = t0 + ((14 + 0.5) / path.length) * ROUTE_MS // head on dot 14, clear of the hub labels
  const [mid] = pulses(path.length, 1, at14, stagger)
  expect(mid!.head).toBe(14)
  expect(pulses(path.length, 1, t0 + ROUTE_MS + 10, stagger)).toEqual([{ ripple: 10 }])
  expect(pulses(path.length, 1, t0 + ROUTE_MS + RIPPLE_MS + 10, stagger)).toEqual([]) // quiet until the next send
  const f = frame(sts, at14, COLS)
  expect(fgAt(f, path[mid!.head!]!)).toBe(colour('work', 7))
  const tail = fgAt(f, path[mid!.head! - 6]!)
  expect(tail).not.toBe(colour('work', 7))
  expect(fgAt(f, path[mid!.head! - 12]!)).toBe(colour('work', 3)) // beyond the tail: the lit spoke
  expect(glyphs(frame(sts, 300, COLS))).toBe(glyphs(frame(sts, 300, COLS))) // pure
})

test('frames: more delegates, more pulses on one spoke, capped', () => {
  let most = 0
  for (let t = 0; t < SEND_MS; t += 40) most = Math.max(most, pulses(100, 9, t).length)
  expect(most).toBeLessThanOrEqual(PULSE_CAP)
  expect(most).toBeGreaterThan(0)
})

test('frames: a finished delegate sends one pulse back to the Lead hub and a ripple there; motion then stops', () => {
  const run = [d('a', 'Scout', 'running')]
  const fin = [d('a', 'Scout', 'done')]
  const r1 = landings({}, run, [], 0)
  expect(r1.returns.length).toBe(0)
  const r2 = landings(r1.seen, fin, r1.returns, 1000)
  expect(r2.returns).toEqual([{ id: 'a', category: 'Scout', at: 1000 }])
  expect(landings(r2.seen, fin, r2.returns, 1100).returns.length).toBe(1)
  const sts = stations(fin, {})
  expect(needsMotion(sts)).toBe(false)
  expect(needsMotion(sts, r2.returns, 1000 + RETURN_MS + RIPPLE_MS / 2)).toBe(true)
  expect(needsMotion(sts, r2.returns, 1000 + RETURN_MS + RIPPLE_MS)).toBe(false)
  const g = geometry(COLS)
  const path = spokePath(g, 3) // Scout, on the left: straight from the Lead
  expect(fgAt(frame(sts, 1000, COLS, RASTER_ROWS, r2.returns), path[path.length - 1]!)).toBe(colour('work', 7))
  expect(fgAt(frame(sts, 1000 + RETURN_MS - 1, COLS, RASTER_ROWS, r2.returns), path[0]!)).toBe(colour('work', 7))
  const rippling = frame(sts, 1000 + RETURN_MS + 50, COLS, RASTER_ROWS, r2.returns)
  expect(glyphs(rippling)).not.toBe(glyphs(frame(sts, 0, COLS)))
  expect(glyphs(frame(sts, 1000 + RETURN_MS + RIPPLE_MS, COLS, RASTER_ROWS, r2.returns))).toBe(glyphs(frame(sts, 0, COLS)))
  expect(glyphs(rippling)).toContain('Scout ✓')
})

test('frames: an unacknowledged failure is a steady red mark with its count; it does not move the timer', () => {
  const failed = stations([d('f', 'Review', 'failed', { alertAt: 5 })], {})
  expect(needsMotion(failed)).toBe(false)
  expect(glyphs(frame(failed, 0, COLS))).toContain('✗ Review 1')
  expect(glyphs(frame(failed, 0, COLS))).toBe(glyphs(frame(failed, 777, COLS)))
  const acked = stations([d('f', 'Review', 'failed', { alertAt: 5 })], { Review: ['f@5'] })
  expect(glyphs(frame(acked, 0, COLS))).not.toContain('✗')
  const still = stations([d('p', 'Plan', 'paused'), d('x', 'Write', 'done')], {})
  expect(glyphs(frame(still, 0, COLS))).toContain('◐')
})


test('frames: a failed result travels back too, in the failure colour', () => {
  const r1 = landings({}, [d('a', 'Scout', 'running')], [], 0)
  const r2 = landings(r1.seen, [d('a', 'Scout', 'failed', { alertAt: 1000 })], r1.returns, 1000)
  expect(r2.returns).toEqual([{ id: 'a', category: 'Scout', at: 1000, failed: true }])
  const sts = stations([d('a', 'Scout', 'failed', { alertAt: 1000 })], { Scout: ['a@1000'] })
  expect(fgSet(frame(sts, 1000 + RETURN_MS / 2, COLS, RASTER_ROWS, r2.returns)).has(colour('alert', 7))).toBe(true)
})

// A run with a Lead: sol (orchestrator, Plan) started terra (Build) and haiku (Scout); the main session itself started x (Review).
const L = d('L', 'Plan', 'running', { nickname: 'sol', rung: 'orchestrator', startedAt: 0 })
const W = d('W', 'Build', 'running', { nickname: 'terra', rung: 'workhorse', startedAt: 100, parentId: 'L' })
const G = d('G', 'Scout', 'running', { nickname: 'haiku', rung: 'grunt', startedAt: 200, parentId: 'L' })
const X = d('X', 'Review', 'running', { nickname: 'luna', rung: 'grunt', startedAt: 1000 })

test('routes: results go back to whoever started the delegate', () => {
  const all = [L, W, G, X]
  expect(routeOf(L, all).kind).toBe('up') // CoS <-> Lead link
  expect(routeOf(W, all).kind).toBe('spoke') // the Lead's Worker: a Lead spoke, never the CoS
  expect(routeOf(X, all).kind).toBe('cos') // started by the main session while a Lead runs
  const g2 = d('g2', 'Write', 'running', { startedAt: 300, parentId: 'W' })
  expect(routeOf(g2, [...all, g2])).toEqual({ kind: 'child', parent: 'Build' }) // Workhorse -> Grunt: a curve
  expect(routeOf(d('o', 'Build', 'running', { parentId: 'gone' }), all).kind).toBe('none') // parent not on the map: nothing invented
  expect(routeOf(d('s', 'Build', 'running', { parentId: 'W' }), [...all]).kind).toBe('none') // same station as its parent
  // no Lead: the main session does the Lead's job on the spokes; nothing goes to a CoS edge
  expect(routeOf(X, [X]).kind).toBe('spoke')
})

test('CoS edges: drawn only while a real dispatch or result between the main session and that delegate travels', () => {
  const g = geometry(COLS)
  const lw = [L, { ...W, state: 'done' as const }, { ...G, state: 'done' as const }]
  const all = [...lw, X]
  const cosEdge = edge(g.cos, g.stations[0]!) // Review
  expect(dispatchesOf(all, 1100)).toEqual([{ id: 'X', at: 1000 }])
  const during = frame(stations(all, {}), 1100, COLS, RASTER_ROWS, [], { dispatches: dispatchesOf(all, 1100) })
  expect(cosEdge.filter(p => fgAt(during, p) === colour('arc', 2)).length).toBeGreaterThan(cosEdge.length / 2)
  const after = frame(stations(all, {}), 1000 + EVENT_MS, COLS, RASTER_ROWS, [], { dispatches: dispatchesOf(all, 1000 + EVENT_MS) })
  expect(fgSet(after).has(colour('arc', 2))).toBe(false)
  expect(dispatchesOf(all, 1000 + EVENT_MS)).toEqual([])
  // X keeps running: no heartbeat on a CoS edge, so nothing moves and the timer may stop
  expect(needsMotion(stations(all, {}), [], 5000, dispatchesOf(all, 5000))).toBe(false)
  // its result travels back on the CoS edge, then the edge goes
  const r = landings(landings({}, all, [], 4000).seen, [...lw, { ...X, state: 'done' as const }], [], 5000).returns
  expect(r).toEqual([{ id: 'X', category: 'Review', at: 5000 }])
  const back = frame(stations([...lw, { ...X, state: 'done' as const }], {}), 5000 + RETURN_MS / 2, COLS, RASTER_ROWS, r)
  expect(fgSet(back).has(colour('arc', 2))).toBe(true)
  expect(fgSet(frame(stations([...lw, { ...X, state: 'done' as const }], {}), 5000 + RETURN_MS + RIPPLE_MS, COLS, RASTER_ROWS, r)).has(colour('arc', 2))).toBe(false)
})

test('CoS: a Worker of the Lead never pulses to the CoS; only the Lead reports up the link', () => {
  const g = geometry(COLS)
  const link = edge(g.cos, g.lead)
  const wDone = { ...W, state: 'done' as const }
  const before = [L, W, G]
  const r = landings(landings({}, before, [], 0).seen, [L, wDone, G], [], 1000).returns
  const f = frame(stations([L, wDone, G], {}), 1000 + RETURN_MS / 2, COLS, RASTER_ROWS, r)
  expect(fgSet(f).has(colour('arc', 2))).toBe(false) // no CoS edge
  expect(link.some(p => fgAt(f, p) === colour('work', 7))).toBe(false) // nothing on the link
  // the Lead's own result goes up the link
  const lDone = { ...L, state: 'done' as const }
  const r2 = landings(landings({}, [L, wDone], [], 0).seen, [lDone, wDone], [], 2000).returns
  expect(r2).toEqual([{ id: 'L', category: 'Plan', at: 2000 }])
  const up = frame(stations([lDone, wDone], {}), 2000 + RETURN_MS / 2, COLS, RASTER_ROWS, r2)
  expect(link.some(p => fgAt(up, p) === colour('work', 7))).toBe(true)
})

test('hubs: Lead and Worker carry their role word; no Lead shows the CoS doing the Lead job; positions never move', () => {
  const g = geometry(COLS)
  const full = rowsOf(frame(stations([L, W, G], {}), 0, COLS))
  expect(full[g.lead.y]).toContain('● Lead · sol'.slice(2))
  expect(full[g.worker.y]).toContain('Worker · terra')
  expect(full[g.lead.y]!.indexOf('Lead · sol')).toBe(g.lead.x + 2) // beside the hub
  expect(full[g.worker.y]![g.worker.x]).toBe('●')
  const noLead = rowsOf(frame(stations([d('a', 'Build', 'running', { rung: 'grunt' })], {}), 0, COLS))
  expect(noLead[g.lead.y]).toContain('CoS as Lead')
  expect(noLead[g.lead.y]![g.lead.x]).toBe('○')
  expect(noLead.join('\n')).not.toContain('Worker')
  expect(noLead.join('\n')).not.toContain('Lead ·')
  // the link CoS -> Lead only while a Lead exists
  const link = edge(g.cos, g.lead)
  expect(isBraille(frame(stations([], {}), 0, COLS)[(link[1]!.y >> 2) * COLS * 3 + (link[1]!.x >> 1) * 3]!)).toBe(false)
  expect(isBraille(frame(stations([L, W], {}), 0, COLS)[(link[1]!.y >> 2) * COLS * 3 + (link[1]!.x >> 1) * 3]!)).toBe(true)
  // stations and hubs stay put with or without Lead and Worker, at every width
  for (const cols of [RASTER_MIN_COLUMNS, 44, RASTER_MAX_COLUMNS]) {
    const gg = geometry(cols)
    const marks = (ds: Delegate[]) => {
      const f = frame(stations(ds, {}), 0, cols)
      return gg.stations.map(p => f[(p.y * cols + p.x) * 3]!)
    }
    expect(marks([L, W, G]).every(c => c !== 0x20 && !isBraille(c))).toBe(true)
    expect(marks([]).every(c => c !== 0x20 && !isBraille(c))).toBe(true)
    expect(geometry(cols)).toEqual(gg)
  }
})

test('curves: a child of a non-Lead delegate draws a curve between stations only while its pulse travels', () => {
  const g2 = d('g2', 'Write', 'running', { rung: 'grunt', startedAt: 3000, parentId: 'W' })
  const all = [L, W, G, g2]
  const g = geometry(COLS)
  const curve = arc(g.stations[1]!, g.stations[2]!, g.centre)
  expect(curve.length).toBeGreaterThan(5)
  const during = frame(stations(all, {}), 3100, COLS, RASTER_ROWS, [], { dispatches: dispatchesOf(all, 3100) })
  expect(curve.filter(p => fgAt(during, p) === colour('arc', 2)).length).toBeGreaterThan(0)
  expect(fgSet(frame(stations(all, {}), 3000 + EVENT_MS, COLS, RASTER_ROWS, [], { dispatches: dispatchesOf(all, 3000 + EVENT_MS) })).has(colour('arc', 2))).toBe(false)
  // the old spawn and start-order arcs are gone: a plain start on another station draws no curve
  const p = d('p', 'Plan', 'running', { startedAt: 0 })
  const q = d('q', 'Build', 'running', { startedAt: 1000 })
  expect(fgSet(frame(stations([p, q], {}), 1100, COLS, RASTER_ROWS, [], { dispatches: dispatchesOf([p, q], 1100) })).has(colour('arc', 2))).toBe(false)
})

test('frames: colour pairs stay far under the 1024 palette; size and encoding', () => {
  const busy = stations([
    d('a', 'Build', 'running'), d('b', 'Build', 'running'), d('c', 'Write', 'review'), d('f', 'Plan', 'lost', { alertAt: 1 }), d('x', 'Other', 'done'),
  ], {})
  const all = [L, W, G, X, ...busy.flatMap(s => s.delegates)]
  const sts = stations(all, {})
  let most = 0
  for (let t = 0; t < 6000; t += 80)
    most = Math.max(most, colourPairs(frame(sts, t, COLS, RASTER_ROWS, [{ id: 'x', category: 'Other', at: 0 }, { id: 'f', category: 'Plan', at: 400, failed: true }], { cos: 'CoS · fable', dispatches: dispatchesOf(all, t) })))
  expect(most).toBeLessThan(64)
  expect(encodeCells(Uint32Array.of(0x2588, 0xff8800, 0x01000000))).toBe('iCUAAACI/wAAAAAB')
  expect(encodeCells(frame([], 0, COLS)).length).toBe(Math.ceil((COLS * RASTER_ROWS * 12) / 3) * 4)
  expect(rasterColumns(RASTER_MIN_COLUMNS - 1)).toBe(0)
  expect(rasterColumns(RASTER_MIN_COLUMNS)).toBe(RASTER_MIN_COLUMNS)
  expect(rasterColumns(200)).toBe(RASTER_MAX_COLUMNS)
  for (let i = 0; i < frame(busy, 0, 70).length; i += 3) expect(frame(busy, 0, 70)[i]! <= 0xffff).toBe(true)
})


// Vertical layout (2026-11-12): width, label room, stable positions, and the two label fixes.
// A busy run with the longest names the map must hold: Lead and Worker with 9-letter nicknames, a station with two
// working delegates, a 12-failure count on a left and a right station.
const BL = d('BL', 'Plan', 'running', { nickname: 'codestral', rung: 'orchestrator', startedAt: 0 })
const BW = d('BW', 'Build', 'running', { nickname: 'ministral', rung: 'workhorse', startedAt: 100, parentId: 'BL' })
const busyRun = (): Delegate[] => [
  BL, BW,
  d('s1', 'Scout', 'running', { nickname: 'haiku', rung: 'grunt', startedAt: 200, parentId: 'BL' }),
  d('s2', 'Scout', 'running', { nickname: 'luna', rung: 'grunt', startedAt: 210, parentId: 'BL' }),
  d('w1', 'Write', 'done', { nickname: 'terra' }),
  d('o1', 'Other', 'running', { nickname: 'mistral', rung: 'grunt', startedAt: 220, parentId: 'BL' }),
  ...Array.from({ length: 12 }, (_, k) => d(`r${k}`, 'Review', 'failed', { nickname: 'rev' + k, alertAt: k })),
]
// Every string the frame must show whole, as [row, column, text]; derived from the geometry alone.
const expectedText = (cols: number, sts: ReturnType<typeof stations>): Array<[number, number, string]> => {
  const g = geometry(cols)
  const out: Array<[number, number, string]> = [
    [g.cos.y, g.cos.x + 2, 'CoS · fable'],
    [g.lead.y, g.lead.x + 2, 'Lead · codestral'],
    [g.worker.y, g.worker.x + 2, 'Worker · ministral'],
  ]
  sts.forEach((s, i) => {
    const p = g.stations[i]!
    const label = s.category + (s.unacked.length ? ` ${s.unacked.length}` : '')
    out.push([p.y, p.x > g.lead.x ? p.x + 2 : p.x - 1 - label.length, label])
  })
  return out
}
function frameAt(sts: ReturnType<typeof stations>, cols: number) {
  return frame(sts, 0, cols, RASTER_ROWS, [], { cos: 'CoS · fable' })
}
const rowsAt = (f: Uint32Array, cols: number) => {
  const out: string[] = []
  for (let y = 0; y < RASTER_ROWS; y++) {
    let r = ''
    for (let x = 0; x < cols; x++) r += String.fromCharCode(f[(y * cols + x) * 3]!)
    out.push(r)
  }
  return out
}

test('width: the map fits a narrow pane; the minimum is the smallest width where the longest labels stay whole', () => {
  expect(RASTER_MIN_COLUMNS).toBeLessThanOrEqual(48)
  expect(RASTER_MIN_COLUMNS).toBeGreaterThanOrEqual(30)
  expect(RASTER_ROWS).toBeLessThanOrEqual(20)
  expect(rasterColumns(RASTER_MIN_COLUMNS - 1)).toBe(0)
  expect(rasterColumns(RASTER_MIN_COLUMNS)).toBe(RASTER_MIN_COLUMNS)
  expect(rasterColumns(500)).toBe(RASTER_MAX_COLUMNS)
  const sts = stations(busyRun(), {})
  const ok = (cols: number) => {
    const rows = rowsAt(frameAt(sts, cols), cols)
    return expectedText(cols, sts).every(([y, x, text]) => rows[y]!.slice(x, x + text.length) === text)
  }
  expect(ok(RASTER_MIN_COLUMNS)).toBe(true)
  expect(ok(RASTER_MIN_COLUMNS - 1)).toBe(false) // one column less and a label is cut: nothing smaller fits
})

test('width: no two labels collide at the minimum, a middle width or the cap', () => {
  const sts = stations(busyRun(), {})
  for (const cols of [RASTER_MIN_COLUMNS, 45, RASTER_MAX_COLUMNS]) {
    const rows = rowsAt(frameAt(sts, cols), cols)
    const taken: string[] = []
    for (const [y, x, text] of expectedText(cols, sts)) {
      expect(rows[y]!.slice(x, x + text.length)).toBe(text)
      for (let k = 0; k < text.length; k++) {
        const key = `${y}:${x + k}`
        expect(taken).not.toContain(key) // no cell claimed by two labels
        taken.push(key)
      }
    }
    // the names lines sit under their stations, clear of every label
    const g = geometry(cols)
    for (const cat of ['Scout', 'Other'] as const) {
      const p = g.stations[CATEGORIES.indexOf(cat)]!
      const room = p.x > g.lead.x ? cols - p.x - 2 : p.x - 1
      const name = stationNames(sts[CATEGORIES.indexOf(cat)]!, room, new Set(['BL', 'BW']))
      expect(name.length).toBeGreaterThan(0)
      const x = p.x > g.lead.x ? p.x + 2 : p.x - 1 - name.length
      expect(rows[p.y + 1]!.slice(x, x + name.length)).toBe(name)
    }
  }
})

test('width: station and hub positions do not depend on the data, at three widths', () => {
  for (const cols of [RASTER_MIN_COLUMNS, 44, RASTER_MAX_COLUMNS]) {
    const g = geometry(cols)
    expect(g.cos.x).toBe(g.lead.x)
    for (const run of [[], [BL, BW], busyRun()]) {
      const f = frame(stations(run, {}), 0, cols)
      for (const p of g.stations) {
        const c = f[(p.y * cols + p.x) * 3]!
        expect(c !== 0x20 && !isBraille(c)).toBe(true) // a mark on every station
      }
      expect(f[(g.cos.y * cols + g.cos.x) * 3]).toBe(0x25c9)
      expect(f[(g.lead.y * cols + g.lead.x) * 3]).not.toBe(0x20)
    }
    expect(geometry(cols)).toEqual(g) // pure
  }
})

test('fix: the Lead and the primary Worker show on their hubs only, and their stations stay lit', () => {
  const sts = stations(busyRun(), {})
  const rows = rowsAt(frameAt(sts, 44), 44).join('\n')
  expect(rows.match(/codestral/g)!.length).toBe(1) // the hub, not under Plan
  expect(rows.match(/ministral/g)!.length).toBe(1) // the hub, not under Build
  expect(sts.find(s => s.category === 'Plan')!.lit).toBe(true)
  expect(sts.find(s => s.category === 'Build')!.lit).toBe(true)
  const g = geometry(44)
  const f = frame(sts, 0, 44)
  for (const cat of ['Plan', 'Build']) {
    const p = g.stations[CATEGORIES.indexOf(cat as never)]!
    expect(f[(p.y * 44 + p.x) * 3]).toBe(0x25cf) // lit mark
    expect(f[(p.y * 44 + p.x) * 3 + 1]).toBe(colour('work', 7))
  }
  // a second delegate on the Lead's station is still named there
  const more = stations([...busyRun(), d('p2', 'Plan', 'running', { nickname: 'extra', startedAt: 300, parentId: 'BL' })], {})
  expect(stationNames(more.find(s => s.category === 'Plan')!, 20, new Set(['BL', 'BW']))).toBe('extra')
  expect(stationNames(more.find(s => s.category === 'Plan')!, 20)).toBe('codestral extra')
})

test('fix: a failed station shows one mark and the count, on the left and on the right', () => {
  const failed = stations([d('a', 'Write', 'failed', { alertAt: 1 }), d('b', 'Write', 'failed', { alertAt: 2 }), d('c', 'Review', 'failed', { alertAt: 3 })], {})
  const rows = rowsAt(frame(failed, 0, 44), 44)
  const g = geometry(44)
  const w = g.stations[CATEGORIES.indexOf('Write')]!
  const r = g.stations[CATEGORIES.indexOf('Review')]!
  expect(rows[w.y]!.slice(w.x - 8, w.x + 1)).toBe('Write 2 ✗') // left: label, count, then the one mark
  expect(rows[r.y]!.slice(r.x, r.x + 10)).toBe('✗ Review 1')
  expect((rows.join('\n').match(/✗/g) ?? []).length).toBe(2) // one mark per failed station
})
