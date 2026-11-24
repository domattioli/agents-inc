// Spec 050 Phase 2: CoS markers and the Item store. Pure functions, no `$`, no I/O, zero model calls.
// Marker line: `[board:<section>] <text> | <option> | <option>`. Only needs-you, fyi and done are read from chat.
import type { Entry } from './board-model'

export type Marker = { section: 'needs-you' | 'fyi' | 'done'; title: string; options: string[]; source: string }
export type Item = {
  id: string
  kind: 'needs' | 'fyi'
  title: string
  options: string[]
  // The full marker line as written, kept for replay and detail.
  source: string
  // The full chat turn the marker came from, shown as context in the reply region.
  context: string
  sessionId: string
  turnId: string
  at: number
}
export type ItemStore = { items: Item[]; seen: Record<string, true>; seq: number }
export type MainTurn = { turnId: string; answer: string }

export const FYI_KEEP = 3
export const DEFAULT_KEYS: readonly string[] = ['yes', 'no', 'hold']
const ACCEPT = new Set(['needs-you', 'fyi', 'done'])
const LINE = /^\[board:([a-z-]+)\][ \t]*(.*)$/

export const newItems = (): ItemStore => ({ items: [], seen: {}, seq: 0 })

// The one place that knows the shape of `turn.complete`. Returns the answer of a successful main-loop turn, else
// undefined (a subagent turn has `agentId`; an interrupted, refused or failed turn has `reason` other than 'answer').
// The live shape is still being probed: only this function changes.
export function extractMainTurnAnswer(event: unknown): MainTurn | undefined {
  const e = (event && typeof event === 'object' ? event : {}) as Record<string, unknown>
  if (e.agentId !== undefined && e.agentId !== null && e.agentId !== '') return undefined
  if (e.isAborted === true) return undefined
  if (e.reason !== undefined && e.reason !== 'answer') return undefined
  if (typeof e.answer !== 'string' || !e.answer || typeof e.turnId !== 'string' || !e.turnId) return undefined
  return { turnId: e.turnId, answer: e.answer }
}

// Complete marker lines only. Unknown or mechanical sections (trouble, working) and lines with no title are skipped.
export function parseMarkers(answer: string): Marker[] {
  const out: Marker[] = []
  for (const raw of String(answer ?? '').split('\n')) {
    const source = raw.trim()
    const m = LINE.exec(source)
    if (!m || !ACCEPT.has(m[1]!)) continue
    const parts = m[2]!.split('|').map(s => s.trim())
    const title = parts[0]!
    if (!title) continue
    out.push({ section: m[1] as Marker['section'], title, options: parts.slice(1).filter(Boolean), source })
  }
  return out
}

// Apply one main-loop turn. A repeat of the same session, turn id and source line does nothing.
export function ingestTurn(s: ItemStore, session: string, turn: MainTurn, now: number): void {
  for (const mk of parseMarkers(turn.answer)) {
    const dk = `${session}|${turn.turnId}|${mk.source}`
    if (s.seen[dk]) continue
    s.seen[dk] = true
    if (mk.section === 'done') {
      s.items = s.items.filter(i => !(i.kind === 'needs' && i.title === mk.title))
      continue
    }
    const kind = mk.section === 'fyi' ? 'fyi' : 'needs'
    s.items.push({ id: `i${++s.seq}`, kind, title: mk.title, options: mk.options, source: mk.source, context: turn.answer, sessionId: session, turnId: turn.turnId, at: now })
    if (kind === 'fyi') {
      const fyi = s.items.filter(i => i.kind === 'fyi')
      const drop = new Set(fyi.slice(0, Math.max(0, fyi.length - FYI_KEEP)).map(i => i.id))
      if (drop.size) s.items = s.items.filter(i => !drop.has(i.id))
    }
  }
}

// An FYI the Board itself raises (a Memo or an FYI to another Team's CoS that did not go as asked). `detail` keeps the text.
export function addFyi(s: ItemStore, title: string, detail: string, now: number): void {
  s.items.push({ id: `i${++s.seq}`, kind: 'fyi', title, options: [], source: detail, context: detail, sessionId: '', turnId: '', at: now })
  const fyi = s.items.filter(i => i.kind === 'fyi')
  const drop = new Set(fyi.slice(0, Math.max(0, fyi.length - FYI_KEEP)).map(i => i.id))
  if (drop.size) s.items = s.items.filter(i => !drop.has(i.id))
}

export const itemKey = (i: Item): string => `i:${i.id}`

// Board rows for the Items: NEEDS YOU oldest first, FYI newest first. Dismissed Items are hidden by key.
export function itemEntries(s: ItemStore, dismissed: Record<string, true>): { needs: Entry[]; fyi: Entry[] } {
  const row = (i: Item): Entry => ({ key: itemKey(i), section: i.kind, glyph: i.kind === 'needs' ? '!' : '·', alias: '', task: '', note: i.title, since: i.at, actions: ['reply', 'dismiss'] })
  const live = s.items.filter(i => dismissed[itemKey(i)] !== true)
  return {
    needs: live.filter(i => i.kind === 'needs').sort((a, b) => a.at - b.at).map(row),
    fyi: live.filter(i => i.kind === 'fyi').reverse().map(row),
  }
}

// Quick keys of an Item: the marker options when present, else yes, no, hold.
export const quickKeys = (i: Item): string[] => (i.options.length ? i.options : [...DEFAULT_KEYS])
export const quickLine = (i: Item): string => quickKeys(i).map((k, n) => `${n + 1} ${k}`).join('   ')
