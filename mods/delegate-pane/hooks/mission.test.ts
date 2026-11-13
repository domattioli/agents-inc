import { expect, test } from 'claude-code/testing'

import { MAIN_ROLE, hierarchy, hierarchyLines, roleOf, ackKey, categoryOf, dirModel, duration, ellipsis, feed, isDryRun, layoutFor, lifecycleOf, LOST_MS, runFromFiles, rungOf, sessionRuns, stations, statusLine, withLost } from './mission'
import { RUNGS } from './rungs'
import type { Delegate } from './mission'

// Plan R2 fixture table: 14 rows, expected values are the provisional ruling.
const TABLE: Array<[string, string | undefined, string]> = [
  ['Orchestrator: batch open issues', undefined, 'Scout'],
  ['Orchestrator: mod pane spec pipeline', undefined, 'Plan'],
  ['Dispatch sonnet to file the agents-inc issue', undefined, 'Write'],
  ['read the tests and list failures', undefined, 'Scout'],
  ['fix the failing test in ledger.py', undefined, 'Build'],
  ['review PR 212 for correctness', undefined, 'Review'],
  ['check-in status card', undefined, 'Other'],
  ['summarize the logs', undefined, 'Scout'],
  ['implement mission.ts per plan', undefined, 'Build'],
  ['draft the README section', undefined, 'Write'],
  ['design the station layout', undefined, 'Plan'],
  ['verify gates pass, then report', undefined, 'Review'],
  ['find the pane source', 'Explore', 'Scout'],
  ['anything', 'Plan', 'Plan'],
]

test('categoryOf: the 14-row table of plan R2', () => {
  expect(TABLE.length).toBe(14)
  for (const [text, subagentType, want] of TABLE) expect([text, categoryOf({ text, subagentType })]).toEqual([text, want])
})

test('categoryOf: structured signals beat text, grunt fallback, other', () => {
  expect(categoryOf({ text: 'fix it', taskKind: 'review' })).toBe('Review')
  expect(categoryOf({ text: 'zzz', role: 'Workhorse (sonnet), dispatched' })).toBe('Build')
  expect(categoryOf({ text: 'zzz', role: 'Grunt scout (luna)' })).toBe('Scout')
  expect(categoryOf({ text: 'zzz', subagentType: 'claude-code-guide' })).toBe('Scout')
  expect(categoryOf({ text: 'zzz', rung: 'grunt' })).toBe('Scout')
  expect(categoryOf({ text: 'zzz', rung: 'workhorse' })).toBe('Other')
  expect(categoryOf({ text: 'Haiku random task 1', subagentType: 'general-purpose' })).toBe('Scout')
  expect(categoryOf({ text: 'Haiku random task 1', subagentType: 'general-purpose', rung: 'workhorse' })).toBe('Scout')
  expect(categoryOf({ text: 'review PR 212', subagentType: 'general-purpose' })).toBe('Review')
})

test('lifecycleOf: every mapping of plan R4', () => {
  expect(lifecycleOf('subagent', 'running')).toBe('running')
  expect(lifecycleOf('subagent', 'finished')).toBe('done')
  expect(lifecycleOf('subagent', 'completed')).toBe('done')
  expect(lifecycleOf('subagent', 'failed')).toBe('failed')
  expect(lifecycleOf('subagent', 'error')).toBe('failed')
  expect(lifecycleOf('subagent', 'killed')).toBe('failed')
  expect(lifecycleOf('dispatch', undefined)).toBe('running')
  expect(lifecycleOf('dispatch', null)).toBe('running')
  expect(lifecycleOf('dispatch', 'unverified')).toBe('review')
  expect(lifecycleOf('dispatch', 'green')).toBe('done')
  expect(lifecycleOf('dispatch', 'red', 'quota-paused')).toBe('paused')
  expect(lifecycleOf('dispatch', 'red', 'rc-nonzero')).toBe('failed')
  for (const o of ['red', 'cancelled', 'blocked', 'launch-failed', 'refused-cap', 'refused-unknown']) expect(lifecycleOf('dispatch', o)).toBe('failed')
})

test('lifecycleOf: engine AgentStatus live values never map to done (A)', () => {
  expect(lifecycleOf('subagent', 'pending')).toBe('running')
  expect(lifecycleOf('subagent', 'waiting')).toBe('paused')
  expect(lifecycleOf('subagent', 'idle')).toBe('paused')
  expect(lifecycleOf('subagent', 'something-new')).toBe('running')
  expect(lifecycleOf('subagent', '')).toBe('running')
})

test('isDryRun: only outcome dry-run (B)', () => {
  expect(isDryRun('{"outcome": "dry-run"}')).toBe(true)
  expect(isDryRun('{"outcome": "red"}')).toBe(false)
  expect(isDryRun(undefined)).toBe(false)
  expect(isDryRun('{oops')).toBe(false)
})

test('rungOf: model id, nickname, unknown gives ?', () => {
  expect(rungOf('sonnet')).toBe('workhorse')
  expect(rungOf('gpt-6-luna')).toBe('grunt')
  expect(rungOf('', 'agents-inc:terra')).toBe('workhorse')
  expect(rungOf('mystery-model')).toBe('?')
  expect(rungOf('', 'general-purpose')).toBe('?')
})

test('sessionRuns drops runs before the session start (UTC id prefix)', () => {
  const names = ['20991101T000000Z-sonnet-old000', '20991112T120000Z-sonnet-abc123', '20991112T120500Z-luna-def456', 'notes', '.hidden']
  expect(sessionRuns(names, '2099-11-12T11:59:59.500Z')).toEqual(['20991112T120000Z-sonnet-abc123', '20991112T120500Z-luna-def456'])
  expect(sessionRuns(names, '2099-11-12T12:00:01Z')).toEqual(['20991112T120500Z-luna-def456'])
  expect(sessionRuns(names, 'not a date')).toEqual([])
})

// Inlined from mods/delegate-pane/hooks/fixtures/runs/20991112T120000Z-sonnet-abc123 (tests cannot read disk).
const ABC_RUN = '{"run_id": "20991112T120000Z-sonnet-abc123", "model": "sonnet", "kind": "claude", "cwd": "/work", "effort": "medium", "outcome": "green", "reason": null}'
const ABC_SLOTS = '{"MODEL": "sonnet", "ROLE": "Workhorse (sonnet), dispatched by Orchestrator (opus).", "TASK": "Implement the widget parser in widget.py. Then run its tests."}'
// Inlined from mods/delegate-pane/hooks/fixtures/runs/20991112T120500Z-luna-def456 (events.jsonl and slots.json, no run.json).
const DEF_EVENTS = '{"v": 1, "seq": 1, "ts": "2099-11-12T12:05:00.000Z", "source": "agents-inc", "event": {"type": "run.start", "run_id": "20991112T120500Z-luna-def456", "model": "luna", "kind": "codex"}}\n'
const DEF_SLOTS = '{"MODEL": "luna", "ROLE": "Grunt scout (luna), dispatched by Orchestrator (opus).", "TASK": "Read the widget docs and list every config key."}'

test('runFromFiles: finished run (fixture abc123)', () => {
  expect(runFromFiles(ABC_RUN, ABC_SLOTS, '20991112T120000Z-sonnet-abc123')).toEqual({
    id: '20991112T120000Z-sonnet-abc123',
    source: 'dispatch',
    nickname: 'sonnet',
    rung: 'workhorse',
    task: 'Implement the widget parser in widget.py. Then run its tests.',
    category: 'Build',
    state: 'done',
  })
})

test('runFromFiles: dir with events.jsonl only, no run.json (fixture def456)', () => {
  const d = runFromFiles(undefined, undefined, '20991112T120500Z-luna-def456', DEF_EVENTS)
  expect(d).toMatchObject({ id: '20991112T120500Z-luna-def456', nickname: 'luna', rung: 'grunt', state: 'running', task: '' })
  const withSlots = runFromFiles(undefined, DEF_SLOTS, '20991112T120500Z-luna-def456', DEF_EVENTS)
  expect(withSlots).toMatchObject({ category: 'Scout', state: 'running' })
})

test('runFromFiles: nothing readable falls back to the dir name; bad JSON is ignored', () => {
  expect(runFromFiles('{oops', 'nope', '20991112T120900Z-terra-aaaaaa')).toMatchObject({ nickname: 'terra', rung: 'workhorse', state: 'running', category: 'Other' })
})

const D = (id: string, category: Delegate['category'], state: Delegate['state']): Delegate => ({ id, source: 'dispatch', nickname: 'x', rung: '?', task: '', category, state })

test('stations: order, lit, unacked ids', () => {
  const ss = stations([D('a', 'Build', 'failed'), D('b', 'Build', 'failed'), D('c', 'Scout', 'review'), D('d', 'Write', 'done')], { Build: ['a@0'] })
  expect(ss.map(s => s.category)).toEqual(['Review', 'Build', 'Write', 'Scout', 'Plan', 'Other'])
  expect(ss[1]).toMatchObject({ lit: false, unacked: ['b@0'] })
  expect(ss[3].lit).toBe(true)
  expect(ss[2]).toMatchObject({ lit: false, unacked: [] })
})

test('layoutFor: grid, stacked, line', () => {
  expect([layoutFor(120), layoutFor(70), layoutFor(69), layoutFor(30), layoutFor(29)]).toEqual(['grid', 'grid', 'stacked', 'stacked', 'line'])
})

// Item 2 (2026-11-12): the task verb decides before ROLE; real ROLE values start with the rung word.
test('categoryOf: task verb beats a real-shaped ROLE; ROLE only when the text matches nothing', () => {
  const role = 'Workhorse (sonnet), dispatched by Orchestrator (opus).'
  expect(categoryOf({ text: 'review PR 212', role, rung: 'workhorse' })).toBe('Review')
  expect(categoryOf({ text: 'draft README', role, rung: 'workhorse' })).toBe('Write')
  expect(categoryOf({ text: 'Read the widget docs', role: 'Workhorse (sonnet)' })).toBe('Scout')
  expect(categoryOf({ text: 'design the layout', role: 'Grunt scout (luna)' })).toBe('Plan')
  expect(categoryOf({ text: 'check-in card', role })).toBe('Build')
  const slots = JSON.stringify({ MODEL: 'sonnet', ROLE: role, TASK: 'review PR 212 for correctness' })
  expect(runFromFiles('{"model": "sonnet"}', slots, '20991112T120000Z-sonnet-abc123').category).toBe('Review')
})

// Item 3: the dir-name fallback keeps a model id that holds `-`; a sanitized OpenRouter slug still finds its rung.
test('dirModel and the dir-name fallback: gpt-6-luna, not gpt; sanitized slugs', () => {
  expect(dirModel('20991112T120000Z-gpt-6-luna-abc123')).toBe('gpt-6-luna')
  expect(dirModel('20991112T120000Z-sonnet-abc123')).toBe('sonnet')
  expect(dirModel('notes')).toBe('')
  expect(runFromFiles(undefined, undefined, '20991112T120000Z-gpt-6-luna-abc123')).toMatchObject({ nickname: 'gpt-6-luna', rung: 'grunt' })
  expect(rungOf('nvidia_nemotron-3.5-lightning_free')).toBe('grunt')
  expect(rungOf('google_gemma-4-31b-it_free')).toBe('grunt')
  expect(rungOf('gemini-2.5-flash')).toBe('grunt')
  expect(rungOf('gpt-6.1-sol')).toBe('orchestrator')
  for (const name of Object.keys(RUNGS)) expect([name, rungOf(name)]).not.toEqual([name, '?'])
})

const RD = (state: Delegate['state'], extra: Partial<Delegate> = {}): Delegate => ({ ...D('r', 'Build', state), ...extra })

// Item 1: lost after LOST_MS of no change; only a dispatch run with no outcome.
test('withLost: a running dispatch run silent for LOST_MS is lost, named by its last event', () => {
  expect(LOST_MS).toBe(300000)
  expect(withLost(RD('running'), 1000, 1000 + LOST_MS)).toMatchObject({ state: 'lost', alertAt: 1000, newest: 1000 })
  expect(withLost(RD('running'), 1000, 1000 + LOST_MS - 1).state).toBe('running')
  expect(withLost(RD('running'), undefined, 1e15).state).toBe('running')
  expect(withLost(RD('failed'), 0, 1e15).state).toBe('failed')
  expect(withLost(RD('review'), 0, 1e15).state).toBe('review')
  expect(withLost({ ...RD('running'), source: 'subagent' }, 0, 1e15).state).toBe('running')
})

// Items 1 and 4: lost counts like a failure, is not lit; an ack covers one event, not the id forever.
test('stations: lost raises the count; an ack key names id and event time', () => {
  const lost = RD('lost', { alertAt: 5 })
  const [, build] = stations([lost], {})
  expect(build).toMatchObject({ lit: false, unacked: ['r@5'] })
  expect(stations([lost], { Build: [ackKey(lost)] })[1]?.unacked).toEqual([])
  // the same id fails again later: a new event, counted again
  expect(stations([RD('failed', { alertAt: 9 })], { Build: ['r@5'] })[1]?.unacked).toEqual(['r@9'])
})

// Pass 3 narration: status line and feed from mission data only.
const F = (id: string, state: Delegate['state'], startedAt?: number, endedAt?: number, task = 'task ' + id): Delegate =>
  ({ id, source: 'subagent', nickname: id, rung: '?', task, category: 'Build', state, startedAt, endedAt })

test('statusLine: nothing running, or the newest running delegate and N more', () => {
  expect(statusLine([])).toBe('Nothing is running.')
  expect(statusLine([F('a', 'done', 1, 2)])).toBe('Nothing is running.')
  expect(statusLine([F('a', 'running', 1), F('b', 'review', 5), F('c', 'running', 3)])).toBe('b: task b and 2 more')
  const long = statusLine([F('a', 'running', 1, undefined, 'x'.repeat(200)), F('b', 'running', 0)], 40)
  expect(long.length).toBe(40)
  expect(long.endsWith('… and 1 more')).toBe(true)
})

test('feed: newest on top, row states, ellipsis, right column, capped', () => {
  const rows = feed([F('old', 'done', 1000, 1850), F('bad', 'failed', 2000, 3500), F('now', 'running', 3000), F('p', 'paused', 2500), F('q', 'done', 500)], 60, 4)
  expect(rows.map(r => r.id)).toEqual(['now', 'p', 'bad', 'old'])
  expect(rows.map(r => r.kind)).toEqual(['running', 'paused', 'failed', 'done'])
  expect(rows.map(r => r.bullet)).toEqual(['●', '◐', '✗', '·'])
  expect(rows.map(r => r.right)).toEqual(['running', 'paused', '1.5 s', '850 ms'])
  for (const r of rows) expect(r.text.length).toBe(60)
  expect(rows[0]!.text.endsWith(' running')).toBe(true)
  const cut = feed([F('a', 'running', 1, undefined, 'y'.repeat(100))], 50, 5)[0]!
  expect(cut.task.endsWith('…')).toBe(true)
  expect(cut.text.length).toBe(50)
  expect(feed([F('u', 'done')], 60, 5)[0]!.right).toBe('—') // no times known: no duration invented
  expect(feed([], 60, 5)).toEqual([])
  expect(duration(65000)).toBe('1m 05s')
  expect(ellipsis('abcdef', 4)).toBe('abc…')
})

const RW = (id: string, rung: string, state: Delegate['state'], startedAt = 1, endedAt?: number): Delegate => ({ ...F(id, state, startedAt, endedAt), rung })

test('feed: a dim role column between name and task, fixed width, for every row state', () => {
  const rows = feed([RW('a', 'grunt', 'done', 1, 2), RW('b', 'orchestrator', 'running', 5), RW('c', 'workhorse', 'failed', 4, 6), RW('d', 'executive', 'paused', 3)], 80, 5)
  expect(rows.map(r => r.role)).toEqual(['orchestrator', 'workhorse', 'executive', 'grunt'])
  for (const r of rows) {
    expect(r.roleCol.length).toBe('orchestrator'.length + 1) // sized to the longest word in use, plus a space
    expect(r.text.length).toBe(80)
    expect(r.text).toBe(r.lead + r.roleCol + r.tail)
    expect(r.lead.length).toBe(2 + 14 + 1) // the role starts right after the name
  }
  expect(rows[1]!.roleCol).toBe('workhorse    ')
  // width is sized to the rows shown, not the longest word anywhere
  expect(feed([RW('a', 'grunt', 'running')], 80, 5)[0]!.roleCol).toBe('grunt ')
})

test('feed: unknown rung gives a blank role; no known role in view means no column', () => {
  const mixed = feed([RW('a', 'workhorse', 'running', 2), RW('b', '?', 'running', 1)], 80, 5)
  expect(mixed[1]!.role).toBe('')
  expect(mixed[1]!.roleCol).toBe(' '.repeat('workhorse'.length + 1))
  expect(mixed[1]!.text.length).toBe(80)
  const none = feed([RW('a', '?', 'running')], 80, 5)[0]!
  expect(none.roleCol).toBe('')
  expect(none.text).toBe(feed([F('a', 'running', 1)], 80, 5)[0]!.text)
  expect(roleOf({ rung: 'lead' })).toBe('') // roles assigned per task are not guessed
})

test('feed: a narrow pane drops the role column before the task is cut further', () => {
  const wide = feed([RW('a', 'orchestrator', 'running', 1, undefined)], 60, 5)[0]!
  expect(wide.roleCol).not.toBe('')
  const narrow = feed([RW('a', 'orchestrator', 'running', 1, undefined)], 50, 5)[0]!
  expect(narrow.roleCol).toBe('')
  expect(narrow.text.length).toBe(50)
  expect(narrow.task).toBe('task a') // task width is the same as with no role at all
  const tight = feed([RW('a', 'orchestrator', 'running', 1, undefined)], 50, 5)[0]!
  const noRole = feed([F('a', 'running', 1)], 50, 5)[0]!
  expect(tight.text).toBe(noRole.text)
})

test('the main session role is the glossary Chief of Staff', () => {
  expect(MAIN_ROLE).toBe('chief of staff')
})

const hd = (id: string, rung: string, extra: Partial<Delegate> = {}): Delegate => ({
  id, source: 'subagent', nickname: id, rung, task: '', category: 'Build', state: 'running', ...extra,
})

test('hierarchy: the Lead is a delegate that started delegates of its own', () => {
  expect(hierarchy([hd('a', 'orchestrator'), hd('b', 'workhorse')]).lead).toBeUndefined()
  expect(hierarchy([hd('a', 'grunt'), hd('b', 'workhorse', { parentId: 'a' })]).lead?.id).toBe('a') // rung alone never makes a Lead
  expect(hierarchy([hd('b', 'workhorse', { parentId: 'gone' })]).lead).toBeUndefined() // parent not on the map
  expect(hierarchy([hd('a', 'workhorse', { parentId: 'a' })]).lead).toBeUndefined() // no self-parent
})

test('hierarchy: several candidates: higher rung, then earliest start, then list order', () => {
  const kids = [hd('k1', 'grunt', { parentId: 'w' }), hd('k2', 'grunt', { parentId: 'o' }), hd('k3', 'grunt', { parentId: 'o2' })]
  expect(hierarchy([hd('w', 'workhorse', { startedAt: 0 }), hd('o', 'orchestrator', { startedAt: 50 }), ...kids.slice(0, 2)]).lead?.id).toBe('o')
  expect(hierarchy([hd('o', 'orchestrator', { startedAt: 50 }), hd('o2', 'orchestrator', { startedAt: 10 }), ...kids.slice(1)]).lead?.id).toBe('o2')
  expect(hierarchy([hd('o', 'orchestrator'), hd('o2', 'orchestrator', { startedAt: 10 }), ...kids.slice(1)]).lead?.id).toBe('o2') // unknown start last
  expect(hierarchy([hd('o', 'orchestrator'), hd('o2', 'orchestrator'), ...kids.slice(1)]).lead?.id).toBe('o')
})

test('hierarchy: primary Worker is the Lead child on the workhorse rung with the newest running start; absent when none runs', () => {
  const lead = hd('L', 'orchestrator', { startedAt: 0 })
  const all = [
    lead,
    hd('w1', 'workhorse', { parentId: 'L', startedAt: 10 }),
    hd('w2', 'workhorse', { parentId: 'L', startedAt: 20 }),
    hd('w3', 'workhorse', { parentId: 'L', startedAt: 30, state: 'done' }),
    hd('g', 'grunt', { parentId: 'L', startedAt: 40 }),
    hd('free', 'workhorse', { startedAt: 50 }), // not the Lead's: never the Lead's Worker
  ]
  expect(hierarchy(all).worker?.id).toBe('w2')
  expect(hierarchy(all.map(x => (x.id === 'w1' || x.id === 'w2' ? { ...x, state: 'failed' as const } : x))).worker).toBeUndefined()
  // no Lead: among all delegates
  expect(hierarchy([hd('a', 'workhorse', { startedAt: 1 }), hd('b', 'workhorse', { startedAt: 2 }), hd('c', 'grunt', { startedAt: 3 })]).worker?.id).toBe('b')
  expect(hierarchy([hd('c', 'grunt')]).worker).toBeUndefined()
})

test('hierarchy lines: the static map names CoS, Lead and primary Worker in one or two lines', () => {
  expect(hierarchyLines([], 'fable')).toEqual(['CoS: main session (fable) · Lead: none, the CoS leads · Worker: none running'])
  const ds = [hd('sol', 'orchestrator', { startedAt: 0 }), hd('terra', 'workhorse', { parentId: 'sol', startedAt: 1 })]
  expect(hierarchyLines(ds, '')).toEqual(['CoS: main session · Lead: sol (orchestrator) · Worker: terra'])
  const two = hierarchyLines(ds, 'claude-opus-5-5', 40)
  expect(two).toEqual(['CoS: main session (claude-opus-5-5)', 'Lead: sol (orchestrator) · Worker: terra'])
  expect(hierarchyLines(ds, 'claude-opus-5-5', 20).every(l => l.length <= 20)).toBe(true)
})
