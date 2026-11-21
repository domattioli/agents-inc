// Spec 050 Phase 1: the deterministic Board renderer and the key rules. Pure: the same Board, width and selection give
// the same lines. No map, stations, roles line, feed, tree, form, done list, tokens or animation (FR-036, FR-037).
import { clip, selectable } from './board-model'
import type { Action, Board, Entry } from './board-model'

export type Span = { t: string; dim?: boolean; color?: 'yellow' | 'red' }
export type Line = Span[]
export type Rendered = {
  lines: Line[]
  // One footer line: the keys valid for the selection. Empty below NARROW columns, where only counts show.
  footer: string
  // The one-line dim hint shown until a key has reached the Board's Client (host: keys need a click first).
  hint: string
  narrow: boolean
}

export const NARROW = 30
export const HINT = 'click here to use keys'
const ALIAS_W = 8
const TASK_W = 13

export const plain = (line: Line): string => line.map(s => s.t).join('')
export const plainBoard = (r: Rendered): string[] => [...r.lines.map(plain), ...(r.footer ? ['', r.footer] : [])]

const LABEL = { needs: 'NEEDS YOU', fyi: 'FYI', trouble: 'TROUBLE', working: 'WORKING' } as const
const COLOR = { needs: 'yellow', trouble: 'red' } as const

export function footerKeys(entry: Entry | undefined): string {
  const names: Record<Action, string> = { open: 'o open', stop: 's stop', dismiss: 'd dismiss' }
  return ['↑↓ select', ...(entry?.actions ?? []).map(a => names[a])].join('  ')
}

export function renderBoard(b: Board, o: { width: number; selected?: string }): Rendered {
  const width = Math.max(0, Math.floor(o.width))
  const sections = (['needs', 'fyi', 'trouble', 'working'] as const).filter(s => b[s].length)
  const narrow = width < NARROW
  if (!sections.length) return { lines: [[{ t: 'nothing to show', dim: true }]], footer: '', hint: HINT, narrow }
  const label = (s: (typeof sections)[number]): string => (s === 'fyi' ? LABEL.fyi : `${LABEL[s]} ${b[s].length}`)
  if (narrow) {
    // counts only: one line per section, FYI included with its count
    const lines = sections.map(s => [{ t: clip(s === 'fyi' ? `${LABEL.fyi} ${b.fyi.length}` : label(s), width), dim: s === 'fyi' || s === 'working' || undefined, color: s in COLOR ? COLOR[s as 'needs' | 'trouble'] : undefined } as Span])
    return { lines, footer: '', hint: HINT, narrow }
  }
  const lines: Line[] = []
  sections.forEach((s, k) => {
    if (k) lines.push([])
    lines.push([{ t: label(s), dim: true }])
    b[s].forEach((e, i) => lines.push(row(s, e, i + 1, width, e.key === o.selected)))
  })
  const sel = selectable(b).find(e => e.key === o.selected)
  return { lines, footer: clip(footerKeys(sel), width), hint: HINT, narrow }
}

// One row, one line. Glyph and alias stay; task and step truncate to the width (FR-048).
function row(s: Entry['section'], e: Entry, n: number, width: number, selected: boolean): Line {
  const color = s in COLOR ? COLOR[s as 'needs' | 'trouble'] : undefined
  const lead = selected ? '▸ ' : '  '
  if (s === 'needs') return [{ t: clip(`${lead}${n} ${e.note}`, width), color }]
  if (s === 'fyi') return [{ t: clip(`${lead}· ${e.note}`, width) }]
  const head = `${lead}${e.glyph} ${e.alias.padEnd(ALIAS_W)}`
  const room = Math.max(0, width - head.length)
  const task = `${e.task.padEnd(TASK_W)} `
  const tail = clip(task + e.note, room)
  const taskPart = tail.slice(0, Math.min(tail.length, task.length))
  const notePart = tail.slice(taskPart.length)
  return [{ t: head + taskPart, color }, { t: notePart, dim: s === 'working' ? true : undefined, color }]
}

// --- keys ---------------------------------------------------------------------------------------------------------

export type KeyResult = { selected?: string; act?: Action; entry?: Entry }

// Up and Down move the selection by identity; o, s and d act on the selected row when its footer lists them.
// Enter is for the reply area, which arrives in Phase 2.
export function keyAction(b: Board, selected: string | undefined, key: string): KeyResult {
  const all = selectable(b)
  const at = all.findIndex(e => e.key === selected)
  const cur = at < 0 ? undefined : all[at]
  if (key === 'up' || key === 'k') return { selected: all.length ? all[at <= 0 ? all.length - 1 : at - 1]!.key : undefined }
  if (key === 'down' || key === 'j') return { selected: all.length ? all[at < 0 || at >= all.length - 1 ? 0 : at + 1]!.key : undefined }
  const act = ({ o: 'open', s: 'stop', d: 'dismiss' } as Record<string, Action>)[key]
  if (act && cur && cur.actions.includes(act)) {
    if (act !== 'dismiss') return { selected: cur.key, act, entry: cur }
    // after a dismissal the selection moves to the neighbour that stays, by identity
    const rest = all.filter(e => e.key !== cur.key)
    const next = rest[Math.min(at, rest.length - 1)]
    return { selected: next?.key, act, entry: cur }
  }
  return { selected }
}
