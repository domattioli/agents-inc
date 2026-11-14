import { expect, mock, test } from 'claude-code/testing'

import { normalizeView, PANE } from './register'
import { mergeAgents } from './poll'

type On = Parameters<Parameters<typeof test>[1]>[1]
type Dollar = Parameters<Parameters<typeof test>[1]>[0]

const MOUNT = {
  plugin: 'delegate-pane',
  component: 'Pane',
  requestId: PANE,
  props: { title: 'agents-inc', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

type World = {
  agents: any[]
  dirs: string[]
  files?: Record<string, string>
  reads?: string[]
  lists?: string[]
  listFails?: boolean
  // when listFails: whether the run root exists (false: no dispatch has run yet)
  rootExists?: boolean
  // read: when set, every fs.read throws; a fixture file still exists, so the read failure is a real one
  readFails?: boolean
  // paths that exist but whose read throws
  badFiles?: string[]
  // file path -> mtimeMs as a run-dir listing reports it (default T0)
  mtimes?: Record<string, number>
  // the plugin's $.store, in memory; seeded by a test to stand for an earlier process of the same session
  store?: Record<string, unknown>
  sessionId?: string
  // ui.open calls seen, and whether ui.open throws
  opens?: any[]
  openFails?: boolean
}

// 2099-11-12T12:00:00Z: the session of the fixture runs under mods/delegate-pane/hooks/fixtures/runs starts here.
const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const SURFACES = ['terminal', 'desktop'] as const

const below = (full: string) => (full.includes('.scratch/') ? full.slice(full.indexOf('.scratch/')) : full)

async function start($: Dollar, on: On, world: World, now = T0, opts: { begin?: boolean } = {}) {
  const clock = mock.clock(on, { now })
  on('fs.exists', (_$, e: any) => {
    const path = below(String(e.path))
    if (path === ROOT) return { value: world.rootExists ?? true } as any
    return { value: path in (world.files ?? {}) || (world.badFiles ?? []).includes(path) } as any
  })
  on('command.register', () => ({ value: { command: 'delegate-pane' } }))
  on('ui.open', (_$, e: any) => {
    world.opens?.push(e)
    if (world.openFails) throw new Error('no panes here')
    return { value: { isPlaced: true } }
  })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('agent.list', () => ({ value: world.agents as any }))
  on('fs.list', (_$, e: any) => {
    if (world.listFails) throw new Error('ENOENT: no such directory')
    const path = below(String(e.path))
    if (path === ROOT) return { value: world.dirs.map(name => ({ name, kind: 'dir', size: 0, mtimeMs: 0, isLink: false })) as any }
    // a run dir: its files with their times, as the engine lists them
    world.lists?.push(path)
    const files = Object.keys(world.files ?? {}).filter(f => f.startsWith(path + '/'))
    return { value: files.map(f => ({ name: f.slice(path.length + 1), kind: 'file', size: 1, mtimeMs: world.mtimes?.[f] ?? T0, isLink: false })) as any }
  })
  const store = (world.store ??= {})
  on('store.get', (_$, e: any) => ({ value: store[e.key] }) as any)
  on('store.set', (_$, e: any) => ((store[e.key] = JSON.parse(JSON.stringify(e.value))), { value: undefined }) as any)
  on('store.delete', (_$, e: any) => (delete store[e.key], { value: undefined }) as any)
  on('store.keys', () => ({ value: Object.keys(store) }) as any)
  on('session.id', () => ({ value: world.sessionId ?? 'S1' }) as any)
  on('fs.read', (_$, e: any) => {
    // the engine resolves the path against the cwd; the fixtures are keyed by the part below the cwd
    const full = String(e.path)
    const path = full.includes('.scratch/') ? full.slice(full.indexOf('.scratch/')) : full
    world.reads?.push(path)
    if (world.readFails || (world.badFiles ?? []).includes(path) || !(path in (world.files ?? {}))) throw new Error('ENOENT: ' + path)
    return { value: world.files![path] as any }
  })
  if (opts.begin === false) return clock
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  await clock.advance(1100)
  return clock
}

// A stored value the way the engine keeps it for a Shaped key (plugin-authoring examples/pane.test.tsx, `state.get`):
// { value: { shape, value }, version }. Writes land in the same cell, so the code reads back what it wrote.
function storedView(on: On, shape: string, value: unknown) {
  const cell = { value: { shape, value } as any, version: 1 }
  on('state.get', (_$, e: any) => (e.key === 'view' ? { value: cell } : ({ value: { value: undefined, version: 0 } } as any)))
  on('state.set', (_$, e: any) => {
    if (e.key !== 'view') return { value: { isSet: true, version: 1 } } as any
    if (e.ifVersion != null && e.ifVersion !== cell.version) return { value: { isSet: false, version: cell.version } } as any
    cell.value = e.value
    cell.version += 1
    return { value: { isSet: true, version: cell.version } } as any
  })
  return cell
}

const ROOT = '.scratch/agents-inc-runs'
const runFiles = (name: string, model: string, outcome: string | null, task: string): Record<string, string> => ({
  [`${ROOT}/${name}/run.json`]: JSON.stringify({ run_id: name, model, kind: 'claude', outcome, reason: null }),
  [`${ROOT}/${name}/slots.json`]: JSON.stringify({ MODEL: model, ROLE: 'Workhorse (sonnet)', TASK: task }),
})
const failedRun = (hhmmss: string, hash: string) => {
  const name = `20991112T${hhmmss}Z-sonnet-${hash}`
  return { name, files: runFiles(name, 'sonnet', 'red', 'fix the failing test') }
}

// Inlined from mods/delegate-pane/hooks/fixtures/runs/20991112T120000Z-sonnet-abc123 (tests cannot read disk).
const ABC = '20991112T120000Z-sonnet-abc123'
const ABC_FILES = {
  [`${ROOT}/${ABC}/run.json`]: '{"run_id": "20991112T120000Z-sonnet-abc123", "model": "sonnet", "kind": "claude", "cwd": "/work", "effort": "medium", "outcome": "green", "reason": null}',
  [`${ROOT}/${ABC}/slots.json`]: '{"MODEL": "sonnet", "ROLE": "Workhorse (sonnet), dispatched by Orchestrator (opus).", "TASK": "Implement the widget parser in widget.py. Then run its tests."}',
}
// Inlined from mods/delegate-pane/hooks/fixtures/runs/20991112T120500Z-luna-def456 (events.jsonl and slots.json, no run.json).
const DEF = '20991112T120500Z-luna-def456'
const DEF_FILES = {
  [`${ROOT}/${DEF}/events.jsonl`]: '{"v": 1, "seq": 1, "ts": "2099-11-12T12:05:00.000Z", "source": "agents-inc", "event": {"type": "run.start", "run_id": "20991112T120500Z-luna-def456", "model": "luna", "kind": "codex"}}\n',
  [`${ROOT}/${DEF}/slots.json`]: '{"MODEL": "luna", "ROLE": "Grunt scout (luna), dispatched by Orchestrator (opus).", "TASK": "Read the widget docs and list every config key."}',
}
// Inlined from mods/delegate-pane/hooks/fixtures/runs/20991101T000000Z-sonnet-old000: started before the session.
const OLD = '20991101T000000Z-sonnet-old000'
const OLD_FILES = { [`${ROOT}/${OLD}/run.json`]: '{"run_id": "20991101T000000Z-sonnet-old000", "model": "sonnet", "kind": "claude", "cwd": "/work", "outcome": "red", "reason": "rc-nonzero"}' }

test('the tree lists every agent type and no run before the session; the map shows Explore and the run dir (FR-003)', async ($, on) => {
  const world: World = {
    agents: [
      { id: 'a1', type: 'agents-inc:luna', description: 'read the repo', status: 'running' },
      { id: 'a2', type: 'Explore', description: 'scout', status: 'running' },
    ],
    dirs: [ABC, OLD],
    files: { ...ABC_FILES, ...OLD_FILES },
  }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect((await ui.find({ type: 'Button', text: /read the repo/ }))?.text).toContain('luna · OpenAI')
    expect((await ui.find({ type: 'Button', text: /scout/ }))?.text).toContain('Explore')
    expect(await ui.find({ type: 'Text', text: /Native agent/ })).toBeFalsy()
    // the map: Explore (rung unknown) and the finished fixture run appear
    expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    // a run started before the session start is absent from the map (H1)
    expect(await ui.find({ type: 'Text', text: /sonnet · workhorse · failed/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('tree: an agent the engine stops listing leaves the tree but stays on the map', async ($, on) => {
  const world: World = { agents: [{ id: 'a1', type: 'agents-inc:terra', description: 'fix it', status: 'running' }] as any[], dirs: [] }
  const clock = await start($, on, world)
  const before = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await before.find({ type: 'Button', text: /fix it/ })).toBeTruthy()
  await before.unmount()
  world.agents = []
  await clock.advance(1100)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Button', text: /fix it/ })).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /no delegates yet/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /terra · workhorse · /i })).toBeTruthy()
  await ui.unmount()
})

test('pure helpers: merge keeps every agent type by id and marks a vanished one finished', () => {
  const one = mergeAgents([], [{ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'running' }, { id: 'y', type: 'Explore', description: 'e', status: 'running' }])
  expect(one.map(a => a.id)).toEqual(['x', 'y'])
  expect(mergeAgents(one, [])[0]).toEqual({ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'finished' })
  expect(mergeAgents([{ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'completed' }], [])[0].status).toBe('completed')
})

// --- spec 039 pane tests (T010-T012, T015) ---

test('the map comes first and places a subagent and fixture runs at the right stations', async ($, on) => {
  const world: World = {
    agents: [{ id: 'a1', type: 'Plan', description: 'anything', status: 'running' }],
    dirs: [ABC, DEF],
    files: { ...ABC_FILES, ...DEF_FILES },
  }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
    const at = (re: RegExp) => texts.findIndex(t => re.test(t))
    expect(at(/^Mission map$/)).toBeGreaterThanOrEqual(0)
    expect(at(/no delegates yet|^ *└─/)).toBe(-1) // the tree has rows, so no empty line
    expect(at(/session · chief of staff · 2 working|session · chief of staff · 1 working/)).toBeGreaterThan(at(/^Mission map$/))
    expect(at(/Plan · \? · running/)).toBeGreaterThan(at(/^Mission map$/))
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy() // Build
    expect(await ui.find({ type: 'Text', text: /^luna · grunt · running$/ })).toBeTruthy() // Scout, run.json absent
    expect(texts.some(t => /Build/.test(t))).toBe(true)
    expect(texts.some(t => /Scout/.test(t))).toBe(true)
    await ui.unmount()
  }
})

test('a station shows 4 markers then +K more', async ($, on) => {
  const names = ['120001', '120002', '120003', '120004', '120005'].map((t, i) => failedRun(t, 'a0000' + i))
  const world: World = { agents: [], dirs: names.map(n => n.name), files: Object.assign({}, ...names.map(n => n.files)) }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect((await ui.findAll({ type: 'Text', text: /^sonnet · workhorse · failed$/ })).length).toBe(4)
    expect(await ui.find({ type: 'Text', text: /^\+1 more$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('an unknown rung renders ?', async ($, on) => {
  const name = '20991112T120100Z-mystery-bbbbbb'
  const world: World = { agents: [], dirs: [name], files: runFiles(name, 'mystery', 'green', 'zzz') }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^mystery · \? · done$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('C: no run root yet (no dispatch in this repo) shows no note', async ($, on) => {
  const world: World = { agents: [], dirs: [], listFails: true, rootExists: false }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /dispatch runs/ })).toBeFalsy()
    expect(await ui.find({ type: 'Text', text: /not ignored/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('C: a list that fails on an existing root keeps known markers and says only that', async ($, on) => {
  const world: World = { agents: [], dirs: [ABC], files: ABC_FILES }
  const clock = await start($, on, world)
  world.listFails = true
  world.rootExists = true
  await clock.advance(1100)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^dispatch runs not listed: .*showing last known$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /not ignored/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('E: every run file unreadable: the run still draws from its name, with one note', async ($, on) => {
  const world: World = { agents: [], dirs: [ABC], files: ABC_FILES, readFails: true }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · running$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^dispatch run file unreadable: .*run\.json \(\+1 more\); drawn from what was read$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^Mission map$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('E: one unreadable file is noted; the run draws from the rest', async ($, on) => {
  const world: World = { agents: [], dirs: [ABC], files: ABC_FILES, badFiles: [`${ROOT}/${ABC}/slots.json`] }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^dispatch run file unreadable: .*slots\.json; drawn from what was read$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('E: a fresh run folder with no file yet draws as running with no note', async ($, on) => {
  const name = '20991112T120700Z-sonnet-fresh0'
  const world: World = { agents: [], dirs: [name], files: {} }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · running$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /unreadable/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('B: a dry-run dispatch draws no marker and raises no ack count; a real unknown outcome still fails', async ($, on) => {
  const dry = '20991112T120100Z-sonnet-dry000'
  const odd = '20991112T120200Z-terra-odd000'
  const world: World = { agents: [], dirs: [dry, odd], files: { ...runFiles(dry, 'sonnet', 'dry-run', 'fix it'), ...runFiles(odd, 'terra', 'mystery-outcome', 'fix it') } }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · / })).toBeFalsy()
    expect(await ui.find({ type: 'Text', text: /^terra · workhorse · failed$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('A: live subagent statuses never draw as done', async ($, on) => {
  const world: World = {
    agents: [
      { id: 'p', type: 'Explore', description: 'x', status: 'pending' },
      { id: 'w', type: 'Plan', description: 'x', status: 'waiting' },
      { id: 'i', type: 'general-purpose', description: 'x', status: 'idle' },
    ],
    dirs: [],
  }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /^Plan · \? · paused$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /^general-purpose · \? · paused$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: / · done$/ })).toBeFalsy()
  await ui.unmount()
})

test('D: past 40 subagents every one keeps a marker on the map', async ($, on) => {
  const agents = Array.from({ length: 45 }, (_, i) => ({ id: 's' + i, type: 'Explore', description: 'x', status: 'running' }))
  const world: World = { agents, dirs: [] }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  // Scout shows 4 markers and +41 more: 45 in all, none fell off
  expect(await ui.find({ type: 'Text', text: /^\+41 more$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /session · chief of staff · 45 working/ })).toBeTruthy()
  await ui.unmount()
})

test('F: no delegates shows "Nothing is running." and the tree says "no delegates yet"', async ($, on) => {
  const world: World = { agents: [], dirs: [] }
  await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^Nothing is running\.$/ })).toBeTruthy()
    expect((await ui.findAll({ type: 'Text', text: /no delegates yet/ })).length).toBe(1)
    expect(await ui.find({ type: 'Text', text: /session · chief of staff · 0 working/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('G(a): a value stored under an older shape tag renders the map and none of its content', async ($, on) => {
  storedView(on, 'view-3', { types: ['agents-inc:stale-type'], agents: [{ id: 'z', type: 'agents-inc:stale', description: 'stale row', status: 'running' }], note: 'stale note' })
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^Mission map$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /stale/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('G(b): the current shape tag with fields missing renders without throw', async ($, on) => {
  storedView(on, 'view-5', { note: 'kept note' })
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^Mission map$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /no delegates yet/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('G(c): a stored sessionStart earlier than a run stamp survives session.start; the run draws', async ($, on) => {
  // stored start 11:00, the clock (and so a fresh start) at 12:30, the run at 12:00: only the stored start keeps it
  storedView(on, 'view-5', { sessionStart: '2099-11-12T11:00:00.000Z' })
  const world: World = { agents: [], dirs: [ABC], files: ABC_FILES }
  await start($, on, world, Date.UTC(2099, 10, 12, 12, 30, 0))
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('a value from the view-3 code (no map fields) normalizes; an unstarted pane renders', async ($, on) => {
  const old = { types: ['agents-inc:luna'], agents: [], note: '' }
  expect(normalizeView(old as any)).toMatchObject({ delegates: [], acked: {}, sessionStart: '', finalRuns: {}, mapNote: '' })
  expect(normalizeView(undefined)).toMatchObject({ treeRows: [], summary: '', controlsOpen: false })
  // no session.start ran: the pane reads the atom's initial value
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^Mission map$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('FR-010: three polls and a render call no model and no network noun', async ($, on) => {
  const calls: string[] = []
  for (const ev of ['model.complete', 'model.classify', 'model.fork', 'http.fetch'] as const) on(ev, () => (calls.push(ev), ({ value: undefined }) as any))
  const world: World = { agents: [{ id: 'a1', type: 'Explore', description: 'x', status: 'running' }], dirs: [ABC], files: ABC_FILES }
  const clock = await start($, on, world)
  await clock.advance(2000)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Mission map$/ })).toBeTruthy()
  await ui.unmount()
  expect(calls).toEqual([])
})

test('bound (M3): 500 run dirs, 495 final and cached; a poll reads at most 5 run.json', async ($, on) => {
  const dirs: string[] = []
  const files: Record<string, string> = {}
  for (let i = 0; i < 500; i++) {
    const name = `20991112T12${String(Math.floor(i / 60)).padStart(2, '0')}${String(i % 60).padStart(2, '0')}Z-sonnet-${String(i).padStart(6, '0')}`
    dirs.push(name)
    Object.assign(files, runFiles(name, 'sonnet', i < 495 ? 'green' : null, 'fix it'))
  }
  // the 5 live runs have no run.json yet (events only)
  const live = dirs.slice(495)
  for (const n of live) {
    delete files[`${ROOT}/${n}/run.json`]
    files[`${ROOT}/${n}/events.jsonl`] = JSON.stringify({ event: { type: 'run.start', run_id: n, model: 'sonnet', kind: 'claude' } }) + '\n'
  }
  const world: World = { agents: [], dirs, files, reads: [] }
  const clock = await start($, on, world)
  world.reads!.length = 0
  const t0 = Date.now()
  await clock.advance(1000)
  const runJsonReads = world.reads!.filter(p => p.endsWith('/run.json')).length
  expect(runJsonReads).toBeLessThanOrEqual(5)
  expect(Date.now() - t0).toBeLessThan(1000)
})

test('lit: a station is lit while a delegate runs and dim when it ends', async ($, on) => {
  const world: World = { agents: [{ id: 'a1', type: 'Plan', description: 'x', status: 'running' }], dirs: [] }
  const clock = await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^● Plan$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^○ Build$/ })).toBeTruthy()
    await ui.unmount()
  }
  world.agents = [{ id: 'a1', type: 'Plan', description: 'x', status: 'finished' }]
  await clock.advance(1100)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^○ Plan$/ })).toBeTruthy()
  await ui.unmount()
})

test('ack: press clears the count; leaving the window and a new failure give count 1 (H2); survives reload', async ($, on) => {
  const A = failedRun('120001', 'aaaaaa')
  const B = failedRun('120002', 'bbbbbb')
  const C = failedRun('120003', 'cccccc')
  const world: World = { agents: [], dirs: [A.name, B.name], files: { ...A.files, ...B.files, ...C.files } }
  const clock = await start($, on, world)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /2✗/ })).toBeTruthy()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'ack-Build' })
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  expect(await ui.find({ key: 'ack-Build' })).toBeUndefined()
  await ui.unmount()
  // one failed run leaves the window, a new failure arrives: count 1, not 0 and not 2
  world.dirs = [A.name, C.name]
  await clock.advance(1100)
  for (const surface of SURFACES) {
    const u = await $.ui.mount({ ...MOUNT, surface })
    expect(await u.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
    expect(await u.find({ key: 'ack-Build' })).toBeTruthy()
    await u.unmount()
  }
  // ack again, then reload (a second session.start): the acked ids survive
  const u2 = await $.ui.mount({ ...MOUNT, surface: 'desktop' })
  await u2.press({ key: 'ack-Build' })
  await u2.unmount()
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  await clock.advance(1100)
  const u3 = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await u3.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await u3.unmount()
})

test('stacked layout keeps every marker; under 30 columns the line layout keeps counts only (plan R6 limit)', async ($, on) => {
  const A = failedRun('120001', 'aaaaaa')
  const world: World = {
    agents: [{ id: 'a1', type: 'Plan', description: 'x', status: 'running' }],
    dirs: [A.name, ABC],
    files: { ...A.files, ...ABC_FILES },
  }
  await start($, on, world)
  for (const surface of SURFACES) {
    const narrow = await $.ui.mount({ ...MOUNT, surface, props: { ...MOUNT.props, bodyColumns: 50 } })
    expect(await narrow.find({ type: 'Text', text: /^sonnet · workhorse · failed$/ })).toBeTruthy()
    expect(await narrow.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    expect(await narrow.find({ type: 'Text', text: /^Plan · \? · running$/ })).toBeTruthy()
    expect(await narrow.find({ type: 'Text', text: /^─+ / })).toBeFalsy()
    await narrow.unmount()
    const tiny = await $.ui.mount({ ...MOUNT, surface, props: { ...MOUNT.props, bodyColumns: 20 } })
    expect(await tiny.find({ type: 'Text', text: /^Build 0● 1✗$/ })).toBeTruthy()
    expect(await tiny.find({ type: 'Text', text: /^Plan 1● 0✗$/ })).toBeTruthy()
    await tiny.unmount()
  }
})

// --- 2026-11-12 operator decisions: lost runs, task verb first, acks per event, --resume ---

const LIVE = '20991112T120000Z-sonnet-live01'
const liveFiles = (outcome: string | null, runJson?: string): Record<string, string> => ({
  [`${ROOT}/${LIVE}/run.json`]: runJson ?? JSON.stringify({ run_id: LIVE, model: 'sonnet', kind: 'claude', outcome, reason: null }),
  [`${ROOT}/${LIVE}/slots.json`]: JSON.stringify({ MODEL: 'sonnet', ROLE: 'Workhorse (sonnet)', TASK: 'fix the failing test' }),
})
const FIVE_MIN = 5 * 60 * 1000

test('lost: a run silent 5 minutes is lost, leaves working, raises the count; ack clears it', async ($, on) => {
  const world: World = { agents: [], dirs: [LIVE], files: liveFiles(null) }
  const clock = await start($, on, world)
  let ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · running$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /session · chief of staff · 1 working/ })).toBeTruthy()
  await ui.unmount()
  await clock.advance(FIVE_MIN)
  for (const surface of SURFACES) {
    const u = await $.ui.mount({ ...MOUNT, surface })
    expect(await u.find({ type: 'Text', text: /^sonnet · workhorse · lost$/ })).toBeTruthy()
    expect(await u.find({ type: 'Text', text: /session · chief of staff · 0 working/ })).toBeTruthy()
    expect(await u.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
    expect(await u.find({ type: 'Text', text: /^○ Build$/ })).toBeTruthy()
    await u.unmount()
  }
  const d = await $.ui.mount({ ...MOUNT, surface: 'desktop' })
  await d.press({ key: 'ack-Build' })
  expect(await d.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await d.unmount()
})

test('lost: a new event brings the run back to running and withdraws the alert; silent again is a new alert', async ($, on) => {
  const world: World = { agents: [], dirs: [LIVE], files: liveFiles(null), mtimes: {} }
  const clock = await start($, on, world)
  await clock.advance(FIVE_MIN)
  let ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await ui.press({ key: 'ack-Build' })
  await ui.unmount()
  // the run writes a new event
  const t1 = clock.now()
  world.files![`${ROOT}/${LIVE}/events.jsonl`] = '{"event": {"type": "tool"}}\n'
  world.mtimes![`${ROOT}/${LIVE}/events.jsonl`] = t1
  await clock.advance(1100)
  ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · running$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /session · chief of staff · 1 working/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await ui.unmount()
  // silent for 5 minutes again: a new lost event under the acknowledged id counts again (item 4)
  await clock.advance(FIVE_MIN)
  ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · lost$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
  await ui.unmount()
})

test('lost: an outcome written later shows the real outcome and withdraws the alert', async ($, on) => {
  const world: World = { agents: [], dirs: [LIVE], files: liveFiles(null), mtimes: {} }
  const clock = await start($, on, world)
  await clock.advance(FIVE_MIN)
  Object.assign(world.files!, liveFiles('green'))
  world.mtimes![`${ROOT}/${LIVE}/run.json`] = clock.now()
  await clock.advance(1100)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await ui.unmount()
})

test('lost: a malformed run.json that stays malformed falls under the same rule', async ($, on) => {
  const world: World = { agents: [], dirs: [LIVE], files: liveFiles(null, '{"outcome": "gre') }
  const clock = await start($, on, world)
  await clock.advance(FIVE_MIN)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · lost$/ })).toBeTruthy()
  await ui.unmount()
})

test('lost: a lost run is listed each poll but not read again until a file changes', async ($, on) => {
  const world: World = { agents: [], dirs: [LIVE], files: liveFiles(null), mtimes: {}, reads: [], lists: [] }
  const clock = await start($, on, world)
  await clock.advance(FIVE_MIN)
  world.reads!.length = 0
  world.lists!.length = 0
  await clock.advance(3000)
  expect(world.reads!.filter(p => p.includes(LIVE))).toEqual([])
  expect(world.lists!.filter(p => p.includes(LIVE)).length).toBeGreaterThanOrEqual(3)
  world.mtimes![`${ROOT}/${LIVE}/slots.json`] = clock.now()
  await clock.advance(1100)
  expect(world.reads!.some(p => p.endsWith(`${LIVE}/run.json`))).toBe(true)
})

test('station from the task verb first: a real Workhorse ROLE with "review PR 212" and "draft README"', async ($, on) => {
  const rev = '20991112T120100Z-sonnet-rev001'
  const drf = '20991112T120200Z-sonnet-drf001'
  const files = {
    ...runFiles(rev, 'sonnet', 'red', 'review PR 212'),
    ...runFiles(drf, 'sonnet', 'red', 'draft README'),
  }
  const world: World = { agents: [], dirs: [rev, drf], files }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal', props: { ...MOUNT.props, bodyColumns: 20 } })
  expect(await ui.find({ type: 'Text', text: /^Review 0● 1✗$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /^Write 0● 1✗$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /^Build 0● 0✗$/ })).toBeTruthy()
  await ui.unmount()
})

test('acks per event: a resumed subagent that fails again under an acknowledged id counts again', async ($, on) => {
  const world: World = { agents: [{ id: 's1', type: 'Plan', description: 'x', status: 'failed' }], dirs: [] }
  const clock = await start($, on, world)
  let ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
  await ui.press({ key: 'ack-Plan' })
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await ui.unmount()
  // still failed, same episode: stays acknowledged
  await clock.advance(2200)
  ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await ui.unmount()
  world.agents = [{ id: 's1', type: 'Plan', description: 'x', status: 'running' }]
  await clock.advance(1100)
  world.agents = [{ id: 's1', type: 'Plan', description: 'x', status: 'failed' }]
  await clock.advance(1100)
  for (const surface of SURFACES) {
    const u = await $.ui.mount({ ...MOUNT, surface })
    expect(await u.find({ type: 'Text', text: /1✗/ })).toBeTruthy()
    await u.unmount()
  }
})

test('acks: no count trim; a station keeps one key per delegate (older keys of a re-acked id dropped)', async ($, on) => {
  const runs = Array.from({ length: 205 }, (_, i) => failedRun(`12${String(Math.floor(i / 60)).padStart(2, '0')}${String(i % 60).padStart(2, '0')}`, 'x' + String(i).padStart(5, '0')))
  const world: World = { agents: [], dirs: runs.map(r => r.name), files: Object.assign({}, ...runs.map(r => r.files)) }
  const clock = await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /205✗/ })).toBeTruthy()
  await ui.press({ key: 'ack-Build' })
  await ui.unmount()
  await clock.advance(1100)
  const u = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  // the 200-id trim would have let 5 come back
  expect(await u.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await u.unmount()
  const rec = world.store!['session:S1'] as any
  expect(rec.acked.Build.length).toBe(205)
})

test('resume: the store record gives back session start and acks when $.state is empty', async ($, on) => {
  // An earlier process of session S1 started at 11:00 and acknowledged the failed run's one failure event.
  const F = failedRun('120100', 'fff000')
  const fMtime = Date.UTC(2099, 10, 12, 12, 2, 0)
  const world: World = {
    agents: [],
    dirs: [ABC, F.name],
    files: { ...ABC_FILES, ...F.files },
    mtimes: { [`${ROOT}/${F.name}/run.json`]: fMtime },
    store: { 'session:S1': { sessionStart: '2099-11-12T11:00:00.000Z', acked: { Build: [`${F.name}@${fMtime}`] }, alertAt: {}, savedAt: 1 } },
  }
  // the resumed process starts at 12:30, after both runs
  await start($, on, world, Date.UTC(2099, 10, 12, 12, 30, 0))
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · done$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^sonnet · workhorse · failed$/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('resume: another session id gets nothing back; the runs before its start stay off', async ($, on) => {
  const world: World = {
    agents: [],
    dirs: [ABC],
    files: ABC_FILES,
    sessionId: 'S2',
    store: { 'session:S1': { sessionStart: '2099-11-12T11:00:00.000Z', acked: {}, alertAt: {}, savedAt: 1 } },
  }
  await start($, on, world, Date.UTC(2099, 10, 12, 12, 30, 0))
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^sonnet · / })).toBeFalsy()
  await ui.unmount()
  expect((world.store!['session:S2'] as any).sessionStart).toBe('2099-11-12T12:30:00.000Z')
})

test('resume: a subagent failure acknowledged before the resume stays acknowledged', async ($, on) => {
  const world: World = {
    agents: [{ id: 's1', type: 'Plan', description: 'x', status: 'failed' }],
    dirs: [],
    store: { 'session:S1': { sessionStart: '2099-11-12T11:00:00.000Z', acked: { Plan: ['s1@42'] }, alertAt: { s1: 42 }, savedAt: 1 } },
  }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Plan · \? · failed$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /\d✗/ })).toBeFalsy()
  await ui.unmount()
})

test('store bound: at most 20 session records are kept, the newest', async ($, on) => {
  const store: Record<string, unknown> = { other: 1 }
  for (let i = 0; i < 25; i++) store['session:old' + i] = { sessionStart: '2099-01-01T00:00:00.000Z', acked: {}, alertAt: {}, savedAt: i }
  const world: World = { agents: [], dirs: [], store }
  await start($, on, world)
  const keys = Object.keys(store).filter(k => k.startsWith('session:'))
  expect(keys.length).toBe(20)
  expect(keys).toContain('session:S1')
  expect(keys).toContain('session:old24')
  expect(keys).not.toContain('session:old5')
  expect(store.other).toBe(1)
})

// Motion (terminal Raster). Blits are counted by a ui.blit hook beneath the plugin.
const blitsOf = (on: On, deny?: string) => {
  const blits: any[] = []
  on('ui.blit', (_$, e: any) => (blits.push(e), ({ value: deny ? { deny } : {} }) as any))
  return blits
}

test('motion: a running delegate starts the frame timer in the terminal; it stops when nothing moves', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = { agents: [{ id: 'a1', type: 'Explore', description: 'scout', status: 'running' }], dirs: [] }
  const clock = await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  const raster = await ui.find({ type: 'Raster' } as any)
  expect(raster).toBeTruthy()
  expect((raster as any).props.columns).toBe(56)
  // the static map stays under the Raster
  expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
  await clock.advance(500)
  expect(blits.length).toBeGreaterThanOrEqual(5)
  expect(blits.length).toBeLessThanOrEqual(7) // 80 ms a frame: 12.5 a second
  expect(blits[0]).toMatchObject({ requestId: PANE, key: 'map', columns: 56, rows: 16 })
  expect(new Set(blits.map(b => b.cells)).size).toBeGreaterThan(1)
  // the agent ends: the next poll marks it done; one return pulse flies to the centre, then the timer stops
  world.agents = [{ id: 'a1', type: 'Explore', description: 'scout', status: 'completed' }]
  await clock.advance(1200)
  const landing = blits.length
  await clock.advance(400)
  expect(blits.length).toBeGreaterThan(landing) // still moving: the return pulse has not landed
  await clock.advance(1200)
  const n = blits.length
  await clock.advance(2000)
  expect(blits.length).toBe(n)
  await ui.unmount()
})

test('motion: the timer keeps running while any agent still runs after the others ended (#191)', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = {
    agents: [
      { id: 'a', type: 'Explore', description: 'a', status: 'running' },
      { id: 'b', type: 'Explore', description: 'b', status: 'running' },
      { id: 'c', type: 'Explore', description: 'c', status: 'running' },
    ],
    dirs: [],
  }
  const clock = await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await clock.advance(500)
  world.agents[0]!.status = 'completed'
  world.agents[1]!.status = 'failed'
  await clock.advance(6000)
  const n = blits.length
  await clock.advance(1000)
  expect(blits.length).toBeGreaterThan(n + 5) // c still runs: the frames go on
  await ui.unmount()
})

test('motion: a render on another surface does not stop the terminal timer (#191)', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = { agents: [{ id: 'a1', type: 'Explore', description: 'scout', status: 'running' }], dirs: [] }
  const clock = await start($, on, world)
  const term = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await clock.advance(500)
  const desk = await $.ui.mount({ ...MOUNT, surface: 'desktop' })
  await desk.redraw()
  const n = blits.length
  await clock.advance(1000)
  expect(blits.length).toBeGreaterThan(n + 5) // the terminal pane still shows a running agent
  await desk.unmount()
  await term.unmount()
})

test('motion: no timer when nothing runs or alerts, on desktop, or below the minimum width', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = { agents: [{ id: 'p', type: 'Plan', description: 'x', status: 'idle' }], dirs: [] }
  const clock = await start($, on, world)
  let ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Raster' } as any)).toBeTruthy() // drawn still, no timer
  await clock.advance(1000)
  expect(blits.length).toBe(0)
  await ui.unmount()
  world.agents = [{ id: 'a1', type: 'Explore', description: 'scout', status: 'running' }]
  await clock.advance(1100)
  ui = await $.ui.mount({ ...MOUNT, surface: 'desktop' })
  expect(await ui.find({ type: 'Raster' } as any)).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
  await clock.advance(1000)
  expect(blits.length).toBe(0)
  await ui.unmount()
  ui = await $.ui.mount({ ...MOUNT, surface: 'terminal', props: { ...MOUNT.props, bodyColumns: 33 } })
  expect(await ui.find({ type: 'Raster' } as any)).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
  await clock.advance(1000)
  expect(blits.length).toBe(0)
  await ui.unmount()
})

// ui.close is not raisable from a test's $ (its ui noun is render/scroll/focus/press/input/select/mount), so the
// close handler is proven only by reading; an unmounted pane's refused blit (next test) stops the timer as well.
test('motion: a refused blit stops the timer and the pane falls back to the static map', async ($, on) => {
  const blits = blitsOf(on, 'not mounted')
  const world: World = { agents: [{ id: 'a1', type: 'Explore', description: 'scout', status: 'running' }], dirs: [] }
  const clock = await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await clock.advance(300)
  expect(blits.length).toBe(1)
  await ui.redraw()
  expect(await ui.find({ type: 'Raster' } as any)).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /^Explore · \? · running$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /session · chief of staff · 1 working/ })).toBeTruthy()
  await clock.advance(1000)
  expect(blits.length).toBe(1)
  await ui.unmount()
})

test('pass 3: the centre names the main session and its model; the feed lists delegates newest first', async ($, on) => {
  on('session.model', () => ({ value: 'claude-opus-5-5' }) as any)
  const world: World = { agents: [{ id: 'a1', type: 'Explore', description: 'scout the repo', status: 'running' }], dirs: [ABC], files: ABC_FILES }
  const clock = await start($, on, world)
  await clock.advance(1000)
  world.agents.push({ id: 'a2', type: 'Plan', description: 'plan the map', status: 'failed' })
  await clock.advance(1000)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /◉ main session · chief of staff · 1 working · claude-opus-5-5 ─/ })).toBeTruthy()
    expect(await ui.find({ type: 'Text', text: /^Explore: scout the repo$/ })).toBeTruthy()
    const rows = ((await ui.findAll({ type: 'Text', text: /^[●✗·◐] / } as any)) as any[]).filter(r => r.text.length === 80) // feed rows fill the width
    expect(rows.map(r => r.text.slice(0, 10))).toEqual(['✗ Plan    ', '● Explore ', '· sonnet  '])
    expect(rows[0].props.color).toBe('red')
    expect(rows[1].props.color).toBe('yellow')
    expect(rows[1].text.endsWith(' running')).toBe(true)
    expect(rows[2].props.dimColor).toBe(true)
    // the role column: dim on a running row and on a failed row too (Plan has no known rung: blank), word of the rung otherwise
    const roles = (await ui.findAll({ type: 'Text', text: /^workhorse\s*$/ } as any)) as any[]
    expect(roles.length).toBe(1)
    expect(roles[0].props.dimColor).toBe(true)
    await ui.unmount()
  }
})

test('pass 3: no model from the engine: the centre keeps its fixed label; no delegates: "Nothing is running."', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = { agents: [], dirs: [] }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /◉ main session · chief of staff · 0 working ─/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /^Nothing is running\.$/ })).toBeTruthy()
  expect(blits.length).toBe(0)
  await ui.unmount()
})

test('hierarchy: a Lead spawn keeps the timer only for its real dispatch and result, then stops', async ($, on) => {
  const blits = blitsOf(on)
  const world: World = { agents: [{ id: 'p', type: 'Plan', description: 'plan', status: 'completed' }], dirs: [] }
  const clock = await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  await clock.advance(500)
  expect(blits.length).toBe(0)
  world.agents.push({ id: 'c', type: 'Explore', description: 'scout', status: 'running', parentId: 'p' })
  await clock.advance(1100)
  await ui.redraw()
  expect(await ui.find({ type: 'Text', text: /Lead: Plan/ })).toBeTruthy()
  world.agents[1]!.status = 'completed'
  await clock.advance(1100)
  expect(blits.length).toBeGreaterThan(5) // the dispatch, the heartbeat and the result moved
  await clock.advance(3000)
  const n = blits.length
  await clock.advance(2000)
  expect(blits.length).toBe(n) // nothing runs and no event lives: the timer stopped
  await ui.unmount()
})

test('hierarchy: the static fallback names CoS, Lead and primary Worker on every surface', async ($, on) => {
  on('session.model', () => ({ value: 'claude-opus-5-5' }) as any)
  const world: World = { agents: [{ id: 'a', type: 'sonnet', description: 'fix the pane', status: 'running' }], dirs: [] }
  const clock = await start($, on, world)
  await clock.advance(1000)
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({ ...MOUNT, surface })
    expect(await ui.find({ type: 'Text', text: /^CoS: main session \(claude-opus-5-5\) · Lead: none, the CoS leads · Worker: sonnet$/ })).toBeTruthy()
    await ui.unmount()
  }
})

test('role column is dim on running, failed and finished rows; blank for an unknown rung', async ($, on) => {
  const world: World = { agents: [{ id: 'r1', type: 'haiku', description: 'scout x', status: 'running' }, { id: 'r2', type: 'opus', description: 'judge y', status: 'failed' }, { id: 'r3', type: 'sonnet', description: 'write z', status: 'completed' }, { id: 'r4', type: 'Explore', description: 'look', status: 'running' }], dirs: [], files: {} }
  const clock = await start($, on, world)
  await clock.advance(1000)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  for (const word of ['grunt', 'orchestrator', 'workhorse']) {
    const hit = ((await ui.findAll({ type: 'Text', text: new RegExp('^' + word + '\\s*$') } as any)) as any[])
    expect(hit.length).toBe(1)
    expect(hit[0].props.dimColor).toBe(true)
  }
  const rows = ((await ui.findAll({ type: 'Text', text: /^[●✗·◐] / } as any)) as any[]).filter(r => r.text.length === 80)
  expect(rows.length).toBe(4)
  const explore = rows.find(r => r.text.includes('Explore'))
  expect(explore.text.slice(17, 30)).toBe(' '.repeat(13)) // unknown rung: empty column, same width
  await ui.unmount()
})

test('session.start opens the pane once', async ($, on) => {
  const world: World = { agents: [], dirs: [], files: {}, opens: [] }
  await start($, on, world)
  expect(world.opens!.length).toBe(1)
  expect(world.opens![0].id).toBe('agents-inc-delegates')
})

test('a ui.open that throws does not fail session.start', async ($, on) => {
  const world: World = { agents: [], dirs: [], files: {}, opens: [], openFails: true }
  await start($, on, world)
  expect(world.opens!.length).toBe(1)
})
