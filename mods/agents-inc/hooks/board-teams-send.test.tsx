// Spec 050 Phase 3 T040: delivery and refusal. Routing is by stable target identity; a refused send keeps its target.
import { expect, mock, test } from 'claude-code/testing'

import { addFyi, newItems } from './board-items'
import { fillSend, parseSend, parseTell, planSend, settle, MEMO_PREFIX, summary, teamKey } from './board-teams'

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
async function start($: any, on: On, sends: any[], answer: () => unknown, status: () => string = () => 'running') {
  on('agent.register', (_$: any, e: any) => ({ value: { agent: `agents-inc:${e.name}` } }))
  on('tool.register', () => ({ value: {} }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 'own' }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'board' } }))
  on('agent.list', () => ({ value: [{ id: 'a8bb', type: 'agents-inc:haiku', description: 'scan', status: status() }] }))
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
// The operator's own Enter in the composer stamps origin composer; a test reaches the hook with that origin directly.
const typed = ($: any, command: string, args: string, origin: any = { kind: 'composer' }) => $.command.run({ command, args, origin } as any)
const key = async ($: any, k: string) => {
  const ui = await mount($)
  await ui.key({ key: k })
  await ui.unmount()
}

test('pane: Enter on a Team line fills /board-send with a short ref, m fills /board-memo with the agent ref', async ($, on) => {
  const sends: any[] = []
  const fills: string[] = []
  on('prompt.fill', (_$: any, e: any) => (fills.push(e.text), { isFilled: true }))
  await start($, on, sends, () => ({ isDelivered: true }))
  await key($, 'down')
  await key($, 'm')
  await key($, 'down')
  await key($, 'return')
  expect(fills).toEqual(['/board-memo a8bb ', '/board-send sess '])
  expect(sends).toEqual([]) // filling sends nothing
})

test('args parsing and ref refusals', () => {
  const teams = [summary('abcd1', 'one', 0, 1, T0), summary('abcd2', 'two', 0, 1, T0), summary('zzzz9', 'three', 0, 1, T0)]
  expect(parseSend('zzzz ship it now', teams)).toMatchObject({ ok: true, text: 'ship it now', target: { kind: 'team', id: 'zzzz9' } })
  expect(parseSend('abcd hi', teams)).toEqual({ ok: false, line: 'not delivered: "abcd" matches 2 Teams; type more of the ref' })
  expect(parseSend('qqqq hi', teams)).toMatchObject({ ok: false, line: expect.stringContaining('not delivered: no live Team matches "qqqq"') })
  expect(parseSend('zzzz   ', teams)).toEqual({ ok: false, line: 'not delivered: no text' })
  expect(parseSend('', teams)).toMatchObject({ ok: false })
  expect(parseTell('zzzz haiku stop at 5', teams)).toMatchObject({ ok: true, text: 'stop at 5', target: { alias: 'haiku', teamId: 'zzzz9' } })
  expect(parseTell('zzzz haiku', teams)).toMatchObject({ ok: false })
  expect(fillSend({ id: 'zzzz9' })).toBe('/board-send zzzz ')
})

test('/board-send: person origin sends by session id; stale ref and refused send keep nothing sent or open', async ($, on) => {
  const sends: any[] = []
  let ok = true
  await start($, on, sends, () => (ok ? { isDelivered: true } : { isDelivered: false, reason: 'no live session' }))
  expect(await typed($, 'board-send', 'sess ship it')).toMatchObject({ text: 'Sent.' })
  expect(sends).toEqual([{ to: 'sess-q', text: 'ship it' }])
  expect((await typed($, 'board-send', 'nope ship it')).text).toContain('not delivered: no live Team matches "nope"')
  expect(sends).toHaveLength(1)
  ok = false
  expect((await typed($, 'board-send', 'sess again')).text).toBe('not delivered: no live session')
})

test('commands from a plugin, the model or the bridge send nothing', async ($, on) => {
  const sends: any[] = []
  await start($, on, sends, () => ({ isDelivered: true }))
  for (const origin of [{ kind: 'plugin', name: 'x' }, { kind: 'model' }, { kind: 'sdk' }, null]) {
    for (const c of ['board-send', 'board-memo', 'board-tell']) {
      expect((await typed($, c, 'sess a8bb hello', origin)).text).toMatch(/^not delivered: only the operator/)
    }
  }
  expect(sends).toEqual([])
})

test('/board-memo: prefixed Memo by agent id; refused Memo leaves one FYI row', async ($, on) => {
  const sends: any[] = []
  await start($, on, sends, () => ({ isDelivered: false, reason: 'could not be resumed' }))
  const r = await typed($, 'board-memo', 'a8bb wrap up')
  expect(sends).toEqual([{ to: 'a8bb', text: MEMO_PREFIX + 'wrap up' }])
  expect(r.text).toBe('not delivered: could not be resumed')
  expect((await read($)).some(x => x.includes('Memo to haiku not delivered: could not be resumed'))).toBe(true)
})

test('/board-tell: an FYI to that CoS only', async ($, on) => {
  const sends: any[] = []
  await start($, on, sends, () => ({ isDelivered: true }))
  await typed($, 'board-tell', 'sess haiku stop at 5')
  expect(sends).toHaveLength(1)
  expect(sends[0].to).toBe('sess-q')
  expect(sends[0].text).toContain('stop at 5')
  expect((await read($)).some(x => x.includes('FYI sent to quadmesh about haiku, not delivered to the Worker'))).toBe(true)
})

const read = async ($: any) => {
  const ui = await mount($)
  const t = (await ui.findAll({ type: 'Text' })).map((x: any) => String(x.text))
  await ui.unmount()
  return t
}

test('/board-memo to a finished Worker sends nothing (no resume) and leaves one FYI row with the text', async ($, on) => {
  const sends: any[] = []
  let st = 'running'
  await start($, on, sends, () => ({ isDelivered: true }), () => st)
  st = 'completed' // finished after the poll saw it running: the send-time check must catch it
  const r = await typed($, 'board-memo', 'a8bb wrap up')
  expect(sends).toEqual([])
  expect(r.text).toBe('not delivered: worker finished')
  expect((await read($)).some(x => x.includes('Memo to haiku not delivered: worker finished'))).toBe(true)
})

test('footer says Esc, then type after a fill, and clears on the next key', async ($, on) => {
  const sends: any[] = []
  on('prompt.fill', () => ({ isFilled: true }))
  await start($, on, sends, () => ({ isDelivered: true }))
  await key($, 'down')
  await key($, 'm')
  const ui = await mount($)
  expect(((await ui.find({ type: 'Client' })) as any)?.props?.props.keys).toBe('Esc, then type')
  await ui.unmount()
  await key($, 'down')
  const ui2 = await mount($)
  expect(((await ui2.find({ type: 'Client' })) as any)?.props?.props.keys).not.toBe('Esc, then type')
  await ui2.unmount()
})
