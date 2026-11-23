import { expect, mock, test } from 'claude-code/testing'

import { board, buildBoard, newMem, resetMem } from './board-model'
import { extractMainTurnAnswer, ingestTurn, newItems, parseMarkers, quickLine, FYI_KEEP } from './board-items'
import { keyAction, plainBoard, renderBoard } from './board-render'

const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const main = (turnId: string, answer: string) => ({ turnId, answer })
const shown = (m: ReturnType<typeof newMem>, selected?: string) => {
  m.board = buildBoard(m, T0 + 1000)
  return plainBoard(renderBoard(m.board, { width: 80, selected }))
}

// --- parser (T023) -----------------------------------------------------------------------------------------------

test('parser: valid lines, title is the whole text before the first pipe, full line kept as source', () => {
  const got = parseMarkers('Prose first.\n[board:needs-you] Merge parser fix to main?\n  [board:fyi] Tests green  \nmore prose')
  expect(got).toEqual([
    { section: 'needs-you', title: 'Merge parser fix to main?', options: [], source: '[board:needs-you] Merge parser fix to main?' },
    { section: 'fyi', title: 'Tests green', options: [], source: '[board:fyi] Tests green' },
  ])
})

test('parser: options split on pipes, empty ones dropped', () => {
  const [m] = parseMarkers('[board:needs-you] Ship it? | ship now | wait a day | | cancel')
  expect(m!.title).toBe('Ship it?')
  expect(m!.options).toEqual(['ship now', 'wait a day', 'cancel'])
})

test('parser: trouble, working and unknown sections are ignored silently', () => {
  expect(parseMarkers('[board:trouble] x\n[board:working] y\n[board:bogus] z\n[board:Needs-You] w')).toEqual([])
})

test('parser: malformed lines make nothing', () => {
  expect(parseMarkers('[board:needs-you]\n[board:needs-you]   | only option\nboard:needs-you] a\n[board needs-you] b\nsee [board:fyi] mid-line')).toEqual([])
  expect(parseMarkers('')).toEqual([])
})

test('parser: done parses with its title', () => {
  expect(parseMarkers('[board:done] Merge parser fix to main?')[0]).toMatchObject({ section: 'done', title: 'Merge parser fix to main?' })
})

test('extractMainTurnAnswer: main successful turns only', () => {
  expect(extractMainTurnAnswer({ turnId: 't1', answer: 'hi', reason: 'answer' })).toEqual({ turnId: 't1', answer: 'hi' })
  expect(extractMainTurnAnswer({ turnId: 't1', answer: 'hi', agentId: 'a1' })).toBeUndefined()
  expect(extractMainTurnAnswer({ turnId: 't1', answer: 'hi', isAborted: true, reason: 'aborted' })).toBeUndefined()
  expect(extractMainTurnAnswer({ turnId: 't1', answer: 'hi', reason: 'error' })).toBeUndefined()
  expect(extractMainTurnAnswer({ answer: 'hi' })).toBeUndefined()
  expect(extractMainTurnAnswer(undefined)).toBeUndefined()
})

// --- Items (T024, T025, T030) ------------------------------------------------------------------------------------

test('items: repeat delivery of one turn makes no duplicate', () => {
  const s = newItems()
  const t = main('t1', '[board:needs-you] Merge?\n[board:fyi] note')
  ingestTurn(s, 's1', t, T0)
  ingestTurn(s, 's1', t, T0 + 5)
  expect(s.items.map(i => i.title)).toEqual(['Merge?', 'note'])
  // same line in a new turn is a new Item
  ingestTurn(s, 's1', main('t2', '[board:fyi] note'), T0 + 9)
  expect(s.items).toHaveLength(3)
})

test('items: FYI keeps the newest three, older age out, NEEDS YOU untouched', () => {
  const s = newItems()
  ingestTurn(s, 's', main('t0', '[board:needs-you] keep me'), T0)
  for (let k = 1; k <= 5; k++) ingestTurn(s, 's', main(`t${k}`, `[board:fyi] f${k}`), T0 + k)
  expect(FYI_KEEP).toBe(3)
  expect(s.items.filter(i => i.kind === 'fyi').map(i => i.title)).toEqual(['f3', 'f4', 'f5'])
  expect(s.items.filter(i => i.kind === 'needs')).toHaveLength(1)
})

test('items: NEEDS YOU stays until dismissed or closed by done; an inexact title closes nothing', () => {
  const m = newMem()
  ingestTurn(m.items, 's', main('t1', '[board:needs-you] Merge?\n[board:needs-you] Deploy?'), T0)
  expect(shown(m)[0]).toBe('NEEDS YOU 2')
  ingestTurn(m.items, 's', main('t2', '[board:done] merge?'), T0 + 1) // inexact
  expect(shown(m)[0]).toBe('NEEDS YOU 2')
  ingestTurn(m.items, 's', main('t3', '[board:done] Merge?'), T0 + 2)
  expect(shown(m).slice(0, 2)).toEqual(['NEEDS YOU 1', '  1 Deploy?'])
  m.board = buildBoard(m, T0 + 3)
  m.selected = keyAction(m.board, undefined, 'down').selected
  const r = keyAction(m.board, m.selected, 'd')
  m.dismissed[r.entry!.key] = true
  expect(shown(m)).toEqual(['nothing to show'])
})

test('items: a marker on a non-main or interrupted turn is ignored', () => {
  const s = newItems()
  for (const ev of [
    { turnId: 't1', answer: '[board:needs-you] from a delegate?', agentId: 'a1' },
    { turnId: 't2', answer: '[board:needs-you] interrupted?', isAborted: true, reason: 'aborted' },
    { turnId: 't3', answer: '[board:needs-you] failed?', reason: 'error' },
  ]) {
    const t = extractMainTurnAnswer(ev)
    if (t) ingestTurn(s, 's', t, T0)
  }
  expect(s.items).toEqual([])
})

test('items: quick keys default, replaced by marker options', () => {
  const s = newItems()
  ingestTurn(s, 's', main('t1', '[board:needs-you] A?\n[board:needs-you] B? | ship | wait'), T0)
  expect(quickLine(s.items[0]!)).toBe('1 yes   2 no   3 hold')
  expect(quickLine(s.items[1]!)).toBe('1 ship   2 wait')
})

// --- golden scene 1, up to the Board line (T029) -----------------------------------------------------------------
// DEFERRED: the sub-pane parts (Enter opens, contents, Escape, test reply makes the Item leave, option keys inside the
// sub-pane) wait on T021 and T026/T027. Covered here: a main-loop turn completes with the marker, the Board shows the
// exact selected line, and no model call happens.

test('scene 1: a completed turn with a marker puts the exact line on the Board, with no model call', async ($, on) => {
  let modelCalls = 0
  on('session.send', () => (modelCalls++, undefined as any))
  on('turn.complete', (_$, e: any) => ({ text: e.answer }))
  mock.clock(on, { now: T0 })
  const done = { answer: 'Parser fix is ready.\n[board:needs-you] Merge parser fix to main?', durationMs: 5, isAborted: false, turnId: 'turn-1', reason: 'answer' } as any
  await $.turn.complete(done)
  await $.turn.complete(done) // repeat delivery: still one Item
  await $.turn.complete({ ...done, turnId: 'turn-2', agentId: 'a1' }) // a delegate turn: ignored
  const ui = await $.ui.mount({ plugin: 'agents-inc', component: 'Pane', requestId: 'Board', surface: 'terminal', props: { title: 'Board', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} } } as any)
  const texts = (await ui.findAll({ type: 'Text' })).map((t: any) => t.text)
  expect([...new Set(texts.filter((t: string) => t.includes('Merge parser fix to main?')))]).toEqual(['  1 Merge parser fix to main?'])
  expect(texts.some((t: string) => t.includes('NEEDS YOU 2'))).toBe(false)
  expect(texts.some((t: string) => t.includes('NEEDS YOU 1'))).toBe(true)
  await ui.unmount()
  expect(modelCalls).toBe(0)
})

// The selected line itself comes from the pure renderer: same Board, selection on the Item.
test('scene 1: the selected Item line is exactly `▸ 1 Merge parser fix to main?`', () => {
  const m = newMem()
  ingestTurn(m.items, 's', { turnId: 'turn-1', answer: 'Ready.\n[board:needs-you] Merge parser fix to main?' }, T0)
  m.board = buildBoard(m, T0)
  m.selected = keyAction(m.board, m.selected, 'down').selected
  expect(plainBoard(renderBoard(m.board, { width: 80, selected: m.selected }))[1]).toBe('▸ 1 Merge parser fix to main?')
})
