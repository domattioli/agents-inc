import { expect, mock, test } from 'claude-code/testing'

import { closesOnSubmit, replyText } from './board-reply'
import { ingestTurn } from './board-items'

const T0 = Date.UTC(2099, 10, 12, 12, 0, 0)
const TURN = { answer: 'Parser fix is ready.\n[board:needs-you] Merge parser fix to main?', durationMs: 5, isAborted: false, turnId: 'turn-1', reason: 'answer' } as any
const MIX = { ...TURN, turnId: 'turn-2', answer: 'Pick one.\n[board:needs-you] Ship it? | ship now | wait' } as any
const REPLY = 'Re: Merge parser fix to main? - yes'

const mountBoard = ($: any) => $.ui.mount({ plugin: 'agents-inc', component: 'Pane', requestId: 'Board', surface: 'terminal', props: { title: 'Board', isFocused: false, bodyColumns: 70, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } } as any)
const mountTexts = async ($: any) => {
  const ui = await mountBoard($)
  const texts = [...new Set((await ui.findAll({ type: 'Text' })).map((t: any) => String(t.text)))]
  await ui.unmount()
  return texts
}
// A key as the operator presses it in the Board's footer Client (after a click): it posts to the hooks.
const key = async ($: any, k: string) => {
  const ui = await mountBoard($)
  await ui.key({ key: k })
  await ui.unmount()
}

function wire(on: any, st: { calls: number; sends: number; fills: string[]; ok: boolean }) {
  on('session.send', () => (st.calls++, st.sends++, undefined as any))
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer }))
  on('prompt.fill', (_$: any, e: any) => (st.fills.push(e.text), { isFilled: st.ok }))
  on('prompt.submit', (_$: any, e: any) => e)
  on('prompt.change', (_$: any, e: any) => e)
  mock.clock(on, { now: T0 })
}

test('scene 1: Enter opens the region, contents shown, x closes, reply fills the draft, matching composer submit closes the Item', async ($, on) => {
  const st = { calls: 0, sends: 0, fills: [] as string[], ok: true }
  wire(on, st)
  await $.turn.complete(TURN)
  await key($, 'down')
  await key($, 'return')
  let t = await mountTexts($)
  expect(t).toContain('▸ 1 Merge parser fix to main?')
  expect(t).toContain('REPLY')
  expect(t.some(x => x.includes('Parser fix is ready.'))).toBe(true) // full source chat turn as context
  expect(t.some(x => x.includes('source [board:needs-you] Merge parser fix to main?'))).toBe(true)
  expect(t).toContain('keys 1 yes   2 no   3 hold   x close')
  expect(t).toContain('sent: nothing yet')
  await key($, 'x')
  t = await mountTexts($)
  expect(t).not.toContain('REPLY')
  // reopen and fill: the draft is filled, the Item stays
  await key($, 'return')
  await key($, '1')
  expect(st.fills).toEqual([REPLY])
  expect((await mountTexts($)).some(x => x.includes('NEEDS YOU 1'))).toBe(true)
  // a plugin-origin submit with the same text (the fill itself) does not close it
  await $.prompt.submit({ text: REPLY, origin: { kind: 'plugin' } } as any)
  expect((await mountTexts($)).some(x => x.includes('NEEDS YOU 1'))).toBe(true)
  // the operator's own Enter with that text closes it and the sent line shows
  await $.prompt.submit({ text: REPLY, origin: { kind: 'composer' } } as any)
  t = await mountTexts($)
  expect(t).toEqual(['nothing to show'])
  expect(st.calls).toBe(0)
  expect(st.sends).toBe(0)
})

test('scene 1: marker options replace the default keys', async ($, on) => {
  const st = { calls: 0, sends: 0, fills: [] as string[], ok: true }
  wire(on, st)
  await $.turn.complete(MIX)
  await key($, 'down')
  await key($, 'return')
  const t = await mountTexts($)
  expect(t).toContain('keys 1 ship now   2 wait   x close')
  await key($, '3') // no third option: nothing fills
  expect(st.fills).toEqual([])
  await key($, '2')
  expect(st.fills).toEqual(['Re: Ship it? - wait'])
  expect(st.sends).toBe(0)
})

test('failed send: an unsent draft keeps the Item open', async ($, on) => {
  const st = { calls: 0, sends: 0, fills: [] as string[], ok: true }
  wire(on, st)
  await $.turn.complete(TURN)
  await key($, 'down'); await key($, 'return'); await key($, '1')
  expect((await mountTexts($)).some(x => x.includes('NEEDS YOU 1'))).toBe(true)
})

test('failed send: a cleared or edited draft then a different submit keeps the Item open', async ($, on) => {
  const st = { calls: 0, sends: 0, fills: [] as string[], ok: true }
  wire(on, st)
  await $.turn.complete(TURN)
  await key($, 'down'); await key($, 'return'); await key($, '1')
  await $.prompt.change({ text: '', origin: { kind: 'composer' } } as any)
  await $.prompt.submit({ text: 'something else', origin: { kind: 'composer' } } as any)
  expect((await mountTexts($)).some(x => x.includes('NEEDS YOU 1'))).toBe(true)
})

test('failed send: a refused fill keeps the Item open and a later submit of that text closes nothing', async ($, on) => {
  const st = { calls: 0, sends: 0, fills: [] as string[], ok: false }
  wire(on, st)
  await $.turn.complete(TURN)
  await key($, 'down'); await key($, 'return'); await key($, '1')
  await $.prompt.submit({ text: REPLY, origin: { kind: 'composer' } } as any)
  expect((await mountTexts($)).some(x => x.includes('NEEDS YOU 1'))).toBe(true)
})

test('reply logic: closesOnSubmit needs pending text, composer origin and equal text', () => {
  expect(closesOnSubmit(undefined, { text: 'a', origin: { kind: 'composer' } })).toBe(false)
  expect(closesOnSubmit({ itemId: 'i1' }, { text: 'a', origin: { kind: 'composer' } })).toBe(false)
  expect(closesOnSubmit({ itemId: 'i1', pending: 'a' }, { text: 'a', origin: { kind: 'plugin' } })).toBe(false)
  expect(closesOnSubmit({ itemId: 'i1', pending: 'a' }, { text: 'b', origin: { kind: 'composer' } })).toBe(false)
  expect(closesOnSubmit({ itemId: 'i1', pending: 'a' }, { text: 'a', origin: { kind: 'composer' } })).toBe(true)
})

test('reply logic: replyText maps digits to options only', () => {
  const s = { items: [] as any[], seen: {}, seq: 0 }
  ingestTurn(s, 's', { turnId: 't', answer: '[board:needs-you] Q?' }, T0)
  expect(replyText(s.items[0], '2')).toBe('Re: Q? - no')
  expect(replyText(s.items[0], '4')).toBeUndefined()
  expect(replyText(s.items[0], 'x')).toBeUndefined()
})
