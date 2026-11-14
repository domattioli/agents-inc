import { expect, test } from 'claude-code/testing'

import {
  agentMeta, agentRows, color, compose, describe, EMPTY, isFreeRun, KEEP_RUNS, newState, normalizeView, parse, resetState,
  runState, slotsFor, stampOf, startFreeRun, treeRuns,
} from './tree'
import type { TreeRow } from './tree'

const run = (id: string, state: string, meta = 'luna · dispatch'): TreeRow => ({ n: 0, depth: 1, kind: 'run', id, label: id, state, meta })

test('tree: agentMeta names the provider of an agents-inc type and keeps other types raw', () => {
  expect(agentMeta('agents-inc:luna')).toBe('luna · OpenAI')
  expect(agentMeta('agents-inc:codestral')).toBe('codestral')
  expect(agentMeta('Explore')).toBe('Explore')
})

test('tree: slotsFor writes a read-only slots file that may only write report.md', () => {
  const s = slotsFor('terra', 'count lines', '.scratch/pane/1') as any
  expect(s.MODEL).toBe('terra')
  expect(s.TASK).toBe('count lines')
  expect(s.FILES_IN_SCOPE).toBe('.scratch/pane/1/report.md')
  expect(typeof s.FILES_IN_SCOPE).toBe('string')
  expect(s.GATES[0].argv).toEqual(['test', '-s', 'report.md'])
})

test('tree: describe turns one events row into one session-style line', () => {
  expect(describe({ event: { type: 'item.started', item: { type: 'command_execution', command: "/bin/zsh -lc 'ls'" } } })).toBe('● Bash(ls)')
  expect(describe({ event: { type: 'item.completed', item: { type: 'command_execution', exit_code: 2 } } })).toBe('  ⎿  exit 2')
  expect(describe({ event: { type: 'run.end', outcome: 'green', rc: 0 } })).toBe('✓ Run end · green rc=0')
  expect(describe({ event: { type: 'nothing' } })).toBe('')
  expect(describe({})).toBe('')
})

test('tree: parse skips blank and broken lines; runState reads run.end', () => {
  const rows = parse('{"event":{"type":"x"}}\n\nnot json\n{"event":{"type":"run.end","outcome":"red"}}\n')
  expect(rows.length).toBe(2)
  expect(runState(rows)).toBe('red')
  expect(runState(rows.slice(0, 1))).toBe('running')
  expect(runState([])).toBe('starting')
})

test('tree: color and isFreeRun', () => {
  expect(color('running')).toBe('yellow')
  expect(color('done')).toBe('green')
  expect(color('failed')).toBe('red')
  expect(color('lost')).toBeUndefined()
  expect(isFreeRun({ meta: 'gemini · agent.sh' })).toBe(true)
  expect(isFreeRun({ meta: 'gemini · free dispatch' })).toBe(true)
  expect(isFreeRun({ meta: 'terra · dispatch' })).toBe(false)
  expect(isFreeRun({})).toBe(false)
})

test('tree: stampOf turns an ISO time into a run dir stamp', () => {
  expect(stampOf('2099-11-12T12:00:00.000Z')).toBe('20991112T120000Z')
  expect(stampOf('')).toBe('')
  expect(stampOf('nope')).toBe('')
})

test('tree: startFreeRun writes run.json kind free, output rows and a run.end row', async () => {
  const wrote: Record<string, string> = {}
  const f = await startFreeRun(async (p, t) => void (wrote[p] = t), 'gemini', 'task', '/w/task.txt')
  await f.out('one\ntwo\npart')
  await f.end(0)
  const rj = Object.keys(wrote).find(k => k.endsWith('/run.json'))!
  expect(JSON.parse(wrote[rj]!).kind).toBe('free')
  const ev = wrote[rj.replace('run.json', 'events.jsonl')]!
  expect(ev).toContain('two')
  expect(ev).toContain('part')
  expect(ev).toContain('"run.end"')
})

test('tree: agentRows nests children under the parent and lists one row per agent id', () => {
  const rows = agentRows([
    { id: 'a1', name: 'lead', type: 'Explore', description: 'top', status: 'running' },
    { id: 'a2', name: 'kid', type: 'Explore', description: 'child', status: 'running', parentId: 'a1' },
    { id: 'a1', name: 'lead', type: 'Explore', description: 'top', status: 'running' },
    { id: 'a3', name: 'orphan', type: 'Explore', description: 'o', status: 'running', parentId: 'gone' },
  ])
  expect(rows.map(r => [r.id, r.depth])).toEqual([['a1', 1], ['a2', 2], ['a3', 1]])
})

test('tree: treeRuns keeps running runs, drops finished runs from before the session, caps the finished', () => {
  const since = '20990101T000000Z'
  const fin = Array.from({ length: 12 }, (_, i) => run(`20990102T00${String(i).padStart(2, '0')}00Z-luna-f${i}`, 'done'))
  const old = run('20200101T000000Z-luna-old', 'done')
  const live = run('20260101T000000Z-luna-live', 'running')
  const r = treeRuns([...fin, old, live], new Map(), since, Date.now())
  expect(r.shown.length).toBe(KEEP_RUNS + 1)
  expect(r.shown.some(x => x.id.includes('old'))).toBe(false)
  expect(r.shown.some(x => x.id.includes('live'))).toBe(true)
  expect(r.summary).toBe(`1 running · 12 finished (showing ${KEEP_RUNS + 1})`)
  expect(treeRuns([], new Map(), since, 0).summary).toBe('')
})

test('tree: compose puts the job rows first and numbers every row', () => {
  const s = newState()
  s.base = [run('r1', 'done')]
  s.jobs.set('5', { stamp: '5', kind: 'free', model: 'gemini', task: ' do  it ', sig: 's', state: 'starting', note: '', dir: 'd', slots: '', before: new Set() })
  const rows = compose(s)
  expect(rows.map(r => [r.n, r.kind])).toEqual([[1, 'job'], [2, 'run']])
  expect(rows[0]!.label).toBe('do it')
  expect(rows[0]!.meta).toBe('gemini · agent.sh')
})

test('tree: resetState empties every map and set of the pane state and sets the cwd', () => {
  const s = newState()
  s.jobs.set('1', {} as any)
  s.stopAsked.add('a')
  s.resumed.add('r')
  s.at.set('r', 1)
  s.tails.set('r', ['x'])
  s.lastAgents.add('a')
  s.open.add('r')
  s.mapSubs.push({ id: 'a', type: 't', description: 'd', status: 'running' })
  s.base = [run('r', 'done')]
  s.summary = 'x'
  s.lastSig = 'sig'
  resetState(s, '/work')
  expect(s.jobs.size + s.stopAsked.size + s.resumed.size + s.at.size + s.tails.size + s.lastAgents.size + s.open.size).toBe(0)
  expect(s.mapSubs).toEqual([])
  expect(s.base).toEqual([])
  expect(s.summary).toBe('')
  expect(s.lastSig).toBe('')
  expect(s.cwd).toBe('/work')
})

test('tree: normalizeView fills fields an older code version did not write', () => {
  expect(normalizeView(undefined)).toEqual(EMPTY)
  expect(normalizeView({ note: 'n' } as any)).toMatchObject({ note: 'n', treeRows: [], controlsOpen: false, delegates: [] })
})
