// Spec 050 Phase 3 T039: golden scene 6 (folded Teams) and the shared Team data rules.
import { expect, mock, test } from 'claude-code/testing'

import { buildBoard, newMem } from './board-model'
import { plainBoard, renderBoard } from './board-render'
import { liveTeams, parseTeam, summary, teamKey, TEAM_STALE_MS } from './board-teams'
import { POLL_MS } from './board'

const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const SIZE = { onlyId: 'own-session' }
const rec = (id: string, name: string, needs: number, working: number, at = T0) => summary(id, name, needs, working, at)

test('the stale bound is three polls', () => {
  expect(TEAM_STALE_MS).toBe(3 * POLL_MS)
})

test('scene 6: other Teams fold to one count line each, two blank lines before them, no label', () => {
  const m = newMem()
  m.sessionId = 'own'
  m.items.items.push({ id: 'i1', kind: 'needs', title: 'Merge?', options: [], source: '', context: '', sessionId: 'own', turnId: 't', at: T0 })
  m.teams = liveTeams([rec('s-ainc2', 'ainc2', 1, 3), rec('s-quad', 'quadmesh', 0, 2)], 'own', T0)
  m.board = buildBoard(m, T0)
  const lines = plainBoard(renderBoard(m.board, { width: 60 }))
  const at = lines.indexOf('! ainc2       1 needs you · 3 working')
  expect(at).toBeGreaterThan(0)
  expect(lines[at + 1]).toBe('● quadmesh    2 working')
  expect(lines[at - 1]).toBe('')
  expect(lines[at - 2]).toBe('')
  expect(lines[at - 3]).not.toBe('')
  expect(lines.join('\n')).not.toMatch(/other sessions/i)
})

test('a Team line takes the selection and Enter fills no Item', () => {
  const m = newMem()
  m.teams = liveTeams([rec('s-q', 'quadmesh', 0, 2)], 'own', T0)
  m.board = buildBoard(m, T0)
  const r = plainBoard(renderBoard(m.board, { width: 60, selected: 'team:s-q' }))
  expect(r[0]).toBe('nothing to show')
  expect(r).toContain('▸ ● quadmesh    2 working')
  expect(r[r.length - 1]).toBe('↑↓ select  Enter reply')
})

test('readers drop own key, stale heartbeats and malformed values; needs-you first', () => {
  const ok = parseTeam(teamKey('a'), rec('a', 'alpha', 0, 1, T0 - TEAM_STALE_MS))
  const stale = parseTeam(teamKey('b'), rec('b', 'beta', 5, 5, T0 - TEAM_STALE_MS - 1))
  const own = parseTeam(teamKey('own'), rec('own', 'me', 1, 1))
  const bad = parseTeam(teamKey('c'), { id: 'other', name: 'x', at: T0 })
  const hot = parseTeam(teamKey('d'), rec('d', 'delta', 2, 0))
  expect(bad).toBeUndefined()
  expect(liveTeams([ok, stale, own, bad, hot], 'own', T0).map(t => t.id)).toEqual(['d', 'a'])
})

test('two Teams with one display name stay two lines: identity is the session id', () => {
  const t = liveTeams([rec('s1', 'same', 0, 1), rec('s2', 'same', 0, 1)], 'own', T0)
  expect(t.map(x => x.id).sort()).toEqual(['s1', 's2'])
})

// --- through the plugin: two sessions share Team data and each opens its own Team ----------------------------------------


// A plain-object store as the engine keeps one: the test reads it back through `map`.
function fakeStore(on: any, map: Record<string, unknown>) {
  on('store.get', (_$: any, e: any) => ({ value: map[e.key] === undefined ? undefined : JSON.parse(JSON.stringify(map[e.key])) }))
  on('store.set', (_$: any, e: any) => ((map[e.key] = JSON.parse(JSON.stringify(e.value))), { value: undefined }))
  on('store.delete', (_$: any, e: any) => (delete map[e.key], { value: undefined }))
  on('store.keys', () => ({ value: Object.keys(map) }))
}

type On = Parameters<Parameters<typeof test>[1]>[1]
async function start($: any, on: On, id: string | (() => string), opens: any[], seed: Record<string, unknown>, agents: any[]) {
  on('agent.register', (_$: any, e: any) => ({ value: { agent: `agents-inc:${e.name}` } }))
  on('tool.register', () => ({ value: {} }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: typeof id === 'function' ? id() : id }))
  on('session.end', (_$: any, e: any) => ({ sessionId: e.sessionId }) as any)
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'board' } }))
  on('agent.list', () => ({ value: agents }))
  on('session.messages', () => ({ value: [] as any }))
  on('fs.list', () => {
    throw new Error('ENOENT')
  })
  on('ui.invalidate', () => ({ value: undefined }))
  for (const ev of ['PermissionRequest', 'Notification', 'SubagentStop', 'PostToolUse', 'PostToolUseFailure', 'PermissionDenied']) on(`classic.${ev}` as any, () => ({}))
  on('ui.open', (_$: any, e: any) => (opens.push(e), { value: { isPlaced: true } }))
  on('process.spawn', async function* () {
    yield { stream: 'stdout' as const, text: JSON.stringify({ offered: false, models: [] }) }
    return { value: { code: 0, signal: null } }
  })
  fakeStore(on, seed)
  const clock = mock.clock(on, { now: T0 })
  await $.session.start({ cwd: '/work/ainc2', surface: 'desktop', isInteractive: true })
  return clock
}
const texts = async ($: any) => {
  const ui = await $.ui.mount({ plugin: 'agents-inc', component: 'Pane', requestId: 'Board', surface: 'terminal', props: { title: 'Board', isFocused: false, bodyColumns: 70, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } } as any)
  const t = (await ui.findAll({ type: 'Text' })).map((x: any) => String(x.text))
  await ui.unmount()
  return t
}

test('the poll writes only the own key and reads the other Teams; the open Team is always its own', async ($, on) => {
  const opens: any[] = []
  const seed: Record<string, any> = { [teamKey('s-quad')]: rec('s-quad', 'quadmesh', 0, 2, T0 + 1000), [teamKey('s-dead')]: rec('s-dead', 'gone', 3, 3, T0 - 10 * TEAM_STALE_MS) }
  const clock = await start($, on, 'own', opens, seed, [{ id: 'a1', type: 'agents-inc:haiku', description: 'scan', status: 'running' }])
  await clock.advance(2100)
  const own = seed[teamKey('own')] as any
  expect(own).toMatchObject({ id: 'own', name: 'ainc2', needs: 0, working: 1, flag: false })
  expect(seed[teamKey('s-quad')]).toEqual(seed[teamKey('s-quad')]) // another session's key is never written
  const t = await texts($)
  expect(t.some(x => x.includes('● quadmesh    2 working'))).toBe(true)
  expect(t.some(x => x.includes('gone'))).toBe(false)
  expect(t.filter(x => x.includes('ainc2')).length).toBe(0) // the own Team has no line
})

test('T037: a delegate or a needs-you in another Team opens Board without focus; an idle Team does not', async ($, on) => {
  const opens: any[] = []
  const seed: Record<string, any> = { [teamKey('s-idle')]: rec('s-idle', 'idle', 0, 0, T0 + 1000) }
  const clock = await start($, on, 'own', opens, seed, [])
  await clock.advance(2100)
  expect(opens).toHaveLength(0)
  seed[teamKey('s-q')] = rec('s-q', 'quadmesh', 0, 1, T0 + 2500)
  await clock.advance(2100)
  expect(opens).toHaveLength(1)
  expect(opens[0].focus).toBeUndefined()
})

test('a session never deletes another key; its own key goes at session.end; a second session.start replaces the poll', async ($, on) => {
  const opens: any[] = []
  const deletes: string[] = []
  let writes = 0
  const seed: Record<string, any> = new Proxy({ [teamKey('s-old')]: rec('s-old', 'ancient', 1, 1, T0 - 100 * 3600_000), [teamKey('bad')]: { junk: true } } as Record<string, any>, {
    deleteProperty: (t, k) => (deletes.push(String(k)), delete t[k as string]),
    set: (t, k, v) => ((t[k as string] = v), writes++, true),
  })
  const clock = await start($, on, 'own', opens, seed, [])
  await clock.advance(2100)
  expect(seed[teamKey('own')]).toBeDefined()
  expect(deletes).toEqual([]) // stale and malformed peers are ignored, not deleted
  expect(seed[teamKey('s-old')]).toBeDefined()
  // a second session.start in this process: one poll only (the first interval is cancelled)
  await $.session.start({ cwd: '/work/ainc2', surface: 'desktop', isInteractive: true })
  writes = 0
  await clock.advance(2100)
  expect(writes).toBe(1)
  await $.session.end({ reason: 'exit', sessionId: 'own', resume: { id: 'x' } } as any)
  expect(deletes).toEqual([teamKey('own')])
  writes = 0
  await clock.advance(6000)
  expect(writes).toBe(0) // the poll is cancelled
})

test('the poll keeps writing across several intervals after one session.start', async ($, on) => {
  let writes = 0
  const seed: Record<string, any> = new Proxy({} as Record<string, any>, { set: (t, k, v) => ((t[k as string] = v), writes++, true) })
  const clock = await start($, on, 'own', [], seed, [{ id: 'a1', type: 'agents-inc:haiku', description: 'scan', status: 'running' }])
  writes = 0
  for (let i = 0; i < 5; i++) await clock.advance(2000)
  expect(writes).toBeGreaterThanOrEqual(4)
  expect((await texts($)).some(x => x.includes('haiku'))).toBe(true) // the delegate shows under WORKING
})

test('session.end stops the poll only when it is this session that ends; /clear resets and keeps polling under the new id', async ($, on) => {
  let writes = 0
  let id = 'own'
  const seed: Record<string, any> = new Proxy({} as Record<string, any>, { set: (t, k, v) => ((t[k as string] = v), writes++, true) })
  const clock = await start($, on, () => id, [], seed, [{ id: 'a1', type: 'agents-inc:haiku', description: 'scan', status: 'running' }])
  await clock.advance(2100)
  await $.session.end({ reason: 'exit', sessionId: 'someone-else', resume: { id: 'x' } } as any)
  writes = 0
  await clock.advance(4000)
  expect(writes).toBeGreaterThanOrEqual(2) // a stray end for another id changes nothing
  // /clear: same process, new session id, no session.start
  id = 'new-id'
  await $.session.end({ reason: 'clear', sessionId: 'own', resume: { id: 'x' } } as any)
  expect(seed[teamKey('own')]).toBeUndefined()
  writes = 0
  await clock.advance(4100)
  expect(writes).toBeGreaterThanOrEqual(2)
  expect(seed[teamKey('new-id')]).toBeDefined()
  expect(seed[teamKey('own')]).toBeUndefined()
  await $.session.end({ reason: 'exit', sessionId: 'new-id', resume: { id: 'x' } } as any)
  writes = 0
  await clock.advance(6000)
  expect(writes).toBe(0)
})
