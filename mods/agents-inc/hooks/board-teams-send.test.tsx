// Spec 050 Phase 3 T040: delivery and refusal. Routing is by stable target identity; a refused send keeps its target.
import { expect, mock, test } from 'claude-code/testing'

import { addFyi, newItems } from './board-items'
import { planSend, settle, MEMO_PREFIX, summary, teamKey } from './board-teams'

const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const memo = (teamId: string) => ({ kind: 'memo' as const, agentId: 'a8bb', alias: 'haiku', teamId, teamName: 'quadmesh' })

test('a Team line reply goes to that Team CoS by session id, unlabelled', () => {
  const p = planSend({ kind: 'team', id: 'sess-q', name: 'quadmesh' }, 'go ahead', 'own')
  expect(p).toMatchObject({ to: { sessionId: 'sess-q' }, text: 'go ahead', how: 'reply' })
})

test('a Memo to an own-session Worker goes by agent id with the self-identifying prefix', () => {
  const p = planSend(memo('own'), 'wrap up', 'own')
  expect(p).toMatchObject({ to: { agentId: 'a8bb' }, text: MEMO_PREFIX + 'wrap up', how: 'memo' })
})

test('a message to another Team delegate becomes an FYI to that Team CoS, recorded as FYI sent, not delivered to the Worker', () => {
  const items = newItems()
  const p = planSend(memo('sess-q'), 'stop at 5', 'own')
  expect(p.how).toBe('fyi')
  expect('sessionId' in p.to && p.to.sessionId).toBe('sess-q')
  const out = settle(p, 'stop at 5', { isDelivered: true }, items, [], T0)
  expect(out.delivered).toBe(true)
  expect(items.items[0]!.title).toBe('FYI sent to quadmesh about haiku, not delivered to the Worker')
  expect(items.items[0]!.context).toBe('stop at 5')
})

test('an undeliverable Memo is one FYI row with the text kept; the target stays', () => {
  const items = newItems()
  const sent: string[] = []
  const p = planSend(memo('own'), 'wrap up', 'own')
  const out = settle(p, 'wrap up', { isDelivered: false, reason: 'Agent could not be resumed' }, items, sent, T0)
  expect(out).toMatchObject({ delivered: false, close: false })
  expect(items.items).toHaveLength(1)
  expect(items.items[0]).toMatchObject({ kind: 'fyi', title: 'Memo to haiku not delivered: Agent could not be resumed', context: 'wrap up' })
  expect(sent).toEqual([])
})

test('a refused Team reply keeps the target open and records nothing', () => {
  const items = newItems()
  addFyi(items, 'earlier', 'x', T0)
  const p = planSend({ kind: 'team', id: 'sess-q', name: 'quadmesh' }, 'hi', 'own')
  const out = settle(p, 'hi', { isDelivered: false, reason: 'no live session' }, items, [], T0)
  expect(out).toMatchObject({ delivered: false, close: false, line: 'not delivered: no live session' })
  expect(items.items).toHaveLength(1)
  expect(settle(p, 'hi', undefined, items, [], T0).close).toBe(false) // no answer at all counts as refused
})

// --- through the pane: the real send call and the open region --------------------------------------------------------


// A plain-object store as the engine keeps one: the test reads it back through `map`.
function fakeStore(on: any, map: Record<string, unknown>) {
  on('store.get', (_$: any, e: any) => ({ value: map[e.key] === undefined ? undefined : JSON.parse(JSON.stringify(map[e.key])) }))
  on('store.set', (_$: any, e: any) => ((map[e.key] = JSON.parse(JSON.stringify(e.value))), { value: undefined }))
  on('store.delete', (_$: any, e: any) => (delete map[e.key], { value: undefined }))
  on('store.keys', () => ({ value: Object.keys(map) }))
}

type On = Parameters<Parameters<typeof test>[1]>[1]
async function start($: any, on: On, sends: any[], answer: () => unknown) {
  on('agent.register', (_$: any, e: any) => ({ value: { agent: `agents-inc:${e.name}` } }))
  on('tool.register', () => ({ value: {} }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 'own' }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'board' } }))
  on('agent.list', () => ({ value: [{ id: 'a8bb', type: 'agents-inc:haiku', description: 'scan', status: 'running' }] }))
  on('session.messages', () => ({ value: [] as any }))
  on('fs.list', () => {
    throw new Error('ENOENT')
  })
  on('ui.invalidate', () => ({ value: undefined }))
  for (const ev of ['PermissionRequest', 'Notification', 'SubagentStop', 'PostToolUse', 'PostToolUseFailure', 'PermissionDenied']) on(`classic.${ev}` as any, () => ({}))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.send', (_$: any, e: any) => (sends.push({ to: e.to, text: e.text }), answer() as any))
  on('process.spawn', async function* () {
    yield { stream: 'stdout' as const, text: JSON.stringify({ offered: false, models: [] }) }
    return { value: { code: 0, signal: null } }
  })
  fakeStore(on, { [teamKey('sess-q')]: summary('sess-q', 'quadmesh', 0, 2, T0 + 1000) })
  const clock = mock.clock(on, { now: T0 })
  await $.session.start({ cwd: '/work/ainc2', surface: 'desktop', isInteractive: true })
  await clock.advance(2100)
}
const mount = ($: any) => $.ui.mount({ plugin: 'agents-inc', component: 'Pane', requestId: 'Board', surface: 'terminal', props: { title: 'Board', isFocused: false, bodyColumns: 70, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } } as any)
// Act on the Board's footer Client, then read the pane with a fresh mount (a mount reads the state before its own key).
const act = async ($: any, k: string, data?: any) => {
  const ui = await mount($)
  if (data) await ui.post(data)
  else await ui.key({ key: k })
  await ui.unmount()
}
const read = async ($: any) => {
  const ui = await mount($)
  const t = (await ui.findAll({ type: 'Text' })).map((x: any) => String(x.text))
  await ui.unmount()
  return t
}
const send = async ($: any, k: string, data?: any) => (await act($, k, data), read($))

test('pane: a reply on a Team line sends to that session id; a refusal keeps the region open', async ($, on) => {
  const sends: any[] = []
  let ok = false
  await start($, on, sends, () => (ok ? { isDelivered: true } : { isDelivered: false, reason: 'no live session' }))
  await send($, 'down') // working row first
  await send($, 'down') // Team line
  let t = await send($, 'return')
  expect(t.some(x => x.includes('reply to quadmesh'))).toBe(true)
  t = await send($, '', { kind: 'reply', text: 'ship it' })
  expect(sends).toEqual([{ to: 'sess-q', text: 'ship it' }])
  expect(t.some(x => x.includes('not delivered: no live session'))).toBe(true)
  expect(t.some(x => x.includes('reply to quadmesh'))).toBe(true) // target kept
  ok = true
  t = await send($, '', { kind: 'reply', text: 'ship it' })
  expect(t.some(x => x.includes('reply to quadmesh'))).toBe(false)
  expect(t.some(x => x.includes('to quadmesh: ship it'))).toBe(false) // closed region shows no sent list
})

test('pane: m on an own working row sends the prefixed Memo by agent id; refused Memo leaves one FYI row', async ($, on) => {
  const sends: any[] = []
  await start($, on, sends, () => ({ isDelivered: false, reason: 'could not be resumed' }))
  await send($, 'down')
  let t = await send($, 'm')
  expect(t.some(x => x.includes('memo to haiku'))).toBe(true)
  t = await send($, '', { kind: 'reply', text: 'wrap up' })
  expect(sends).toEqual([{ to: 'a8bb', text: MEMO_PREFIX + 'wrap up' }])
  expect(t.some(x => x.includes('Memo to haiku not delivered: could not be resumed'))).toBe(true)
  expect(t.some(x => x.includes('memo to haiku'))).toBe(true) // target stays
})

test('pane: a message to another Team delegate sends an FYI to that CoS only', async ($, on) => {
  const sends: any[] = []
  await start($, on, sends, () => ({ isDelivered: true }))
  const t = await send($, '', { kind: 'tell', teamId: 'sess-q', teamName: 'quadmesh', agentId: 'a1db', alias: 'haiku', text: 'stop at 5' })
  expect(sends).toHaveLength(1)
  expect(sends[0].to).toBe('sess-q')
  expect(sends[0].text).toContain('stop at 5')
  expect(t.some(x => x.includes('FYI sent to quadmesh about haiku, not delivered to the Worker'))).toBe(true)
})
