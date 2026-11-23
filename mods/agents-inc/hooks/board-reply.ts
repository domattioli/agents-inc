// Spec 050 T026, T027: the reply region and the reply flow. Pure, no `$`, no I/O, zero model calls.
// The Board never sends a reply itself: it fills the chat box and the operator's own Enter sends it. The Item closes
// only on a composer submission whose text equals the text filled for it.
import { ago, clip } from './board-model'
import type { Item } from './board-items'
import { quickKeys, quickLine } from './board-items'
import type { Line } from './board-render'

// `pending` is the text filled for the Item that still waits for the operator's Enter.
export type Reply = { itemId: string; pending?: string }

export const CONTEXT_LINES = 6
export const SENT_KEEP = 3

// The text a quick key fills: the nth option (1 based), tied to its Item by the title. Undefined for a key with no option.
export function replyText(item: Item, key: string): string | undefined {
  const opt = quickKeys(item)[Number(key) - 1]
  return /^[1-9]$/.test(key) && opt ? `Re: ${item.title} - ${opt}` : undefined
}

// A fill counts only when the host kept it in the box. A refusal (isFilled false) leaves the reply unset.
export function afterFill(r: Reply, text: string, isFilled: unknown): Reply {
  return isFilled === true ? { ...r, pending: text } : { itemId: r.itemId }
}

// An Item closes only for the operator's own submission of exactly the filled text. A fill (origin plugin), another
// text and a changed draft never close it; with no `prompt.cancel` event, a draft that is never submitted just stays.
export function closesOnSubmit(r: Reply | undefined, e: { text?: unknown; origin?: { kind?: unknown } }): boolean {
  return Boolean(r && r.pending !== undefined && e?.origin?.kind === 'composer' && String(e.text ?? '') === r.pending)
}

export function regionLines(item: Item, now: number, sent: string[], width: number): Line[] {
  const dim = (t: string): Line => [{ t: clip(t, width), dim: true }]
  const ctx = String(item.context || item.source).split('\n').map(l => l.trimEnd()).filter(Boolean)
  const shown = ctx.slice(-CONTEXT_LINES)
  const lines: Line[] = [[], dim('REPLY'), [{ t: clip(item.title, width), color: 'yellow' }]]
  lines.push(dim('context'))
  if (shown.length < ctx.length) lines.push(dim('  ...'))
  for (const l of shown) lines.push([{ t: clip('  ' + l, width) }])
  lines.push(dim(`source ${item.source} · ${ago(now - item.at)}`))
  lines.push([{ t: clip(`keys ${quickLine(item)}   x close`, width) }])
  const last = sent.slice(-SENT_KEEP)
  lines.push(dim(last.length ? 'sent' : 'sent: nothing yet'))
  for (const t of last) lines.push([{ t: clip('  ' + t, width) }])
  return lines
}
