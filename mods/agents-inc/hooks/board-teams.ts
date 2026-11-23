// Spec 050 Phase 3: Teams across sessions. Pure functions, no `$`, no I/O, zero model calls.
// Shared data lives in `$.store` under one key per session, `team.<sessionId>`, written only by that session (spike S1:
// distinct keys never lose updates; one shared writable key does). Readers age out stale keys. A Team is its session id.
import type { Entry } from './board-model'
import type { ItemStore } from './board-items'
import { addFyi } from './board-items'

export type TeamRec = { id: string; name: string; needs: number; working: number; flag: boolean; at: number }

export const TEAM_PREFIX = 'team.'
// The Board polls every 2000 ms (board.tsx POLL_MS) and rewrites its key each poll. A reader ignores a key whose heartbeat
// is older than three polls: one missed poll or a slow disk write does not flicker, a dead session leaves within 6 s.
export const TEAM_STALE_MS = 6000
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
  // FYI to another Team's CoS: accepted means queued for its Chief. The plugin cannot observe receipt, and the Worker never gets it directly.
  if (ok) addFyi(items, `FYI queued for ${t.teamName} about ${t.alias}, not delivered to the Worker`, text, now)
  else addFyi(items, `FYI to ${t.teamName} about ${t.alias} not delivered: ${reason}`, text, now)
  return { delivered: ok, close: ok, line: ok ? undefined : `not delivered: ${reason}` }
}

// --- chat commands: the operator types in the composer (Phase 2 pattern) ----------------------------------------------

export const REF_MIN = 4
export const SEND_CMD = 'board-send'
export const MEMO_CMD = 'board-memo'
export const TELL_CMD = 'board-tell'
// What Board puts in the composer: the command, a short ref, a trailing space. The operator types the text and presses Enter.
// Fills carry the full id, so a typed command never depends on a prefix being unique; a hand-typed prefix still works.
export const teamRef = (id: string): string => id
export const agentRef = (id: string): string => id
export const fillSend = (t: { id: string }): string => `/${SEND_CMD} ${teamRef(t.id)} `
export const fillMemo = (a: { id: string }): string => `/${MEMO_CMD} ${agentRef(a.id)} `

export type Parsed = { ok: true; target: Target; text: string } | { ok: false; line: string }
const refuse = (why: string): Parsed => ({ ok: false, line: `not delivered: ${why}` })
const split = (args: string): [string, string] => {
  const m = /^\s*(\S+)\s*([\s\S]*)$/.exec(args)
  return m ? [m[1]!, m[2]!.trim()] : ['', '']
}
function pick<T extends { id: string }>(ref: string, all: T[], what: string): T | string {
  if (!ref) return `no ${what} given`
  const exact = all.filter(x => x.id === ref)
  if (exact.length === 1) return exact[0]!
  const hit = all.filter(x => x.id.startsWith(ref))
  if (!hit.length) return `no live ${what} matches "${ref}" ${what === 'Team' ? '(it may have gone; press Enter on the line again)' : '(it may have gone)'}`
  if (hit.length > 1) return `"${ref}" matches ${hit.length} ${what}s; type more of the ref`
  return hit[0]!
}

// `/board-send <teamRef> <text>`: the ref must name exactly one live other Team.
export function parseSend(args: string, teams: TeamRec[]): Parsed {
  const [ref, text] = split(args)
  const t = pick(ref, teams, 'Team')
  if (typeof t === 'string') return refuse(t)
  return text ? { ok: true, target: { kind: 'team', id: t.id, name: t.name }, text } : refuse('no text')
}

// `/board-memo <agentRef> <text>`: the ref must name exactly one live own delegate.
export function parseMemo(args: string, agents: Array<{ id: string; alias: string }>, ownId: string, ownName: string): Parsed {
  const [ref, text] = split(args)
  const a = pick(ref, agents, 'delegate')
  if (typeof a === 'string') return refuse(a)
  return text ? { ok: true, target: { kind: 'memo', agentId: a.id, alias: a.alias, teamId: ownId, teamName: ownName }, text } : refuse('no text')
}

// `/board-tell <teamRef> <alias> <text>`: another Team's delegate is not listed here, so it is named by hand.
export function parseTell(args: string, teams: TeamRec[]): Parsed {
  const [ref, rest] = split(args)
  const t = pick(ref, teams, 'Team')
  if (typeof t === 'string') return refuse(t)
  const [alias, text] = split(rest)
  if (!alias || !text) return refuse('use /board-tell <teamRef> <delegate> <text>')
  return { ok: true, target: { kind: 'memo', agentId: alias, alias, teamId: t.id, teamName: t.name }, text }
}

// Only the operator's own Enter in the composer is a deliberate send: a plugin, the model or the bridge never is.
// The ref and text of a Memo's args, for a target that has gone (the caller then looks the ref up among agents already seen).
export const memoRefText = (args: string): [string, string] => split(args)

export const isPerson = (origin: unknown): boolean => (origin as { kind?: unknown } | undefined)?.kind === 'composer'

// --- send text screen (D91: credential screen and 64 KiB limit) --------------------------------------------------------

export const MAX_BYTES = 64 * 1024
// A first filter in the spirit of D88, kept stricter and simpler: any mention of a secret location or a secret-shaped
// assignment is refused. The repo's real credential screen is Python (agents_inc dispatch); no TypeScript copy exists to
// reuse. Limit: prose that hides a request (encoded or indirect) is not seen.
// Ported from agents_inc/install/dispatch.py CREDENTIAL_RE (the D54 resume screen): a home credential path with a further
// non-glob segment, key files as path tokens, `.env` after a separator or ~, and a backticked read of `.env`.
const HOME_CRED = /(~|\$HOME|\$\{HOME\}|\/Users\/[^/\s]+|\/home\/[^/\s]+|\/root)\/\.(claude(?!\/skills\/(?!\S*\.\.))(?!\/AGENTS\.md(?=$|[\s'"`,;)]))|codex|ssh|config|aws|gnupg|netrc|local(?!\/(?:bin|share\/agents-inc|state\/agents-inc)\/(?!\S*\.\.))|codex-bridge(?!\/usage\.jsonl(?=$|[\s'"`,;)]|\.(?:\s|$))))\b\/(?![^\s/]*[*?\[])[^\s/'"`,;)]+/i
const KEY_FILE = /(?<![^\s/='"])(?:id_rsa|id_ed25519|[^\s/]*\.(?:pem|key))(?=$|[\s/'".,;:)])/i
const ENV_AFTER_SEP = /(?<=[/~])\.env(?:\.[\w.-]+)?\b/i
const ENV_READ_TICKED = /`[^`\n]*?(?<![\w-])(?:cat|read|print|open|source|dump|echo|show|less|head|tail)\s+\.env(?:\.[\w.-]+)?(?=[\s`])[^`\n]*`/i
// SECRET_VAR_PRINT_RE: a print verb, then within the clause an upper-case name ending in a secret word ($OPENAI_API_KEY,
// ${GH_TOKEN}, printenv AWS_SECRET_ACCESS_KEY). The verb is case-insensitive, the name is not, so `$tokens` passes.
const PRINT_VERB = /\b(?:print(?:env)?|echo|show|dump|output|paste|reveal|log|report|copy|cat|env)\b/gi
const SECRET_NAME = /(?<![\w])\$?\{?[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Z0-9_]*\b/
export function printsSecretVar(text: string): boolean {
  for (const m of text.matchAll(PRINT_VERB)) {
    const rest = text.slice((m.index ?? 0) + m[0].length)
    const clause = /^[^.;\n]{0,60}?(?<![\w])\$?\{?[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Z0-9_]*\b/.exec(rest)
    if (clause && SECRET_NAME.test(clause[0])) return true
  }
  return false
}
// A credential directory or file under any home path (`~`, $HOME, /Users/x, /home/x, /root), even bare: `/root/.aws`.
const HOME_CRED_DIR = /(~|\$HOME|\$\{HOME\}|\/Users\/[^/\s]+|\/home\/[^/\s]+|\/root)\/\.(ssh|aws|gnupg|netrc|npmrc|pypirc|docker\/config\.json|kube\/config|config\/(gh|gcloud)|codex\/auth\.json|claude\/\.?credentials(\.json)?)(?![\w-])/i
const SECRET = [
  HOME_CRED_DIR, HOME_CRED, KEY_FILE, ENV_AFTER_SEP, ENV_READ_TICKED,
  /(^|[\s/"'`=~])\.env(\.[\w-]+)?(?![\w-])/i,
  /~\/\.(ssh|aws|gnupg|netrc|config\/(gh|gcloud)|claude\/\.?credentials|codex\/auth)/i,
  /\bauth\.json\b|\.credentials\.json|\bid_(rsa|ed25519|ecdsa)\b/i,
  /\.(pem|key)(?![\w-])/i,
  /\b(password|passwd|token|secret|api[_-]?key|apikey|authorization|credentials?)\b\s*[=:]\s*\S/i,
  /\bbearer\s+[\w.~+/-]{8,}/i,
  /\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[\w-]{10,})/,
]
export function screenText(text: string): string | undefined {
  if (new TextEncoder().encode(text).length > MAX_BYTES) return 'text is over the 64 KiB limit'
  if (SECRET.some(r => r.test(text)) || printsSecretVar(text)) return 'text names a credential or secret location (credential screen)'
  return undefined
}

