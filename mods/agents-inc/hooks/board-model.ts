// Spec 050 Phase 1: the pure model behind the Board. No engine nouns and no I/O: the hooks read and write, this decides.
// Zero model calls: every state here comes from host events, the agent list, transcript tails and dispatch run files.

export type Listed = { id: string; type?: string; name?: string; description?: string; status?: string; parentId?: string }
export type AgentRec = { id: string; type: string; description: string; status: string; since: number }
// One dispatch run of this session, as read from its run dir. `newest` is the newest file time, the run's last event.
export type RunRec = {
  id: string
  model: string
  task: string
  outcome: string
  reason: string
  resetAt?: number
  startedAt: number
  newest: number
}
// An operator hold the host announced with `classic.PermissionRequest`. `status` is the agent's status when it began:
// a status change or SubagentStop clears it, because no event says a prompt was answered.
export type Hold = { agentId: string; question: string; at: number; status: string }
export type StepRec = { text: string; sig: string; changedAt: number; readAt: number }

export type Section = 'needs' | 'fyi' | 'trouble' | 'working'
export type Action = 'open' | 'stop' | 'dismiss'
export type Entry = {
  // Identity of the selection: stable across refreshes. Trouble and needs keys carry the episode start.
  key: string
  section: Section
  glyph: string
  alias: string
  task: string
  // NEEDS YOU: the whole line after the number. Others: the state note or current step.
  note: string
  agentId?: string
  runId?: string
  since: number
  actions: Action[]
}
export type Board = { needs: Entry[]; fyi: Entry[]; trouble: Entry[]; working: Entry[] }

export type Mem = {
  start: number
  agents: Record<string, AgentRec>
  steps: Record<string, StepRec>
  holds: Record<string, Hold>
  runs: Record<string, RunRec>
  // Dismissed episodes of this session only; nothing persists beyond it (FR-019).
  dismissed: Record<string, true>
  selected?: string
  opened: boolean
  closedByPerson: boolean
  busy: boolean
  board: Board
  sig: string
  notice: string
}

export const LOST_MS = 5 * 60 * 1000
export const QUIET_MS = 60 * 1000
export const STEP_MS = 5000
export const RUNS = '.scratch/agents-inc-runs'
export const STOP_TEXT = 'Stop now and report what you have.'
const LIVE = new Set(['pending', 'running', 'waiting', 'idle'])
const DONE = new Set(['completed', 'finished', 'done'])

export const emptyBoard = (): Board => ({ needs: [], fyi: [], trouble: [], working: [] })
export const newMem = (): Mem => ({
  start: 0, agents: {}, steps: {}, holds: {}, runs: {}, dismissed: {}, selected: undefined, opened: false, closedByPerson: false,
  busy: false, board: emptyBoard(), sig: '', notice: '',
})
export const board: Mem = newMem()
// A session start clears everything Board remembers.
export function resetMem(m: Mem): void {
  Object.assign(m, newMem())
}

export const clip = (s: string, n: number): string => (s.length <= n ? s : n <= 1 ? s.slice(0, Math.max(0, n)) : s.slice(0, n - 1) + '…')

export function ago(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h`
}

// Model aliases and agent types shown as one short word: `agents-inc:luna` and `claude-sonnet-4-5` read luna and sonnet.
export function alias(type: string): string {
  const t = String(type ?? '').replace(/^agents-inc:/, '').replace(/^claude-/, '')
  const word = (/^[a-z][a-z0-9.]*(?:-[a-z][a-z0-9.]*)*/i.exec(t)?.[0] ?? t).toLowerCase()
  const known = /^(opus|sonnet|haiku|luna|terra|sol|astra|fable)/.exec(word)
  return clip(known ? known[1]! : word || '?', 10)
}

export function hhmm(ms: number): string {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// --- the host's agent list --------------------------------------------------------------------------------------

// Merge one agent.list answer by id. An agent the host stops listing stays: finished unless it already ended, so a
// failed or killed one keeps its TROUBLE row until dismissed. `since` moves only when the status changes.
export function ingestAgents(m: Mem, listed: Listed[], now: number): void {
  const seen = new Set<string>()
  for (const a of listed) {
    if (!a || typeof a.id !== 'string' || typeof a.type !== 'string') continue
    seen.add(a.id)
    const status = String(a.status ?? 'running')
    const prev = m.agents[a.id]
    m.agents[a.id] = {
      id: a.id, type: a.type, description: String(a.description ?? a.name ?? ''), status,
      since: prev && prev.status === status ? prev.since : now,
    }
    const hold = m.holds[a.id]
    if (hold && hold.status !== status) delete m.holds[a.id]
  }
  for (const a of Object.values(m.agents)) {
    if (seen.has(a.id)) continue
    if (LIVE.has(a.status)) m.agents[a.id] = { ...a, status: 'finished', since: now }
    delete m.holds[a.id]
    delete m.steps[a.id]
  }
}

export function noteHold(m: Mem, e: { agent_id?: string; tool_name?: string; tool_input?: unknown }, now: number): boolean {
  const id = typeof e.agent_id === 'string' ? e.agent_id : ''
  if (!id) return false // a hold in the main session is the operator's own prompt: no row
  m.holds[id] = { agentId: id, question: holdQuestion(String(e.tool_name ?? ''), e.tool_input), at: now, status: m.agents[id]?.status ?? 'running' }
  return true
}

export function clearHold(m: Mem, agentId: string): void {
  delete m.holds[agentId]
}

const firstLine = (s: unknown): string => String(s ?? '').split('\n').find(l => l.trim())?.trim() ?? ''
const base = (p: unknown): string => String(p ?? '').split('/').filter(Boolean).pop() ?? ''

// The question or approval a hold carries, in a few words: the tool's own question or plan, else what it would act on.
export function holdQuestion(tool: string, input: unknown): string {
  const i = (input && typeof input === 'object' ? input : {}) as Record<string, unknown>
  const text = firstLine(i.question) || firstLine(i.plan) || firstLine(i.command) || firstLine(i.url) || firstLine(i.prompt)
  if (text) return text
  const file = base(i.file_path ?? i.path)
  return file ? `${tool} ${file}` : tool || 'approval'
}

// --- current step ----------------------------------------------------------------------------------------------

// The latest action of a transcript tail as a few words: the last tool call, named by what it acts on.
export function stepOf(messages: unknown): string {
  if (!Array.isArray(messages)) return ''
  for (let k = messages.length - 1; k >= 0; k--) {
    const m = messages[k] as { role?: string; content?: unknown }
    if (m?.role !== 'assistant' || !Array.isArray(m.content)) continue
    const tool = [...m.content].reverse().find((b: any) => b?.type === 'tool_use') as { name?: string; input?: Record<string, unknown> } | undefined
    if (tool) return describeTool(String(tool.name ?? ''), tool.input ?? {})
    return ''
  }
  return ''
}

export function describeTool(name: string, input: Record<string, unknown>): string {
  switch (name) {
    case 'Edit': case 'Write': case 'MultiEdit': case 'NotebookEdit': return `edit ${base(input.file_path ?? input.notebook_path)}`.trim()
    case 'Read': return `read ${base(input.file_path)}`.trim()
    case 'Bash': return `run ${firstLine(input.command)}`.trim()
    case 'Grep': case 'Glob': return `search ${firstLine(input.pattern)}`.trim()
    case 'WebFetch': return `fetch ${String(input.url ?? '').replace(/^https?:\/\//, '').split('/')[0]}`.trim()
    case 'WebSearch': return `search ${firstLine(input.query)}`.trim()
    case 'Agent': case 'Task': return `spawn ${firstLine(input.description)}`.trim()
    default: return name.toLowerCase()
  }
}

// Record one transcript read. A changed step marks the agent active now; the same step leaves its time alone.
export function noteStep(m: Mem, id: string, messages: unknown, now: number): void {
  const text = stepOf(messages)
  const sig = `${Array.isArray(messages) ? messages.length : -1}|${text}`
  const prev = m.steps[id]
  m.steps[id] = { text, sig, changedAt: prev && prev.sig === sig ? prev.changedAt : text ? now : (prev?.changedAt ?? 0), readAt: now }
}

export const stepDue = (m: Mem, id: string, now: number): boolean => !m.steps[id] || now - m.steps[id]!.readAt >= STEP_MS

// --- dispatch runs ---------------------------------------------------------------------------------------------

// Run dir names start with a UTC `YYYYMMDDTHHMMSSZ` stamp.
export function dirTime(name: string): number | undefined {
  const x = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z-/.exec(name)
  if (!x) return undefined
  const t = Date.UTC(+x[1]!, +x[2]! - 1, +x[3]!, +x[4]!, +x[5]!, +x[6]!)
  return Number.isNaN(t) ? undefined : t
}

const parseObj = (text?: string): Record<string, any> => {
  try {
    const v = JSON.parse(text ?? '')
    return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
  } catch {
    return {}
  }
}

function resetOf(run: Record<string, any>): number | undefined {
  const v = run.reset_at ?? run.resets_at ?? run.reset
  if (typeof v === 'number' && v > 0) return v > 1e12 ? v : v * 1000
  if (typeof v === 'string' && v) {
    const t = Date.parse(v)
    return Number.isNaN(t) ? undefined : t
  }
  return undefined
}

// Build one run from the files the tick read. `newest` is the newest file time of the run dir (undefined: unknown).
export function runFrom(name: string, f: { runJson?: string; slotsJson?: string; events?: string }, newest: number | undefined): RunRec {
  const run = parseObj(f.runJson)
  const slots = parseObj(f.slotsJson)
  let outcome = run.outcome == null ? '' : String(run.outcome)
  if (!outcome && f.events) {
    for (const line of f.events.split('\n').reverse()) {
      const ev = parseObj(line.trim()).event
      if (ev && ev.type === 'run.end') {
        outcome = String(ev.outcome ?? 'done')
        break
      }
    }
  }
  const started = dirTime(name) ?? 0
  return {
    id: name,
    model: String(run.model ?? slots.MODEL ?? name.split('-')[1] ?? '?'),
    task: String(slots.TASK ?? '').split('\n')[0]!.slice(0, 80),
    outcome,
    reason: run.reason == null ? '' : String(run.reason),
    resetAt: resetOf(run),
    startedAt: started,
    newest: newest ?? started,
  }
}

// Which run dirs this session reads: started at or after the session start, not final unless a file moved. The caller
// lists each dir and passes the newest file time back through `runFrom`.
export function sessionRunNames(names: string[], start: number): string[] {
  return names.filter((n, i) => names.indexOf(n) === i && (dirTime(n) ?? -1) >= Math.floor(start / 1000) * 1000)
}

// --- the Board --------------------------------------------------------------------------------------------------

const quietNote = (ms: number): string => (ms < 60_000 ? 'quiet <1m' : `quiet ${ago(ms)}`)
const COND_AGO = new Set(['died', 'killed', 'timed out', 'failed check'])

function runCondition(r: RunRec): { section: 'needs' | 'trouble' | 'working' | 'hidden'; cond: string } {
  const o = r.outcome
  if (o === '') return { section: 'working', cond: '' }
  if (o === 'green' || o === 'done' || o === 'dry-run') return { section: 'hidden', cond: '' }
  if (o === 'red' && r.reason === 'quota-paused') return { section: 'needs', cond: 'quota' }
  if (o === 'unverified' || o === 'needs-review') return { section: 'trouble', cond: 'needs review' }
  if (o === 'cancelled') return { section: 'trouble', cond: 'killed' }
  if (r.reason === 'timeout') return { section: 'trouble', cond: 'timed out' }
  if (/gate|check/.test(r.reason)) return { section: 'trouble', cond: 'failed check' }
  return { section: 'trouble', cond: 'died' }
}

const byAge = (a: Entry, b: Entry): number => a.since - b.since || (a.key < b.key ? -1 : 1)

// Collect every row of the session into the four sections. Hidden: finished delegates with no outstanding trouble and
// dismissed episodes. A held row is NEEDS YOU only; once its hold is dismissed it returns to WORKING.
export function buildBoard(m: Mem, now: number): Board {
  const b = emptyBoard()
  const hidden = (key: string) => m.dismissed[key] === true
  for (const a of Object.values(m.agents)) {
    const name = alias(a.type)
    const live = LIVE.has(a.status)
    if (DONE.has(a.status)) continue
    if (a.status === 'failed' || a.status === 'killed') {
      const cond = a.status === 'failed' ? 'died' : 'killed'
      const key = `t:${a.id}:${cond}@${a.since}`
      if (!hidden(key)) b.trouble.push({ key, section: 'trouble', glyph: '▲', alias: name, task: a.description, note: `${cond} ${ago(now - a.since)} ago`, agentId: a.id, since: a.since, actions: ['open', 'dismiss'] })
      continue
    }
    if (!live) continue
    const hold = m.holds[a.id]
    const hkey = hold ? `n:${a.id}@${hold.at}` : ''
    if (hold && !hidden(hkey)) {
      b.needs.push({ key: hkey, section: 'needs', glyph: '!', alias: name, task: a.description, note: `${name} waits: ${hold.question}`, agentId: a.id, since: hold.at, actions: ['open', 'stop', 'dismiss'] })
      continue
    }
    const st = m.steps[a.id]
    const stepOk = a.status === 'running' && st && st.text && now - st.changedAt < QUIET_MS
    const quietSince = Math.max(a.since, st?.changedAt ?? 0)
    const note = a.status === 'waiting' ? 'waiting' : stepOk ? st!.text : quietNote(now - quietSince)
    b.working.push({ key: `w:${a.id}`, section: 'working', glyph: stepOk ? '●' : '◌', alias: name, task: a.description, note, agentId: a.id, since: a.since, actions: ['open', 'stop'] })
  }
  for (const r of Object.values(m.runs)) {
    const name = alias(r.model)
    const c = runCondition(r)
    if (c.section === 'hidden') continue
    if (c.section === 'needs') {
      const key = `n:${r.id}@${r.newest}`
      if (!hidden(key)) {
        const reset = r.resetAt ? `, resets ${hhmm(r.resetAt)}` : ''
        b.needs.push({ key, section: 'needs', glyph: '!', alias: name, task: r.task, note: `${name} paused: quota${reset}`, runId: r.id, since: r.newest, actions: ['dismiss'] })
      }
    } else if (c.section === 'trouble') {
      const key = `t:${r.id}:${c.cond}@${r.newest}`
      if (!hidden(key)) b.trouble.push({ key, section: 'trouble', glyph: '▲', alias: name, task: r.task, note: COND_AGO.has(c.cond) ? `${c.cond} ${ago(now - r.newest)} ago` : c.cond, runId: r.id, since: r.newest, actions: ['dismiss'] })
    } else if (now - r.newest >= LOST_MS) {
      const key = `t:${r.id}:lost@${r.newest}`
      if (!hidden(key)) b.trouble.push({ key, section: 'trouble', glyph: '▲', alias: name, task: r.task, note: `lost, no update ${ago(now - r.newest)}`, runId: r.id, since: r.newest, actions: ['dismiss'] })
    } else {
      const active = now - r.newest < QUIET_MS
      b.working.push({ key: `w:${r.id}`, section: 'working', glyph: active ? '●' : '◌', alias: name, task: r.task, note: active ? 'running' : quietNote(now - r.newest), runId: r.id, since: r.startedAt, actions: [] })
    }
  }
  b.needs.sort(byAge)
  b.trouble.sort(byAge)
  b.working.sort((x, y) => (x.glyph === y.glyph ? byAge(x, y) : x.glyph === '●' ? -1 : 1))
  return b
}

export const selectable = (b: Board): Entry[] => [...b.needs, ...b.fyi, ...b.trouble, ...b.working]
export const isEmpty = (b: Board): boolean => selectable(b).length === 0
