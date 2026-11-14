import type { PaneAgent, PaneDelegate, PaneView } from '../types'

// The delegation tree: pure logic ported from the retired agents-manager mod, the pane's mutable state and the view atom.
// The types below stand in for the additions to types/index.d.ts (spec 040 data-model): TreeRow, treeRows, summary, controlsOpen.
export type TreeRow = { n: number; depth: number; kind: 'agent' | 'run' | 'job'; id: string; label: string; state: string; meta?: string; note?: string }
export type RunLines = Record<string, { lines: string[]; note: string }>
export type Form = { model: string; effort: string; note: string; target: string; targetLabel: string }
export type View = Omit<PaneView, 'types' | 'agents'> & { treeRows: TreeRow[]; summary: string; controlsOpen: boolean }
// A dispatch run's delegate also carries the tree row's meta and the slots path of its run.json.
export type RunDelegate = PaneDelegate & { meta?: string; slots?: string }

export const RUNS = '.scratch/agents-inc-runs'
export const RUN_PANE = 'run-'
export const KEEP_RUNS = 8
export const TREE_CAP = 40
// Run dirs from before the session that the poll still looks at (a run still running stays listed however old it is).
export const PRE_CAP = 40
// A running run with no event for this long (pre-session runs only; session runs go lost after 5 minutes) is stale.
export const STALE_MS = 30 * 60 * 1000
// A finished run leaves the tree this long after its last event: older rows are history, kept on disk, not in the pane.
export const RECENT_MS = 60 * 60 * 1000
export const STOP_TEXT = 'Stop now and report what you have.'
export const STAMP = /^\d{8}T\d{6}Z-/
export const HINT = 'click a row to open it · or pick a target and type a message'

export const EMPTY: View = {
  note: '', delegates: [], acked: {}, alertAt: {}, sessionStart: '', finalRuns: {}, lostRuns: {}, mapNote: '', model: '', seen: {},
  treeRows: [], summary: '', controlsOpen: false,
}

// A value an older code version wrote (no map or tree fields) still renders.
export const normalizeView = (v: Partial<View> | undefined): View => ({ ...EMPTY, ...(v ?? {}) })

// A free-model run (through agent.sh, or since spec 037 through dispatch) takes no cancel and no follow-up message.
export const isFreeRun = (r: { meta?: string }): boolean => / · (agent\.sh|free dispatch)$/.test(String(r.meta ?? ''))

// One start made from this pane. Lives in memory only; keyed by launch stamp.
export type JobKind = 'native' | 'dispatch' | 'free'
export type Job = {
  stamp: string
  kind: JobKind
  model: string
  task: string
  sig: string
  state: 'starting' | 'running' | 'done' | 'failed'
  note: string
  dir: string
  slots: string
  before: Set<string>
}

// Everything the pane remembers between polls and clicks, in one object created per register() and reset at session.start.
export type PaneState = {
  jobs: Map<string, Job>
  // Agents the person asked to stop. The ask is not a stop: the row says "stop requested".
  stopAsked: Set<string>
  // Runs resumed from this pane: their cached final state is read again once (a resume appends to events.jsonl).
  resumed: Set<string>
  // Run dir -> time of its last event, for the "finished more than an hour ago" cut.
  at: Map<string, number>
  // Run dir -> reply lines of a free run (stdout.md or stderr.txt), read once per run and again only while it is failed.
  tails: Map<string, string[]>
  // Agent ids seen at the last poll; a native job is done once an id outside this snapshot appears.
  lastAgents: Set<string>
  // Poll rows (agents and runs) without the job rows; compose() puts the jobs in front and numbers them.
  base: TreeRow[]
  summary: string
  // Run panes the person opened; the poll refreshes only these.
  open: Set<string>
  // Session working directory; resume needs an absolute run dir.
  cwd: string
  // Every subagent of the session, for the map.
  mapSubs: PaneAgent[]
  lastSig: string
}
export const newState = (): PaneState => ({
  jobs: new Map(), stopAsked: new Set(), resumed: new Set(), at: new Map(), tails: new Map(), lastAgents: new Set(), base: [], summary: '',
  open: new Set(), cwd: '.', mapSubs: [], lastSig: '',
})
export function resetState(s: PaneState, cwd: string): void {
  s.jobs.clear()
  s.stopAsked.clear()
  s.resumed.clear()
  s.at.clear()
  s.tails.clear()
  s.lastAgents = new Set()
  s.base = []
  s.summary = ''
  s.open.clear()
  s.cwd = cwd
  s.mapSubs = []
  s.lastSig = ''
}

export const compose = (s: PaneState): TreeRow[] => {
  const jobs: TreeRow[] = [...s.jobs.values()].map(j => ({
    n: 0,
    depth: 1,
    kind: 'job' as const,
    id: j.stamp,
    label: j.task.replace(/\s+/g, ' ').trim(),
    state: j.state,
    meta: `${j.model} · ${j.kind === 'free' ? 'agent.sh' : j.kind}`,
    note: j.note,
  }))
  return [...jobs, ...s.base].map((r, i) => ({ ...r, n: i + 1 }))
}

// Native: a Claude Code subagent (transcript view, SendMessage, stop). Dispatch: an agents-inc run (resume by message).
export type Pick = { value: string; label: string; native?: { subagentType: string; model?: string } }
export const MODELS: Pick[] = [
  { value: 'luna', label: 'luna · OpenAI (native)', native: { subagentType: 'agents-inc:luna' } },
  { value: 'haiku', label: 'haiku · Claude (native)', native: { subagentType: 'general-purpose', model: 'haiku' } },
  { value: 'sonnet', label: 'sonnet · Claude (native)', native: { subagentType: 'general-purpose', model: 'sonnet' } },
  { value: 'opus', label: 'opus · Claude (native)', native: { subagentType: 'general-purpose', model: 'opus' } },
  { value: 'terra', label: 'terra · OpenAI (dispatch)' },
  { value: 'sol', label: 'sol · OpenAI (dispatch)' },
  { value: 'astra', label: 'astra · OpenAI (dispatch)' },
  { value: 'gemini', label: 'gemini · free (agent.sh)' },
  { value: 'mistral', label: 'mistral · free (agent.sh)' },
  { value: 'openrouter', label: 'openrouter · free (agent.sh)' },
]
export const FREE = new Set(['gemini', 'mistral', 'openrouter'])
export const EFFORTS = ['low', 'medium', 'high', 'max'].map(v => ({ value: v, label: v }))

// Row meta for an agent: `<nickname> · <Provider>` for an agents-inc type, the provider read from the MODELS labels; the raw type otherwise.
export function agentMeta(type: string): string {
  if (!type.startsWith('agents-inc:')) return type
  const nick = type.slice('agents-inc:'.length)
  const label = MODELS.find(m => m.value === nick)?.label ?? ''
  const provider = /^[^·]*·\s*([^(]+?)\s*(\(|$)/.exec(label)?.[1]
  return provider ? `${nick} · ${provider}` : nick
}

// A read-only 14-field slots file for a task typed in the pane; the report is the one file it may write.
export const slotsFor = (model: string, task: string, dir: string) => ({
  MODEL: model,
  ROLE: 'Read-only helper started from the agents-inc pane.',
  TASK: task,
  CONSTRAINTS: `Read only. Write only ${dir}/report.md. No network. No git writes.`,
  OUT_OF_SCOPE: `Any file outside ${dir}.`,
  // A string, not a list: dispatch reads a list's brackets as a glob and refuses the run.
  FILES_IN_SCOPE: `${dir}/report.md`,
  STOP_RULE: 'Stop after 20 tool calls or once report.md holds the answer.',
  SUCCESS_GATE: `\`test -s report.md\` in ${dir} exits 0.`,
  FAILURE_GATE: `\`test -s report.md\` in ${dir} exits 1.`,
  GATES: [{ argv: ['test', '-s', 'report.md'], cwd: dir, timeout_s: 30, expect_rc: 0 }],
})

export const clip = (s: string, n: number): string => {
  const one = s.replace(/\s+/g, ' ').trim()
  return one.length > n ? one.slice(0, n - 1) + '…' : one
}

export const runTitle = (name: string): string => name.replace(/^\d{8}T(\d{6})Z-/, '$1 ')

const unwrap = (cmd: string): string => cmd.replace(/^\/bin\/(?:ba|z)?sh -lc\s+/, '').replace(/^['"]|['"]$/g, '')

// One events.jsonl row -> one session-style line, or '' to skip it.
export const describe = (row: any): string => {
  const ev = row?.event
  if (!ev) return ''
  const item = ev.item
  if (ev.type === 'item.started' && item?.type === 'command_execution')
    return '● Bash(' + unwrap(String(item.command ?? '')) + ')'
  if (ev.type === 'item.completed' && item?.type === 'command_execution') {
    const rc = item.exit_code ?? '?'
    return '  ⎿  ' + (rc === 0 ? 'ok' : 'exit ' + String(rc))
  }
  if (ev.type === 'item.completed' && item?.type === 'agent_message') return '● ' + String(item.text ?? '')
  if (ev.type === 'item.completed' && item?.type === 'reasoning') return '✻ Thinking…'
  if (ev.type === 'assistant') {
    for (const c of ev.message?.content ?? []) {
      if (c.type === 'tool_use') {
        const i = c.input ?? {}
        return `● ${c.name}(${String(i.command ?? i.file_path ?? i.pattern ?? i.path ?? i.skill ?? '')})`
      }
      if (c.type === 'text') return '● ' + String(c.text ?? '')
    }
    return '✻ Thinking…'
  }
  if (ev.type === 'result') return `✓ Done · ${ev.usage?.input_tokens ?? 0} in, ${ev.usage?.output_tokens ?? 0} out`
  if (ev.type === 'turn.completed')
    return `✓ Turn done · ${ev.usage?.input_tokens ?? 0} in, ${ev.usage?.output_tokens ?? 0} out`
  if (ev.type === 'run.end') return `✓ Run end · ${ev.outcome} rc=${ev.rc}`
  return ''
}

export const parse = (text: string): any[] =>
  text
    .split('\n')
    .filter(l => l.trim())
    .map(l => {
      try {
        return JSON.parse(l)
      } catch {
        return null
      }
    })
    .filter(Boolean)

// A dispatch run is done once its events.jsonl holds a run.end row.
export const runState = (rows: any[]): string => {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i]?.event?.type === 'run.end') return String(rows[i].event.outcome ?? 'done')
  return rows.length ? 'running' : 'starting'
}

export const color = (s: string): string | undefined =>
  s === 'running' || s === 'waiting' || s === 'resuming' || s === 'starting'
    ? 'yellow'
    : s === 'completed' || s === 'green' || s === 'done' || s === 'idle'
      ? 'green'
      : s === 'failed' || s === 'red' || s === 'killed'
        ? 'red'
        : undefined

// A time as a run-dir stamp; run dirs are named <stamp>-<model>-<id>, so a plain string compare orders them. '' when unparseable.
export const stampOf = (iso: string): string => {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? '' : new Date(t).toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
}
export const isoStamp = (): string => stampOf(new Date().toISOString())

// A free-model start (agent.sh) writes a run-style dir under RUNS: run.json with kind 'free', and
// events.jsonl with one agent_message row per output line and a closing run.end row. No gates, no ledger row.
export const startFreeRun = async (write: (path: string, text: string) => Promise<unknown>, model: string, task: string, slots: string) => {
  const base = `${RUNS}/${isoStamp()}-${model}-free${String(Date.now()).slice(-6)}`
  const rows: string[] = []
  const row = (event: any) => rows.push(JSON.stringify({ event }))
  const flush = () => write(`${base}/events.jsonl`, rows.join('\n') + '\n')
  await write(`${base}/run.json`, JSON.stringify({ model, kind: 'free', slots, task, via: 'agent.sh' }, null, 1))
  row({ type: 'item.completed', item: { type: 'agent_message', text: `agent.sh submit --backend ${model} (no gates, no ledger row)` } })
  await flush()
  let partial = ''
  return {
    out: async (text: string) => {
      const parts = (partial + text).split('\n')
      partial = parts.pop() ?? ''
      for (const l of parts) if (l.trim()) row({ type: 'item.completed', item: { type: 'agent_message', text: l } })
      if (parts.length) await flush()
    },
    end: async (code: number | null) => {
      if (partial.trim()) row({ type: 'item.completed', item: { type: 'agent_message', text: partial } })
      row({ type: 'run.end', outcome: code === 0 ? 'green' : 'red', rc: code })
      await flush()
    },
  }
}

type ListedAgent = { id: string; type?: string; name?: string; description?: string; status?: string; parentId?: string }

// Agent rows of the current agent.list answer, nested under their parent. One row per agent id.
export function agentRows(agents: ListedAgent[]): TreeRow[] {
  const rows: TreeRow[] = []
  const uniq = agents.filter((a, i) => agents.findIndex(x => x.id === a.id) === i)
  const known = new Set(uniq.map(a => a.id))
  const add = (a: ListedAgent, depth: number) => {
    const type = String(a.type ?? '')
    rows.push({
      n: rows.length + 1, depth, kind: 'agent', id: a.id, label: `${a.name ?? type} · ${a.description ?? ''}`,
      state: String(a.status ?? ''), meta: agentMeta(type),
    })
    for (const c of uniq.filter(x => x.parentId === a.id)) add(c, depth + 1)
  }
  for (const a of uniq.filter(x => !x.parentId || !known.has(x.parentId))) add(a, 1)
  return rows
}

const live = (r: TreeRow) => r.state === 'running' || r.state === 'starting'

// Which run rows the tree shows, and the count line. Finished runs from before this session are history, not this
// session's delegates; in a long session a finished run also drops out an hour after its last event. A run still
// running stays listed however old it is; only finished ones are capped (KEEP_RUNS, newest first).
export function treeRuns(runRows: TreeRow[], at: Map<string, number>, since: string, now: number): { shown: TreeRow[]; summary: string } {
  const recent = (r: TreeRow) => {
    const t = at.get(r.id)
    return typeof t !== 'number' || now - t <= RECENT_MS
  }
  const mine = (r: TreeRow) => live(r) || (r.id >= since && recent(r))
  const finishedAll = runRows.filter(r => !live(r) && mine(r)).length
  let kept = 0
  const shown = runRows.filter(r => {
    if (live(r)) return true
    if (!mine(r)) return false
    kept++
    return kept <= KEEP_RUNS
  })
  const summary = runRows.length === 0 ? '' : `${runRows.filter(live).length} running · ${finishedAll} finished (showing ${shown.length})`
  return { shown, summary }
}
