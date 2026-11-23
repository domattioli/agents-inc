import { expect, mock, test } from 'claude-code/testing'

import { ago, board, buildBoard, clearHold, ingestAgents, newMem, noteHold, noteStep, resetMem, runFrom } from './board-model'
import type { Listed, Mem } from './board-model'
import { keyAction, plainBoard, renderBoard } from './board-render'

type On = Parameters<Parameters<typeof test>[1]>[1]
type Dollar = Parameters<Parameters<typeof test>[1]>[0]

const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const MIN = 60_000
const agent = (id: string, type: string, description: string, status = 'running'): Listed => ({ id, type, description, status })
const show = (m: Mem, now: number, width = 80, selected?: string): string[] => {
  m.board = buildBoard(m, now)
  return plainBoard(renderBoard(m.board, { width, selected }))
}
const use = (m: Mem, now: number, key: string): void => {
  m.board = buildBoard(m, now)
  const r = keyAction(m.board, m.selected, key)
  m.selected = r.selected
  if (r.act === 'dismiss' && r.entry) m.dismissed[r.entry.key] = true
}

// --- golden scene 2: dead delegate (FR-018, FR-019, FR-023) -------------------------------------------------------

test('scene 2: a died luna shows in TROUBLE with its exact row, and dismiss keeps it gone', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs')], T0 - MIN)
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'failed')], T0)
  const now = T0 + 2 * MIN
  expect(show(m, now)).toEqual(['TROUBLE 1', '  ▲ luna    scan docs     died 2m ago', '', '↑↓ select'])
  // select the row: the footer lists the keys valid for it (transcript, dismiss; a dead agent has no stop)
  use(m, now, 'down')
  expect(show(m, now, 80, m.selected)).toEqual(['TROUBLE 1', '▸ ▲ luna    scan docs     died 2m ago', '', '↑↓ select  o open  d dismiss'])
  expect(keyAction(m.board, m.selected, 'o').act).toBe('open')
  expect(keyAction(m.board, m.selected, 's').act).toBeUndefined()
  use(m, now, 'd')
  expect(show(m, now)).toEqual(['nothing to show'])
  // a refresh of the same episode stays hidden
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'failed')], now + MIN)
  expect(show(m, now + MIN)).toEqual(['nothing to show'])
  // a later distinct episode surfaces again
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs')], now + 2 * MIN)
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'failed')], now + 3 * MIN)
  expect(show(m, now + 3 * MIN)[0]).toBe('TROUBLE 1')
})

test('scene 2: killed shows in TROUBLE until dismissed', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'killed')], T0)
  expect(show(m, T0 + 2 * MIN)[1]).toBe('  ▲ luna    scan docs     killed 2m ago')
  use(m, T0, 'down')
  use(m, T0, 'd')
  expect(show(m, T0 + 3 * MIN)).toEqual(['nothing to show'])
})

test('trouble from dispatch runs: timed out, failed check, lost, review owed', () => {
  const m = newMem()
  const run = (name: string, o: object, newest: number) => (m.runs[name] = runFrom(name, { runJson: JSON.stringify({ model: 'sonnet', ...o }), slotsJson: '{"TASK":"fix it"}' }, newest))
  run('20991112T120000Z-sonnet-aaa111', { outcome: 'red', reason: 'timeout' }, T0)
  run('20991112T120001Z-sonnet-bbb222', { outcome: 'red', reason: 'gate-failed' }, T0)
  run('20991112T120002Z-sonnet-ccc333', { outcome: 'unverified' }, T0)
  run('20991112T120003Z-sonnet-ddd444', {}, T0) // no outcome, nothing new for 7 minutes: lost
  run('20991112T120004Z-sonnet-eee555', { outcome: 'green' }, T0) // finished: hidden
  const out = show(m, T0 + 7 * MIN)
  expect(out[0]).toBe('TROUBLE 4')
  const notes = out.slice(1, 5).map(l => l.slice(l.lastIndexOf('fix it') + 6).trim()).sort()
  expect(notes).toEqual(['failed check 7m ago', 'lost, no update 7m', 'needs review', 'timed out 7m ago'])
  // a new event clears the live lost condition
  m.runs['20991112T120003Z-sonnet-ddd444'] = runFrom('20991112T120003Z-sonnet-ddd444', { runJson: '{"model":"sonnet"}', slotsJson: '{"TASK":"fix it"}' }, T0 + 7 * MIN)
  expect(show(m, T0 + 7 * MIN).join('\n')).toContain('WORKING 1')
})

// --- golden scene 3: operator hold (FR-014) -----------------------------------------------------------------------

test('scene 3: a held sonnet reaches NEEDS YOU with its question, and nothing else does', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'migrate db')], T0)
  expect(noteHold(m, { agent_id: 'a1', tool_name: 'AskUserQuestion', tool_input: { question: 'run migration?' } }, T0)).toBe(true)
  const out = show(m, T0 + 5000)
  expect(out).toEqual(['NEEDS YOU 1', '  1 sonnet waits: run migration?', '', '↑↓ select'])
  expect(m.board.working).toHaveLength(0)
  // a tool permission names what it would act on; a plan approval its first line
  noteHold(m, { agent_id: 'a1', tool_name: 'WebFetch', tool_input: { url: 'https://x.test/a' } }, T0)
  expect(show(m, T0)[1]).toBe('  1 sonnet waits: https://x.test/a')
  noteHold(m, { agent_id: 'a1', tool_name: 'ExitPlanMode', tool_input: { plan: '\nShip the parser\nstep two' } }, T0)
  expect(show(m, T0)[1]).toBe('  1 sonnet waits: Ship the parser')
})

test("scene 3: idle, background wait, and the operator's own main-session prompt create no Item", () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'sleeping', 'waiting'), agent('a2', 'agents-inc:terra', 'between turns', 'idle')], T0)
  expect(noteHold(m, { tool_name: 'ExitPlanMode', tool_input: { plan: 'p' } }, T0)).toBe(false) // main session: no agent_id
  m.board = buildBoard(m, T0 + 4 * MIN)
  expect(m.board.needs).toHaveLength(0)
  const out = plainBoard(renderBoard(m.board, { width: 80 }))
  expect(out[0]).toBe('WORKING 2')
  expect(out.join('\n')).toContain('waiting') // a waiting agent with no hold reads `waiting`, in WORKING
})

test('scene 3: a hold clears when the status changes or the agent stops; dismissal returns the row to WORKING', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'migrate db')], T0)
  noteHold(m, { agent_id: 'a1', tool_name: 'Bash', tool_input: { command: 'rm x' } }, T0)
  expect(buildBoard(m, T0).needs).toHaveLength(1)
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'migrate db', 'waiting')], T0 + MIN) // status changed: answered
  expect(buildBoard(m, T0 + MIN).needs).toHaveLength(0)
  noteHold(m, { agent_id: 'a1', tool_name: 'Bash', tool_input: { command: 'rm y' } }, T0 + 2 * MIN)
  expect(buildBoard(m, T0 + 2 * MIN).needs).toHaveLength(1)
  clearHold(m, 'a1') // SubagentStop
  expect(buildBoard(m, T0 + 2 * MIN).needs).toHaveLength(0)
  noteHold(m, { agent_id: 'a1', tool_name: 'Bash', tool_input: { command: 'rm z' } }, T0 + 3 * MIN)
  use(m, T0 + 3 * MIN, 'down')
  use(m, T0 + 3 * MIN, 'd')
  const b = buildBoard(m, T0 + 3 * MIN)
  expect(b.needs).toHaveLength(0)
  expect(b.working).toHaveLength(1)
})

// --- golden scene 4: quota pause (FR-014, FR-034, FR-035) ---------------------------------------------------------

test('scene 4: a quota-paused haiku run reaches NEEDS YOU with its reset time', () => {
  const m = newMem()
  const name = '20991112T120000Z-haiku-abc123'
  const reset = new Date(2099, 10, 12, 14, 20).getTime() // 14:20 local
  m.runs[name] = runFrom(name, { runJson: JSON.stringify({ model: 'haiku', outcome: 'red', reason: 'quota-paused', reset_at: reset }), slotsJson: '{"TASK":"scan docs"}' }, T0)
  expect(show(m, T0 + MIN)).toEqual(['NEEDS YOU 1', '  1 haiku paused: quota, resets 14:20', '', '↑↓ select'])
  // no reset time known: the line says only what is known
  m.runs[name] = runFrom(name, { runJson: '{"model":"haiku","outcome":"red","reason":"quota-paused"}' }, T0)
  expect(show(m, T0)[1]).toBe('  1 haiku paused: quota')
})

// --- focused cases ------------------------------------------------------------------------------------------------

test('working rows: active shows the step, quiet shows the note; same alias differs by task', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'write tests'), agent('a2', 'agents-inc:opus', 'review PR'), agent('a3', 'agents-inc:sonnet', 'fix parser')], T0)
  noteStep(m, 'a1', [{ role: 'assistant', content: [{ type: 'tool_use', name: 'Edit', input: { file_path: '/w/test_x.py' } }] }], T0 + 3 * MIN)
  noteStep(m, 'a2', [{ role: 'assistant', content: [{ type: 'tool_use', name: 'Read', input: { file_path: '/w/pr.md' } }] }], T0)
  noteStep(m, 'a3', undefined, T0 + 3 * MIN) // no readable step yet
  expect(show(m, T0 + 3 * MIN)).toEqual([
    'WORKING 3',
    '  ● sonnet  write tests   edit test_x.py',
    '  ◌ opus    review PR     quiet 3m',
    '  ◌ sonnet  fix parser    quiet 3m',
    '',
    '↑↓ select',
  ])
})

test('empty sections are hidden and sections keep their order with one blank line between', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'failed'), agent('a2', 'agents-inc:sonnet', 'write tests')], T0)
  noteHold(m, { agent_id: 'a2', tool_name: 'Bash', tool_input: { command: 'go?' } }, T0)
  ingestAgents(m, [agent('a1', 'agents-inc:luna', 'scan docs', 'failed'), agent('a2', 'agents-inc:sonnet', 'write tests'), agent('a3', 'agents-inc:terra', 'docs')], T0)
  const out = show(m, T0 + MIN)
  expect(out.filter(l => /^[A-Z ]+( \d+)?$/.test(l))).toEqual(['NEEDS YOU 1', 'TROUBLE 1', 'WORKING 1'])
  expect(out.indexOf('TROUBLE 1') - out.indexOf('NEEDS YOU 1')).toBe(3)
})

test('width: 30 columns and up truncate task and step and keep glyph and alias; below 30 only counts', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'refactor the entire authentication subsystem')], T0)
  noteStep(m, 'a1', [{ role: 'assistant', content: [{ type: 'tool_use', name: 'Edit', input: { file_path: '/w/a_very_long_file_name.py' } }] }], T0)
  const wide = show(m, T0, 30)
  expect(wide[1]).toBe('  ● sonnet  refactor the enti…')
  expect(wide[1]!.length).toBeLessThanOrEqual(30)
  expect(show(m, T0, 100)[1]).toBe('  ● sonnet  refactor the entire authentication subsystem edit a_very_long_file_name.py')
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'refactor the entire authentication subsystem'), agent('a2', 'agents-inc:luna', 'x', 'failed')], T0)
  expect(show(m, T0, 29)).toEqual(['TROUBLE 1', 'WORKING 1'])
  expect(show(m, T0, 12)).toEqual(['TROUBLE 1', 'WORKING 1'])
})

test('selection stays on the same target across a refresh', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'one'), agent('a2', 'agents-inc:luna', 'two')], T0)
  use(m, T0, 'down')
  use(m, T0, 'down')
  const picked = m.selected
  expect(m.board.working.find(e => e.key === picked)?.agentId).toBe('a2')
  // a new, more urgent row appears above it: the selection keeps its target
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'one'), agent('a2', 'agents-inc:luna', 'two'), agent('a3', 'agents-inc:haiku', 'dead', 'failed')], T0 + MIN)
  const lines = show(m, T0 + MIN, 80, m.selected)
  expect(lines.find(l => l.startsWith('▸'))).toContain('luna')
  // the selected row finishes: the selection is gone, not moved to another target
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'one'), agent('a2', 'agents-inc:luna', 'two', 'completed')], T0 + 2 * MIN)
  expect(show(m, T0 + 2 * MIN, 80, m.selected).some(l => l.startsWith('▸'))).toBe(false)
})

test('keys: o and s act on live rows only, Enter does nothing yet, and the footer matches', () => {
  const m = newMem()
  ingestAgents(m, [agent('a1', 'agents-inc:sonnet', 'one')], T0)
  use(m, T0, 'down')
  expect(show(m, T0, 80, m.selected).slice(-1)).toEqual(['↑↓ select  o open  s stop'])
  expect(keyAction(m.board, m.selected, 's').act).toBe('stop')
  expect(keyAction(m.board, m.selected, 'return').act).toBeUndefined()
  expect(keyAction(m.board, m.selected, 'd').act).toBeUndefined() // a working row cannot be dismissed
})

test('time words and the session reset', () => {
  expect([ago(5_000), ago(2 * MIN), ago(90 * MIN)]).toEqual(['5s', '2m', '1h'])
  board.opened = true
  resetMem(board)
  expect(board.opened).toBe(false)
})

// --- the pane inside the plugin -----------------------------------------------------------------------------------

async function startPlugin($: Dollar, on: On, world: { agents: any[]; runs?: boolean }, opens: any[]) {
  on('agent.register', (_$, e) => ({ value: { agent: `agents-inc:${e.name}` } }))
  on('tool.register', () => ({ value: {} }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 's1' }))
  on('ui.log', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'board' } }))
  on('agent.list', () => ({ value: world.agents }))
  on('session.messages', () => ({ value: [] as any }))
  on('fs.list', () => {
    throw new Error('ENOENT')
  })
  on('ui.invalidate', () => ({ value: undefined }))
  on('classic.PermissionRequest', () => ({}))
  on('classic.Notification', () => ({}))
  on('classic.SubagentStop', () => ({}))
  on('ui.open', (_$, e: any) => (opens.push(e), { value: { isPlaced: true } }))
  on('process.spawn', async function* () {
    yield { stream: 'stdout' as const, text: JSON.stringify({ offered: false, models: [] }) }
    return { value: { code: 0, signal: null } }
  })
  const clock = mock.clock(on, { now: T0 })
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  return clock
}

test('scene 4: Board starts closed, then opens without focus at the first delegate', async ($, on) => {
  const opens: any[] = []
  const world = { agents: [] as any[] }
  const clock = await startPlugin($, on, world, opens)
  await clock.advance(2100)
  expect(opens).toHaveLength(0) // nothing to show: stays closed
  world.agents = [agent('a1', 'agents-inc:haiku', 'scan docs')]
  await clock.advance(2100)
  expect(opens).toHaveLength(1)
  expect(opens[0].id).toBe('Board')
  expect(opens[0].title).toBe('Board')
  expect(opens[0].focus).toBeUndefined() // never takes focus
  expect('closeOnEscape' in opens[0]).toBe(false) // host accepts only true; left out

  await clock.advance(10_000)
  expect(opens).toHaveLength(1) // once per session
})

test('the pane draws NEEDS YOU from the host hold event, and the footer Client carries the keys and the click hint', async ($, on) => {
  const opens: any[] = []
  const world = { agents: [agent('a1', 'agents-inc:sonnet', 'migrate db')] }
  const clock = await startPlugin($, on, world, opens)
  await clock.advance(2100)
  await $.classic.PermissionRequest({ session_id: 's', transcript_path: '', cwd: '/work', agent_id: 'a1', agent_type: 'agents-inc:sonnet', tool_name: 'AskUserQuestion', tool_input: { question: 'run migration?' } } as any)
  await clock.advance(2100)
  const ui = await $.ui.mount({ plugin: 'agents-inc', component: 'Pane', requestId: 'Board', surface: 'terminal', props: { title: 'Board', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} } } as any)
  const texts = (await ui.findAll({ type: 'Text' })).map((t: any) => t.text)
  expect(texts.some((t: string) => t.includes('  1 sonnet waits: run migration?'))).toBe(true)
  expect(texts.some((t: string) => t.includes('NEEDS YOU 1'))).toBe(true)
  const footer: any = await ui.find({ type: 'Client' })
  expect(footer?.props?.props).toEqual({ keys: '↑↓ select', hint: 'click here to use keys' })
  await ui.unmount()
})
