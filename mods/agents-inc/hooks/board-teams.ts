// Spec 050 Phase 3: Teams across sessions. Pure functions, no `$`, no I/O, zero model calls.
// Shared data lives in `$.store` under one key per session, `team.<sessionId>`, written only by that session (spike S1:
// distinct keys never lose updates; one shared writable key does). Readers age out stale keys. A Team is its session id.
import type { Entry } from './board-model'
import type { ItemStore } from './board-items'
import { addFyi } from './board-items'
import type { Line } from './board-render'

export type TeamRec = { id: string; name: string; needs: number; working: number; flag: boolean; at: number }

export const TEAM_PREFIX = 'team.'
// The Board polls every 2000 ms (board.tsx POLL_MS) and rewrites its key each poll. A reader ignores a key whose heartbeat
// is older than three polls: one missed poll or a slow disk write does not flicker, a dead session leaves within 6 s.
export const TEAM_STALE_MS = 6000
// A key this old belongs to a session long gone; any reader may delete it (the owner rewrites on its next poll anyway).
export const TEAM_DEAD_MS = 60 * 60 * 1000
export const NAME_W = 12
export const MEMO_PREFIX = 'Memo from the operator via Board: '
export const FYI_PREFIX = 'FYI from the operator via Board: '

const clip = (s: string, n: number): string => (s.length <= n ? s : n <= 1 ? s.slice(0, Math.max(0, n)) : s.slice(0, n - 1) + '…')
export const teamKey = (id: string): string => TEAM_PREFIX + id

export function summary(id: string, name: string, needs: number, working: number, now: number): TeamRec {
  return { id, name: clip(name || 'team', NAME_W - 1), needs, working, flag: needs > 0, at: now }
}

// One store value read back. Anything with the wrong shape, or whose id is not the key's, is dropped.
export function parseTeam(key: string, v: unknown): TeamRec | undefined {
  const o = (v && typeof v === 'object' ? v : {}) as Record<string, unknown>
  const id = key.startsWith(TEAM_PREFIX) ? key.slice(TEAM_PREFIX.length) : ''
  if (!id || o.id !== id || typeof o.name !== 'string' || typeof o.at !== 'number') return undefined
  const n = (x: unknown): number => (typeof x === 'number' && x >= 0 && Number.isFinite(x) ? Math.floor(x) : 0)
  return { id, name: o.name, needs: n(o.needs), working: n(o.working), flag: n(o.needs) > 0, at: o.at }
}

// The other live Teams: not this session, heartbeat within the stale bound. Needs-you first, then busier, then name.
export function liveTeams(recs: Array<TeamRec | undefined>, ownId: string, now: number): TeamRec[] {
  return recs
    .filter((t): t is TeamRec => !!t && t.id !== ownId && now - t.at <= TEAM_STALE_MS && t.at - now <= TEAM_STALE_MS)
    .sort((a, b) => Number(b.flag) - Number(a.flag) || b.working - a.working || (a.name < b.name ? -1 : a.name > b.name ? 1 : a.id < b.id ? -1 : 1))
}

export const deadKeys = (all: Array<[string, TeamRec | undefined]>, now: number): string[] =>
  all.filter(([, t]) => !t || now - t.at > TEAM_DEAD_MS).map(([k]) => k)

export function teamNote(t: TeamRec): string {
  const parts = [...(t.needs ? [`${t.needs} needs you`] : []), ...(t.working ? [`${t.working} working`] : [])]
  return parts.length ? parts.join(' · ') : 'idle'
}

export function teamEntries(teams: TeamRec[]): Entry[] {
  return teams.map(t => ({
    key: `team:${t.id}`, section: 'team' as const, glyph: t.needs ? '!' : t.working ? '●' : '◌', alias: t.name, task: '', note: teamNote(t),
    teamId: t.id, since: t.at, actions: ['reply' as const],
  }))
}

// --- targets and sends ------------------------------------------------------------------------------------------------

// What the open region will send to. `team`: a reply on a Team line, to that Team's CoS. `memo`: a Memo to a delegate:
// own session's native Worker by agent id; with another Team's id it becomes an FYI to that Team's CoS.
export type Target =
  | { kind: 'team'; id: string; name: string }
  | { kind: 'memo'; agentId: string; alias: string; teamId: string; teamName: string }
export type Plan = { to: { sessionId: string } | { agentId: string }; text: string; target: Target; how: 'reply' | 'memo' | 'fyi' }

// Only the operator's own press builds a plan; CoS markers never reach here (D91).
export function planSend(t: Target, text: string, ownId: string): Plan {
  if (t.kind === 'team') return { to: { sessionId: t.id }, text, target: t, how: 'reply' }
  if (!t.teamId || t.teamId === ownId) return { to: { agentId: t.agentId }, text: MEMO_PREFIX + text, target: t, how: 'memo' }
  // Another Team's Worker has no direct path (S2): its CoS gets an FYI and decides what to do.
  return { to: { sessionId: t.teamId }, text: `${FYI_PREFIX}please tell your delegate ${t.alias}: ${text}`, target: t, how: 'fyi' }
}

export type Settled = { delivered: boolean; close: boolean; line?: string }

// Record what the host answered. A send the host did not accept never closes the region, so the target stays; a Memo or FYI
// that did not go as asked leaves one FYI row, with the text kept in its detail.
export function settle(p: Plan, text: string, result: unknown, items: ItemStore, sent: string[], now: number): Settled {
  const r = (result && typeof result === 'object' ? result : {}) as { isDelivered?: unknown; reason?: unknown }
  const ok = r.isDelivered === true
  const reason = String(r.reason ?? 'no reason given')
  const t = p.target
  if (p.how === 'reply') {
    if (ok) sent.push(`to ${t.kind === 'team' ? t.name : '?'}: ${text}`)
    return { delivered: ok, close: ok, line: ok ? undefined : `not delivered: ${reason}` }
  }
  if (t.kind !== 'memo') return { delivered: false, close: false }
  if (p.how === 'memo') {
    if (ok) sent.push(`memo to ${t.alias}: ${text}`)
    else addFyi(items, `Memo to ${t.alias} not delivered: ${reason}`, text, now)
    return { delivered: ok, close: ok, line: ok ? undefined : `not delivered: ${reason}` }
  }
  // FYI to another Team's CoS: accepted means FYI sent, never "delivered to the Worker".
  if (ok) addFyi(items, `FYI sent to ${t.teamName} about ${t.alias}, not delivered to the Worker`, text, now)
  else addFyi(items, `FYI to ${t.teamName} about ${t.alias} not delivered: ${reason}`, text, now)
  return { delivered: ok, close: ok, line: ok ? undefined : `not delivered: ${reason}` }
}

export function targetLines(t: Target, note: string | undefined, sent: string[], width: number): Line[] {
  const dim = (s: string): Line => [{ t: clip(s, width), dim: true }]
  const who = t.kind === 'team' ? `reply to ${t.name} (its Chief)` : `memo to ${t.alias}`
  const lines: Line[] = [[], dim('SEND'), [{ t: clip(who, width), color: 'yellow' }]]
  if (note) lines.push([{ t: clip(note, width), color: 'red' }])
  lines.push(dim('type the text, then send; x close'))
  for (const s of sent.slice(-3)) lines.push([{ t: clip('  ' + s, width) }])
  return lines
}
