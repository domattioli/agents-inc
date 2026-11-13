// Spec 039: pure functions behind the mission map. No engine nouns, no I/O: the register hook reads, these decide.
import { RUNGS } from './rungs'

export type Category = 'Review' | 'Build' | 'Write' | 'Scout' | 'Plan' | 'Other'
export type State = 'running' | 'review' | 'done' | 'failed' | 'paused' | 'lost'
export type Delegate = {
  id: string
  source: 'subagent' | 'dispatch'
  nickname: string
  rung: string
  task: string
  category: Category
  state: State
  // When the current failed or lost episode began (ms); with the id it names one alert event (ackKey).
  alertAt?: number
  // Newest change time among a dispatch run's files (ms), the run's "last event".
  newest?: number
  // When the delegate started and ended (ms), as the poll saw them (a dispatch run: its id stamp and its newest file
  // time; a subagent: first poll that listed it, first poll that saw it end). Feed order and durations.
  startedAt?: number
  endedAt?: number
  // A subagent spawned by another subagent: that one's id (engine AgentInfo.parentId). Spawn arcs.
  parentId?: string
}
// unacked: the ack keys (ackKey) of the station's failed or lost delegates not yet acknowledged.
export type Station = { category: Category; delegates: Delegate[]; lit: boolean; unacked: string[] }

// A dispatch run with no outcome and no file change for this long is lost (spec 039 FR-012).
export const LOST_MS = 5 * 60 * 1000
export const isAlert = (s: State): boolean => s === 'failed' || s === 'lost'
// One acknowledgement covers one failure (or lost) event of one delegate, not the id forever.
export const ackKey = (d: Pick<Delegate, 'id' | 'alertAt'>): string => `${d.id}@${d.alertAt ?? 0}`
export const ackId = (key: string): string => key.slice(0, key.lastIndexOf('@'))

export const CATEGORIES: Category[] = ['Review', 'Build', 'Write', 'Scout', 'Plan', 'Other']
const TASK_CAP = 80

const SUBAGENT_TYPE: Record<string, Category> = { Explore: 'Scout', Plan: 'Plan', 'claude-code-guide': 'Scout' }
const TASK_KIND: Record<string, Category> = {
  review: 'Review', verify: 'Review', code: 'Build', fix: 'Build', docs: 'Write', write: 'Write',
  scout: 'Scout', read: 'Scout', plan: 'Plan', design: 'Plan',
}
const ROLE_WORD: Record<string, Category> = {
  reviewer: 'Review', workhorse: 'Build', scout: 'Scout', grunt: 'Scout', orchestrator: 'Plan',
}
const VERB: Record<string, Category> = {
  review: 'Review', verify: 'Review', audit: 'Review', grade: 'Review',
  implement: 'Build', fix: 'Build', refactor: 'Build', patch: 'Build', code: 'Build', build: 'Build',
  write: 'Write', draft: 'Write', document: 'Write', file: 'Write',
  read: 'Scout', find: 'Scout', search: 'Scout', list: 'Scout', summarize: 'Scout', scout: 'Scout',
  triage: 'Scout', explore: 'Scout', locate: 'Scout', batch: 'Scout',
  plan: 'Plan', design: 'Plan', scope: 'Plan', spec: 'Plan',
}

// Plan R2: first rule that gives a category wins. The task verb comes before ROLE: a real ROLE starts with the rung word
// ("Workhorse (sonnet) ..."), so ROLE first would put every sonnet dispatch in Build.
export function categoryOf(d: { text: string; subagentType?: string; taskKind?: string; role?: string; rung?: string }): Category {
  if (d.subagentType && SUBAGENT_TYPE[d.subagentType]) return SUBAGENT_TYPE[d.subagentType]
  if (d.taskKind && TASK_KIND[d.taskKind.toLowerCase()]) return TASK_KIND[d.taskKind.toLowerCase()]
  const stripped = (d.text ?? '')
    .replace(/^\s*(orchestrator|workhorse|grunt|executive|reviewer)\s*:\s*/i, '')
    .replace(/^\s*dispatch\s+\S+\s+to\s+/i, '')
  const clause = stripped.split(/[.:;\n]/)[0]
  for (const w of clause.toLowerCase().split(/[^a-z]+/)) if (VERB[w]) return VERB[w]
  const roleWord = (d.role ?? '').trim().split(/[^A-Za-z]+/)[0]?.toLowerCase()
  if (roleWord && ROLE_WORD[roleWord]) return ROLE_WORD[roleWord]
  if (d.rung === 'grunt') return 'Scout'
  // A general-purpose subagent whose description names no work reads as a scout: the pane cannot see its model or prompt.
  if (d.subagentType === 'general-purpose') return 'Scout'
  return 'Other'
}

// Plan R3: rung from the table in rungs.ts; the model id first, then the nickname (without `agents-inc:`).
// A run dir name holds the model as dispatch.py new_run_id spells it: `/` and `:` (and anything outside [A-Za-z0-9._-])
// turned to `_`; the table is matched in that spelling too.
const safe = (s: string): string => s.replace(/[^A-Za-z0-9._-]/g, '_')
const SAFE_RUNGS: Record<string, string> = Object.fromEntries(Object.entries(RUNGS).map(([k, v]) => [safe(k), v]))
export function rungOf(model: string, nickname?: string): string {
  const nick = (nickname ?? '').replace(/^agents-inc:/, '')
  return RUNGS[model] ?? RUNGS[nick] ?? SAFE_RUNGS[safe(model)] ?? '?'
}

// The model part of a run dir name `<YYYYMMDDTHHMMSSZ>-<model>-<6 hex>`: everything between the stamp and the
// last `-` part (a model id may hold `-`, as in gpt-6-luna).
export function dirModel(dirName: string): string {
  const m = /^\d{8}T\d{6}Z-(.+)-[^-]+$/.exec(dirName)
  return m?.[1] ?? ''
}

// The UTC start time in a run dir name (dispatch.py:202), or undefined.
export function dirTime(dirName: string): number | undefined {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z-/.exec(dirName)
  if (!m) return undefined
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number) as [number, number, number, number, number, number]
  return Date.UTC(y, mo - 1, d, h, mi, s)
}

// FR-012: a dispatch run still drawn as running whose last event is LOST_MS or more ago is lost; its alert event is
// named by that last event time. Any other delegate is returned unchanged.
export function withLost(d: Delegate, newest: number | undefined, now: number): Delegate {
  if (d.source !== 'dispatch' || d.state !== 'running' || newest === undefined) return d
  return now - newest >= LOST_MS ? { ...d, state: 'lost', alertAt: newest, newest } : d
}

// Plan R4. A subagent status or dispatch outcome that is empty means "no end seen": running.
// Engine AgentStatus: pending | running | waiting | idle | completed | failed | killed. A live agent never draws as done:
// pending draws as running (queued is not drawn in v1), waiting and idle as paused. Only a known terminal status is done.
// A status not known here draws as running: the engine still lists the agent, so it has not ended (an agent the engine
// stops listing is marked finished by mergeAgents).
const SUB_DONE = new Set(['completed', 'finished', 'done'])
const SUB_FAILED = new Set(['failed', 'error', 'killed'])
const SUB_PAUSED = new Set(['waiting', 'idle'])
export function lifecycleOf(source: 'subagent' | 'dispatch', outcomeOrStatus?: string | null, reason?: string | null): State {
  const s = String(outcomeOrStatus ?? '')
  if (source === 'subagent') {
    if (SUB_FAILED.has(s)) return 'failed'
    if (SUB_DONE.has(s)) return 'done'
    if (SUB_PAUSED.has(s)) return 'paused'
    return 'running' // '', running, pending, and any status not known
  }
  if (s === '') return 'running'
  if (s === 'unverified') return 'review'
  if (s === 'green') return 'done'
  if (s === 'red' && reason === 'quota-paused') return 'paused'
  return 'failed' // red, cancelled, blocked, launch-failed, refused-*, and any outcome not known (dry-run is skipped earlier)
}

// A dry run (dispatch.py writes outcome "dry-run") launched nothing: the map does not draw it, as the pane's list never did.
export const isDryRun = (runJson?: string): boolean => parseObj(runJson).outcome === 'dry-run'

function parseObj(text?: string): Record<string, unknown> {
  if (!text) return {}
  try {
    const v = JSON.parse(text)
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

// run.start (line 1 of events.jsonl) carries model and kind while run.json does not exist yet (plan R1 findings).
function runStart(eventsJsonl?: string): Record<string, unknown> {
  for (const line of (eventsJsonl ?? '').split('\n')) {
    const ev = parseObj(line.trim()).event as Record<string, unknown> | undefined
    if (ev && ev.type === 'run.start') return ev
  }
  return {}
}

export function runFromFiles(runJson: string | undefined, slotsJson: string | undefined, dirName: string, eventsJsonl?: string): Delegate {
  const run = parseObj(runJson)
  const slots = parseObj(slotsJson)
  const start = runStart(eventsJsonl)
  const fromDir = dirModel(dirName)
  const model = String(run.model ?? start.model ?? slots.MODEL ?? fromDir)
  const task = String(slots.TASK ?? '').split('\n')[0].slice(0, TASK_CAP)
  const rung = rungOf(model)
  return {
    id: String(run.run_id ?? start.run_id ?? dirName),
    source: 'dispatch',
    nickname: model || '?',
    rung,
    task,
    category: categoryOf({
      text: task,
      taskKind: typeof slots.TASK_KIND === 'string' ? slots.TASK_KIND : undefined,
      role: typeof slots.ROLE === 'string' ? slots.ROLE : undefined,
      rung,
    }),
    state: lifecycleOf('dispatch', run.outcome == null ? undefined : String(run.outcome), run.reason == null ? undefined : String(run.reason)),
  }
}

// Run ids start with a UTC `YYYYMMDDTHHMMSSZ` (dispatch.py:202). Keep dirs started at or after the session start.
export function sessionRuns(dirNames: string[], sessionStartIso: string): string[] {
  const start = Math.floor(Date.parse(sessionStartIso) / 1000) * 1000
  if (Number.isNaN(start)) return []
  return dirNames.filter(n => {
    const t = dirTime(n)
    return t !== undefined && t >= start
  })
}

export function stations(delegates: Delegate[], acked: Record<string, string[]>): Station[] {
  return CATEGORIES.map(category => {
    const ds = delegates.filter(d => d.category === category)
    const seen = new Set(acked[category] ?? [])
    return {
      category,
      delegates: ds,
      lit: ds.some(d => d.state === 'running' || d.state === 'review'),
      unacked: ds.filter(d => isAlert(d.state)).map(ackKey).filter(k => !seen.has(k)),
    }
  })
}

// Plan R6: grid from 70 columns, stacked from 30, one line per station below.
export function layoutFor(columns: number): 'grid' | 'stacked' | 'line' {
  return columns >= 70 ? 'grid' : columns >= 30 ? 'stacked' : 'line'
}

// Spec 039 narration (pass 3): the status line and the feed under the map. Pure; only mission data, nothing invented.
export const ellipsis = (s: string, n: number): string => (n <= 0 ? '' : s.length <= n ? s : n === 1 ? '…' : s.slice(0, n - 1) + '…')
const live = (d: Delegate) => d.state === 'running' || d.state === 'review'
// Newest start first; a delegate with no start time sorts after those with one, later-listed first.
export function newestFirst(ds: Delegate[]): Delegate[] {
  return ds
    .map((d, i) => [d, i] as const)
    .sort((a, b) => (b[0].startedAt ?? -Infinity) - (a[0].startedAt ?? -Infinity) || b[1] - a[1])
    .map(([d]) => d)
}

export function duration(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))} ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`
  const m = Math.floor(ms / 60000)
  return m < 60 ? `${m}m ${String(Math.floor((ms % 60000) / 1000)).padStart(2, '0')}s` : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`
}

// "Nothing is running." or the newest running delegate, `name: task`, with "and N more" for the others running.
export function statusLine(ds: Delegate[], width = 80): string {
  const run = newestFirst(ds.filter(live))
  if (!run.length) return 'Nothing is running.'
  const more = run.length > 1 ? ` and ${run.length - 1} more` : ''
  const head = run[0]!.task ? `${run[0]!.nickname}: ${run[0]!.task}` : run[0]!.nickname
  return ellipsis(head, width - more.length) + more
}

export type FeedKind = 'running' | 'failed' | 'done' | 'paused'
// `role` is the delegate's rung word ('' when unknown). `lead` (bullet and name), `roleCol` (the dim role column with its
// trailing space, '' when dropped) and `tail` (task and right column) are the pieces of `text` for the register to style.
export type FeedRow = { id: string; kind: FeedKind; bullet: string; name: string; task: string; right: string; role: string; lead: string; roleCol: string; tail: string; text: string }
const NAME_W = 14
const RIGHT_W = 8
// Below this task width the role column is dropped before the task is cut any further.
const TASK_MIN_WITH_ROLE = 16
// Role words come from the glossary rungs, via the rung the pane already holds; anything else (`?`) is unknown: blank.
const ROLE_WORDS = ['executive', 'orchestrator', 'workhorse', 'grunt']
export const roleOf = (d: Pick<Delegate, 'rung'>): string => (ROLE_WORDS.includes(d.rung) ? d.rung : '')
// The main session's role (glossary: Chief of Staff, the agent the operator talks to), shown beside `main session`.
export const MAIN_ROLE = 'chief of staff'
// The feed: one row per delegate, newest on top, at most `cap` rows, each `width` columns:
// bullet, name, role (dim, fixed width), task (ellipsis), right-aligned `running` / `review` / `paused` / `lost` or the run's duration.
export function feed(ds: Delegate[], width: number, cap: number): FeedRow[] {
  const picked = newestFirst(ds).slice(0, Math.max(0, cap))
  const roleW = Math.max(0, ...picked.map(d => roleOf(d).length))
  const baseW = Math.max(0, width - 2 - NAME_W - 1 - 1 - RIGHT_W)
  const withRole = roleW > 0 && baseW - roleW - 1 >= TASK_MIN_WITH_ROLE
  const taskW = withRole ? baseW - roleW - 1 : baseW
  return picked.map(d => {
    const kind: FeedKind = live(d) ? 'running' : isAlert(d.state) ? 'failed' : d.state === 'paused' ? 'paused' : 'done'
    const bullet = kind === 'running' ? '●' : kind === 'failed' ? '✗' : kind === 'paused' ? '◐' : '·'
    const span = d.startedAt !== undefined && d.endedAt !== undefined ? duration(d.endedAt - d.startedAt) : '—'
    const right = d.state === 'running' ? 'running' : d.state === 'review' || d.state === 'paused' || d.state === 'lost' ? d.state : span
    const name = ellipsis(d.nickname, NAME_W).padEnd(NAME_W)
    const task = ellipsis(d.task, taskW).padEnd(taskW)
    const role = roleOf(d)
    const lead = `${bullet} ${name} `
    const roleCol = withRole ? role.padEnd(roleW) + ' ' : ''
    const tail = `${task} ${right.padStart(RIGHT_W)}`
    return { id: d.id, kind, bullet, name: name.trim(), task: task.trim(), right, role, lead, roleCol, tail, text: lead + roleCol + tail }
  })
}

// Hierarchy pass (2026-11-12): who is Lead and who is the primary Worker, from real data only (parentId, rung, state,
// start time). Glossary: a Lead manages the run and starts Workers; a Worker is any agent reporting to a Lead.
// Lead: a delegate that has started delegates of its own (a child on the map names it as parentId). Several: the higher
// rung (executive > orchestrator > workhorse > grunt > unknown), then the earliest start (unknown start last), then
// list order. None: the main session does the Lead's job itself (no Lead delegate; the map shows "CoS as Lead").
// Primary Worker: among the Lead's children (all delegates when there is no Lead) the workhorse-rung delegate running
// now with the newest start; none running: no Worker hub. At most these two hubs.
export type Hierarchy = { lead?: Delegate; worker?: Delegate }
const RUNG_RANK: Record<string, number> = { executive: 4, orchestrator: 3, workhorse: 2, grunt: 1 }
export function hierarchy(ds: Delegate[]): Hierarchy {
  const ids = new Set(ds.map(d => d.id))
  const parents = new Set(ds.filter(d => d.parentId && d.parentId !== d.id && ids.has(d.parentId)).map(d => d.parentId!))
  const lead = ds
    .map((d, i) => [d, i] as const)
    .filter(([d]) => parents.has(d.id))
    .sort(
      (a, b) =>
        (RUNG_RANK[b[0].rung] ?? 0) - (RUNG_RANK[a[0].rung] ?? 0) ||
        (a[0].startedAt ?? Infinity) - (b[0].startedAt ?? Infinity) ||
        a[1] - b[1],
    )[0]?.[0]
  const pool = lead ? ds.filter(d => d.parentId === lead.id) : ds
  const worker = newestFirst(pool.filter(d => d.rung === 'workhorse' && d.state === 'running' && d.id !== lead?.id))[0]
  return { ...(lead ? { lead } : {}), ...(worker ? { worker } : {}) }
}

// The static map's role lines (every surface): who is CoS, Lead and primary Worker, in at most two lines of `width`.
export function hierarchyLines(ds: Delegate[], model: string, width = 80): string[] {
  const h = hierarchy(ds)
  const cos = `CoS: main session${model ? ` (${model})` : ''}`
  const lead = h.lead ? `Lead: ${h.lead.nickname}${roleOf(h.lead) ? ` (${roleOf(h.lead)})` : ''}` : 'Lead: none, the CoS leads'
  const worker = h.worker ? `Worker: ${h.worker.nickname}` : 'Worker: none running'
  const one = `${cos} · ${lead} · ${worker}`
  return one.length <= width ? [one] : [ellipsis(cos, width), ellipsis(`${lead} · ${worker}`, width)]
}
