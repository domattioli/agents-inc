import { expect, test } from 'claude-code/testing'

import { mergeAgents, poll } from './poll'
import { EMPTY, newState } from './tree'

const NOW = Date.UTC(2099, 10, 12, 13, 0, 0)
const SINCE = '2099-11-12T12:00:00.000Z'
const A = '20991112T120500Z-luna-aaaaaa'
const B = '20991112T120600Z-gemini-bbbbbb'
const FREE_JSON = '{"model":"gemini","kind":"free","via":"agent.sh","outcome":"red"}'
const DONE = '{"event":{"type":"run.end","outcome":"green","rc":0}}\n'

// A hand-made `$` for calling poll directly: agents, run dir names and file contents by path; every read is logged.
function fake(agents: any[], dirs: string[], files: Record<string, string>) {
  const reads: string[] = []
  const lists: string[] = []
  const $ = {
    agent: { list: async () => agents },
    session: { model: async () => 'opus' },
    fs: {
      list: async (path: string) => {
        lists.push(path)
        if (path.endsWith('agents-inc-runs')) return dirs.map(name => ({ name, kind: 'dir' }))
        return Object.keys(files).filter(f => f.startsWith(path + '/')).map(f => ({ name: f.slice(path.length + 1), kind: 'file', mtimeMs: NOW - 1000, size: 10 }))
      },
      read: async (path: string) => {
        reads.push(path)
        if (!(path in files)) throw new Error('ENOENT')
        return files[path]
      },
      exists: async (path: string) => path in files,
    },
  }
  return { $: $ as any, reads, lists }
}
const root = (n: string) => `.scratch/agents-inc-runs/${n}`
const view = { ...EMPTY, sessionStart: SINCE }

test('poll: an agent listed twice is one row; a run dir listed twice is one row', async () => {
  const f = fake(
    [{ id: 'a1', type: 'Explore', description: 'x', status: 'running' }, { id: 'a1', type: 'Explore', description: 'x', status: 'running' }],
    [A, A],
    { [root(A) + '/run.json']: '{"model":"luna","kind":"claude","outcome":"green"}', [root(A) + '/events.jsonl']: DONE },
  )
  const r = await poll(f.$, newState(), view, NOW)
  expect(r.rows.filter(x => x.kind === 'agent').length).toBe(1)
  expect(r.rows.filter(x => x.kind === 'run').length).toBe(1)
  expect(r.agentIds).toEqual(['a1', 'a1'])
  expect(r.delegates.filter(d => d.source === 'dispatch').length).toBe(1)
})

test('poll: the result carries delegates, finals, note, model, rows and summary', async () => {
  const f = fake([], [A], { [root(A) + '/run.json']: '{"model":"luna","kind":"claude","outcome":"green"}', [root(A) + '/events.jsonl']: DONE })
  const st = newState()
  const r = await poll(f.$, st, view, NOW)
  expect(r.model).toBe('opus')
  expect(r.mapNote).toBe('')
  expect(Object.keys(r.finalRuns)).toEqual([A])
  expect(r.summary).toBe(st.summary)
  expect(r.rows.map(x => x.id)).toEqual([A])
  expect(Object.keys(r.runLines)).toEqual([])
})

test('poll: a cached final run is not read again on the next poll', async () => {
  const f = fake([], [A], { [root(A) + '/run.json']: '{"model":"luna","kind":"claude","outcome":"green"}', [root(A) + '/events.jsonl']: DONE })
  const st = newState()
  const first = await poll(f.$, st, view, NOW)
  f.reads.length = 0
  await poll(f.$, st, { ...view, finalRuns: first.finalRuns }, NOW + 1000)
  expect(f.reads).toEqual([])
})

test('poll: a free run tail is read once, and again only while the run is failed', async () => {
  const files = {
    [root(B) + '/run.json']: FREE_JSON,
    [root(B) + '/events.jsonl']: DONE,
    [root(B) + '/stderr.txt']: 'boom\n',
  }
  const f = fake([], [B], files)
  const st = newState()
  st.open.add(B)
  const r1 = await poll(f.$, st, view, NOW)
  expect(r1.runLines[B]!.some(l => l.includes('boom'))).toBe(true)
  const tails = () => f.reads.filter(p => p.endsWith('stdout.md') || p.endsWith('stderr.txt')).length
  const after1 = tails()
  expect(after1).toBeGreaterThan(0)
  // failed: the tail is read again on every poll
  await poll(f.$, st, view, NOW + 1000)
  expect(tails()).toBeGreaterThan(after1)
  // a green free run keeps its tail: read once
  const g = fake([], [B], { ...files, [root(B) + '/run.json']: '{"model":"gemini","kind":"free","via":"agent.sh","outcome":"green"}' })
  const sg = newState()
  sg.open.add(B)
  await poll(g.$, sg, view, NOW)
  const once = g.reads.filter(p => p.endsWith('stdout.md') || p.endsWith('stderr.txt')).length
  await poll(g.$, sg, view, NOW + 1000)
  expect(g.reads.filter(p => p.endsWith('stdout.md') || p.endsWith('stderr.txt')).length).toBe(once)
})

test('poll: a dispatch job row ends once a run dir with its slots path appears', async () => {
  const f = fake([], [A], { [root(A) + '/run.json']: '{"model":"luna","kind":"claude","slots":"/w/.scratch/x/7/slots.json"}', [root(A) + '/events.jsonl']: '' })
  const st = newState()
  st.jobs.set('7', { stamp: '7', kind: 'dispatch', model: 'luna', task: 't', sig: 's', state: 'starting', note: '', dir: 'd', slots: '', before: new Set() })
  await poll(f.$, st, view, NOW)
  expect(st.jobs.size).toBe(0)
})

test('poll: a native job row ends once a new agent appears', async () => {
  const f = fake([{ id: 'n1', type: 'agents-inc:luna', description: 'd', status: 'running' }], [], {})
  const st = newState()
  st.jobs.set('8', { stamp: '8', kind: 'native', model: 'luna', task: 't', sig: 's', state: 'starting', note: '', dir: '', slots: '', before: new Set() })
  await poll(f.$, st, view, NOW)
  expect(st.jobs.size).toBe(0)
})

test('mergeAgents: one entry per id, in first-seen order, a vanished agent marked finished', () => {
  const a = mergeAgents([], [{ id: '1', type: 'Plan', description: 'p', status: 'running' }, { id: '2', type: 'Explore', description: 'e', status: 'running' }])
  const b = mergeAgents(a, [{ id: '2', type: 'Explore', description: 'e', status: 'running' }, { id: '3', type: 'Plan', description: 'q', status: 'running' }])
  expect(b.map(x => [x.id, x.status])).toEqual([['1', 'finished'], ['2', 'running'], ['3', 'running']])
})

test('poll: a refused guest agent leaves a red run.json and its row reads failed (#177)', async () => {
  const R = '20991112T120700Z-ministral-cccccc'
  const reason = 'needs-authorization: mistral is not authorized for /ws. Nothing was sent. Authorize: agents-inc native allow mistral --workspace /ws'
  const f = fake([], [R], { [root(R) + '/run.json']: JSON.stringify({ run_id: R, model: 'ministral', kind: 'native', cwd: '/ws', outcome: 'red', reason }) })
  const r = await poll(f.$, newState(), view, NOW)
  expect(r.rows.find(x => x.id === R)?.state).toBe('failed')
  expect(r.delegates.find(d => d.id === R)?.state).toBe('failed')
})
