import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Form, ManagerView, Row, RunLines } from '../types'

const RUNS = '.scratch/agents-inc-runs'
const PANE = 'agents-manager'
const RUN_PANE = 'run-'
const POLL_MS = 2000
const KEEP_RUNS = 8
const STALE_MS = 30 * 60 * 1000
// A finished run leaves the tree this long after its last event: older rows are history, kept on disk, not in the pane.
// A free-model run (through agent.sh, or since spec 037 through dispatch) takes no cancel and no follow-up message.
const isFreeRun = (r: { meta?: string }): boolean => / · (agent\.sh|free dispatch)$/.test(String(r.meta ?? ''))
const RECENT_MS = 60 * 60 * 1000
const AT = new Map<string, number>()
const EMPTY: ManagerView = { rows: [], note: 'click a row to open it · or pick a target and type a message', summary: '' }
const STOP_TEXT = 'Stop now and report what you have.'

const view = atom({ plugin: 'agents-manager', key: 'view' } as const, EMPTY, { shape: 'view-3' })
const runs = atom({ plugin: 'agents-manager', key: 'runs' } as const, {} as RunLines, { shape: 'runs-1' })
const form = atom(
  { plugin: 'agents-manager', key: 'form' } as const,
  { model: 'luna', effort: 'low', note: '', target: '', targetLabel: '' } as Form,
  { shape: 'form-2' },
)

// One start made from this pane. Lives in memory only; keyed by launch stamp.
type JobKind = 'native' | 'dispatch' | 'free'
type Job = {
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
const JOBS = new Map<string, Job>()
// Poll rows (agents and runs) without the job rows; compose() puts the jobs in front and numbers them.
let BASE: Row[] = []
let SUMMARY = ''
// Agent ids seen at the last poll; a native job is done once an id outside this snapshot appears.
let LAST_AGENTS = new Set<string>()
// Agents the person asked to stop. The ask is not a stop: the row says "stop requested".
const STOP_ASKED = new Set<string>()
// Finished run rows by dir name. A resume appends to events.jsonl, so resuming a run drops it from here.
const DONE = new Map<string, { row: Row | null; slots: string; size: number }>()

const compose = (): Row[] => {
  const jobs: Row[] = [...JOBS.values()].map(j => ({
    n: 0,
    depth: 1,
    kind: 'job' as const,
    id: j.stamp,
    label: j.task.replace(/\s+/g, ' ').trim(),
    state: j.state,
    meta: `${j.model} · ${j.kind === 'free' ? 'agent.sh' : j.kind}`,
    note: j.note,
  }))
  return [...jobs, ...BASE].map((r, i) => ({ ...r, n: i + 1 }))
}

// Row meta for an agent: `<nickname> · <Provider>` for an agents-inc type, the provider read from the MODELS labels; the raw type otherwise.
function agentMeta(type: string): string {
  if (!type.startsWith('agents-inc:')) return type
  const nick = type.slice('agents-inc:'.length)
  const label = MODELS.find(m => m.value === nick)?.label ?? ''
  const provider = /^[^·]*·\s*([^(]+?)\s*(\(|$)/.exec(label)?.[1]
  return provider ? `${nick} · ${provider}` : nick
}

// Native: a Claude Code subagent (transcript view, SendMessage, stop). Dispatch: an agents-inc run (resume by message).
type Pick = { value: string; label: string; native?: { subagentType: string; model?: string } }
const MODELS: Pick[] = [
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
const FREE = new Set(['gemini', 'mistral', 'openrouter'])
const EFFORTS = ['low', 'medium', 'high', 'max'].map(v => ({ value: v, label: v }))

// A read-only 14-field slots file for a task typed in the pane; the report is the one file it may write.
const slotsFor = (model: string, task: string, dir: string) => ({
  MODEL: model,
  ROLE: 'Read-only helper started from the agents-manager pane.',
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

// Run panes the person opened; the poll refreshes only these.
const open = new Set<string>()
// Session working directory, set at session.start; resume needs an absolute run dir.
let CWD = '.'

const clip = (s: string, n: number): string => {
  const one = s.replace(/\s+/g, ' ').trim()
  return one.length > n ? one.slice(0, n - 1) + '…' : one
}

const unwrap = (cmd: string): string => cmd.replace(/^\/bin\/(?:ba|z)?sh -lc\s+/, '').replace(/^['"]|['"]$/g, '')

// One events.jsonl row -> one session-style line, or '' to skip it.
const describe = (row: any): string => {
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

const parse = (text: string): any[] =>
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

// A free-model start (agent.sh) writes a run-style dir under RUNS: run.json with kind 'free', and
// events.jsonl with one agent_message row per output line and a closing run.end row. No gates, no ledger row.
// Session start as a run-dir stamp; run dirs are named <stamp>-<model>-<id>, so a plain string compare orders them.
let SINCE = ''
const isoStamp = (): string => new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
const startFreeRun = async (write: (path: string, text: string) => Promise<unknown>, model: string, task: string, slots: string) => {
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

// A dispatch run is done once its events.jsonl holds a run.end row.
const runState = (rows: any[]): string => {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i]?.event?.type === 'run.end') return String(rows[i].event.outcome ?? 'done')
  return rows.length ? 'running' : 'starting'
}

const color = (s: string): string | undefined =>
  s === 'running' || s === 'waiting' || s === 'resuming' || s === 'starting'
    ? 'yellow'
    : s === 'completed' || s === 'green' || s === 'done' || s === 'idle'
      ? 'green'
      : s === 'failed' || s === 'red' || s === 'killed'
        ? 'red'
        : undefined

export const register: Register = on => {
  // Resume a dispatch run with a message: `agents-inc dispatch --resume <dir> --message <m>`.
  // The child runs in the background; its new rows land in events.jsonl and the poll shows them.
  // The caller passes closures over its own `$`, so this helper never holds `$` itself.
  const resume = (
    spawn: (argv: string[]) => AsyncIterable<{ text: string }> & { result: Promise<{ code?: number | null }> },
    done: (note: string) => Promise<unknown>,
    name: string,
    message: string,
  ) => {
    DONE.delete(name)
    void (async () => {
      const child = spawn(['agents-inc', 'dispatch', '--resume', `${CWD}/${RUNS}/${name}`, '--message', message])
      let tail = ''
      for await (const piece of child) tail = (tail + piece.text).slice(-400)
      const end = await child.result
      await done(end?.code === 0 ? 'resume finished' : 'resume failed: ' + clip(tail, 120))
    })()
  }
  const runTitle = (name: string): string => name.replace(/^\d{8}T(\d{6})Z-/, '$1 ')

  on('session.start', async ($, e, next) => {
    CWD = e.cwd
    JOBS.clear()
    BASE = []
    SUMMARY = ''
    LAST_AGENTS = new Set()
    STOP_ASKED.clear()
    DONE.clear()
    SINCE = isoStamp()
    await $.command.register({ name: 'agents-manager', description: 'Open the agents manager: a tree of live agents and a message box' })
    void $.ui.open({ id: PANE, title: 'agents-inc manager' })

    $.clock.every(POLL_MS, async () => {
      try {
        const rows: Row[] = []
        const agents = await $.agent.list()
        const known = new Set(agents.map(a => a.id))
        const add = (a: (typeof agents)[number], depth: number) => {
          const meta = agentMeta(a.type)
          rows.push({ n: rows.length + 1, depth, kind: 'agent', id: a.id, label: `${a.name ?? a.type} · ${a.description}`, state: a.status, meta })
          for (const c of agents.filter(x => x.parentId === a.id)) add(c, depth + 1)
        }
        for (const a of agents.filter(x => !x.parentId || !known.has(x.parentId))) add(a, 1)

        // Every run dir is read: a running run stays listed however old it is; only finished ones are capped.
        const listed = (await $.fs.list(RUNS).catch(() => [])).filter(d => d.kind === 'dir' && /^\d{8}T\d{6}Z-/.test(d.name))
        const dirAge = new Map(listed.map(d => [d.name, d.mtimeMs] as const))
        const dirs = listed
          .map(d => d.name)
          .sort()
          .reverse()
        const fresh: RunLines = {}
        const runRows: Row[] = []
        const slotsSeen: string[] = []
        for (const name of dirs) {
          // A finished run is reused while its events.jsonl size is unchanged; a resume from anywhere grows it.
          // No size known (listing failed or lacks the file): never cache.
          const ev = (await $.fs.list(`${RUNS}/${name}`).catch(() => [])).find(x => x.name === 'events.jsonl')
          const size = typeof ev?.size === 'number' ? ev.size : -1
          if (typeof ev?.mtimeMs === 'number') AT.set(name, ev.mtimeMs)
          else if (typeof dirAge.get(name) === 'number') AT.set(name, dirAge.get(name) as number)
          const hit = DONE.get(name)
          if (hit && size >= 0 && hit.size === size && !open.has(name)) {
            if (hit.row) runRows.push(hit.row)
            if (hit.slots) slotsSeen.push(hit.slots)
            continue
          }
          const evs = parse(await $.fs.read(`${RUNS}/${name}/events.jsonl`).catch(() => ''))
          let meta = name.split('-')[1] ?? ''
          let slots = ''
          try {
            const rj = JSON.parse(await $.fs.read(`${RUNS}/${name}/run.json`))
            meta = `${rj.model ?? meta}${rj.effort ? ' · ' + rj.effort : ''} · ${rj.kind === 'free' ? (rj.via === 'agent.sh' ? 'agent.sh' : 'free dispatch') : 'dispatch'}`
            if (typeof rj.slots === 'string') slotsSeen.push((slots = rj.slots))
          } catch {}
          // A run with no run.end whose log has not moved in 30 min died without closing: call it stale, not running.
          let state = runState(evs)
          // No events.jsonl (refused or dry-run dispatch): judge by the run dir's own time instead.
          const moved = typeof ev?.mtimeMs === 'number' ? ev.mtimeMs : dirAge.get(name)
          if ((state === 'running' || state === 'starting') && typeof moved === 'number' && Date.now() - moved > STALE_MS) state = 'stale'
          // A dry-run dispatch ran no agent: keep it out of the tree and the counts.
          if (state === 'dry-run') {
            if (size >= 0) DONE.set(name, { row: null, slots, size })
            continue
          }
          const row: Row = { n: 0, depth: 1, kind: 'run', id: name, label: runTitle(name), state, meta }
          runRows.push(row)
          if (size >= 0 && row.state !== 'running' && row.state !== 'starting') DONE.set(name, { row, slots, size })
          else DONE.delete(name)
          if (open.has(name)) {
            const lines = evs.map(describe).filter(Boolean)
            // A free-model run logs only run.start and run.end: its reply is stdout.md (stderr.txt when it failed).
            if (isFreeRun(row)) {
              const reply = await $.fs.read(`${RUNS}/${name}/stdout.md`).catch(() => '')
              const text = reply.trim() ? reply : await $.fs.read(`${RUNS}/${name}/stderr.txt`).catch(() => '')
              const body = text.split('\n').filter(l => l.trim())
              if (body.length) lines.splice(Math.max(0, lines.length - 1), 0, '● ' + body[0], ...body.slice(1).map(l => '  ' + l))
            }
            fresh[name] = { lines, note: '' }
          }
        }
        const live = (r: Row) => r.state === 'running' || r.state === 'starting'
        const active = runRows.filter(live).length
        // Finished runs from before this session are history, not this session's delegates: they used to fill the tree with
        // eight old rows in every session. In a long session a finished run also drops out an hour after its last event.
        // A run still running stays listed however old it is.
        const recent = (r: Row) => { const at = AT.get(r.id); return typeof at !== 'number' || Date.now() - at <= RECENT_MS }
        const mine = (r: Row) => live(r) || (r.id >= SINCE && recent(r))
        const finishedAll = runRows.filter(r => !live(r) && mine(r)).length
        let keptFinished = 0
        const shown = runRows.filter(r => {
          if (live(r)) return true
          if (!mine(r)) return false
          keptFinished++
          return keptFinished <= KEEP_RUNS
        })
        const summary = runRows.length === 0 ? '' : `${active} running · ${finishedAll} finished (showing ${shown.length})`
        rows.push(...shown)

        // A job row ends once the real thing appears in the lists: a new agent (native) or a run dir with its slots path (dispatch).
        const claimed = new Set<string>()
        for (const j of [...JOBS.values()]) {
          if (j.kind === 'native' && j.state !== 'failed') {
            const fresh1 = agents.find(a => !j.before.has(a.id) && !claimed.has(a.id))
            if (fresh1) {
              claimed.add(fresh1.id)
              JOBS.delete(j.stamp)
            }
          } else if (j.kind !== 'native' && slotsSeen.some(s => s.includes(`/${j.stamp}/`))) JOBS.delete(j.stamp)
        }
        LAST_AGENTS = new Set(agents.map(a => a.id))
        BASE = rows
        SUMMARY = summary
        const all = compose()

        const cur = await read($, view)
        const same =
          cur.summary === summary &&
          cur.rows.length === all.length &&
          cur.rows.every((r, i) => r.id === all[i]?.id && r.kind === all[i]?.kind && r.state === all[i]?.state && r.note === all[i]?.note)
        const stale = cur.note.startsWith('poll error: ')
        if (!same || stale) await update($, view, v => ({ ...v, rows: all, summary, note: v.note.startsWith('poll error: ') ? EMPTY.note : v.note }))

        if (Object.keys(fresh).length) {
          const had = await read($, runs)
          const changed = Object.keys(fresh).some(k => had[k]?.lines.length !== fresh[k]!.lines.length)
          if (changed) await update($, runs, r => {
            const out = { ...r }
            for (const k of Object.keys(fresh)) out[k] = { lines: fresh[k]!.lines, note: r[k]?.note ?? '' }
            return out
          })
        }
      } catch (err) {
        await update($, view, v => ({ ...v, note: 'poll error: ' + String((err as Error)?.message ?? err) }))
      }
    })
    return next(e)
  })

  // Run panes: session-style rows of one dispatch run, with a box that resumes it.
  on('ui.render', { component: 'Pane' }, async ($, re, nextRender) => {
      const id = String((re as any).requestId ?? '')
      if (!id.startsWith(RUN_PANE)) return nextRender(re)
      const name = id.slice(RUN_PANE.length)
      open.add(name)
      const { Box, Text, Input } = $.ui.resolve(re)
      const r = (await read($, runs))[name] ?? { lines: [], note: '' }
      const cols = Math.max(20, (re.viewport?.columns ?? 60) - 2)
      const height = Math.max(3, (re.viewport?.rows ?? 24) - 6)
      return (
        <Box flexDirection="column">
          <Text dimColor>{clip(name, cols)}</Text>
          <Text> </Text>
          {r.lines.length === 0 ? <Text dimColor>loading…</Text> : null}
          {r.lines.slice(-height).map(l =>
            l.startsWith('●') ? (
              <Text>
                <Text color="green">●</Text>
                {clip(l.slice(1), cols - 2)}
              </Text>
            ) : (
              <Text color={l.startsWith('✓') ? 'green' : undefined} dimColor={!l.startsWith('✓')}>
                {clip(l, cols)}
              </Text>
            ),
          )}
          {r.note ? <Text dimColor>{clip(r.note, cols)}</Text> : null}
          <Input
            key="resume"
            label="› "
            placeholder="message to resume this run"
            submitLabel="send"
            onSubmit={async (text: string) => {
              if (!text.trim()) return
              resume(
                argv => $.process.spawn({ argv }),
                note => update($, runs, x => ({ ...x, [name]: { lines: x[name]?.lines ?? [], note } })),
                name,
                text,
              )
              await update($, runs, x => ({ ...x, [name]: { lines: x[name]?.lines ?? [], note: 'resuming…' } }))
            }}
          />
        </Box>
      )
  })

  on('command.run', { command: 'agents-manager' }, async $ => {
    await $.ui.open({ id: PANE, title: 'agents-inc manager' })
    return { text: 'agents manager opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Input, Button, Select } = $.ui.resolve(e)
    const v = await read($, view)
    const f = await read($, form)
    const cols = Math.max(20, (e.viewport?.columns ?? 60) - 2)
    const rows = Math.max(3, (e.viewport?.rows ?? 24) - 8)
    const pick = MODELS.find(m => m.value === f.model) ?? MODELS[0]!
    const free = FREE.has(pick.value)
    // Message targets: agent and run rows only, by kind:id so a poll never moves the choice.
    const targets = v.rows.filter(r => r.kind !== 'job')
    const key = (r: Row) => `${r.kind}:${r.id}`
    const tlabel = (r: Row) => clip(`${r.n} ${r.label}`, 44)
    const first = targets[0]
    const cur = f.target || (first ? key(first) : '')
    // A Select takes 1 to 64 options: keep 63 rows, leaving room for the "gone" entry.
    const topts = targets.slice(0, 63).map(r => ({ value: key(r), label: tlabel(r) }))
    if (cur && !topts.some(o => o.value === cur)) topts.unshift({ value: cur, label: 'gone: ' + (f.targetLabel || cur) })
    // Agent row: show its transcript in the main view (Enter then talks to it).
    // Run row: open a pane of its live rows. Job row: nothing to open.
    const press = (r: Row) => async () => {
      if (r.kind === 'job') return
      if (r.kind === 'agent') {
        const res = await $.ui.view({ agentId: r.id })
        if ((res as any)?.deny) await update($, view, x => ({ ...x, note: 'cannot view: ' + (res as any).deny }))
      } else {
        open.add(r.id)
        await $.ui.open({ id: RUN_PANE + r.id, title: runTitle(r.id) })
      }
    }
    return (
      <Box flexDirection="column">
        <Text bold>who delegates to whom</Text>
        <Button key="main" onPress={() => $.ui.view({})}>
          <Text color="cyan">◆</Text>
          {' main session '}
          <Text dimColor>(you · click to return here)</Text>
        </Button>
        {v.summary ? <Text dimColor>{clip(v.summary, cols)}</Text> : null}
        {v.rows.slice(0, rows).map((r, i, all) => {
          // ├─ unless no later row sits at this depth before the tree climbs back out.
          const later = all.slice(i + 1)
          const stop = later.findIndex(x => x.depth < r.depth)
          const last = !(stop < 0 ? later : later.slice(0, stop)).some(x => x.depth === r.depth)
          const indent = '│  '.repeat(r.depth - 1)
          const asked = r.kind === 'agent' && STOP_ASKED.has(r.id)
          return (
            <Box key={r.kind + r.id} flexDirection="column">
              <Button key={'row-' + r.kind + r.id} onPress={press(r)}>
                <Text dimColor>{String(r.n).padStart(2) + ' ' + indent + (last ? '└─' : '├─')}</Text>
                <Text color={color(r.state)}>{r.state === 'running' || r.state === 'starting' ? '●' : '○'}</Text>
                {' ' + clip(r.label, cols - 34 - r.depth * 3) + ' '}
                <Text color={r.kind === 'agent' ? 'blue' : 'magenta'}>{r.meta ?? ''}</Text>
                <Text dimColor>{' ' + (asked ? 'stop requested' : r.state)}</Text>
              </Button>
              {r.kind === 'job' && r.note ? <Text dimColor>{clip('      ' + r.note, cols)}</Text> : null}
              {r.kind === 'run' && r.state === 'running' && !isFreeRun(r) ? (
                <Button
                  key={'cancel-' + r.id}
                  onPress={async () => {
                    let note: string
                    try {
                      const child = $.process.spawn({ argv: ['agents-inc', 'dispatch', '--cancel', `${CWD}/${RUNS}/${r.id}`] })
                      let tail = ''
                      for await (const piece of child as AsyncIterable<{ text: string }>) tail = (tail + piece.text).slice(-400)
                      const end = await (child as any).result
                      note = end?.code === 0 ? `cancel sent: ${r.label}` : `cancel failed (exit ${end?.code ?? '?'}): ${clip(tail, 100)}`
                    } catch (err) {
                      note = 'cancel failed: ' + String((err as Error)?.message ?? err)
                    }
                    await update($, view, x => ({ ...x, note }))
                  }}
                >
                  <Text color="red">{'      cancel'}</Text>
                </Button>
              ) : null}
              {r.kind === 'agent' && r.state === 'running' && !asked ? (
                <Button
                  key={'stop-' + r.id}
                  onPress={async () => {
                    let note: string
                    try {
                      await $.session.send({ to: { agentId: r.id }, text: STOP_TEXT })
                      STOP_ASKED.add(r.id)
                      note = `stop requested: ${r.label}`
                    } catch (err) {
                      note = 'stop request failed: ' + String((err as Error)?.message ?? err)
                    }
                    await update($, view, x => ({ ...x, note }))
                  }}
                >
                  <Text color="yellow">{'      ask to stop'}</Text>
                </Button>
              ) : null}
            </Box>
          )
        })}
        {v.rows.length === 0 ? <Text dimColor>   └─ no delegates yet</Text> : null}
        <Text> </Text>
        <Text bold>new agent</Text>
        <Select
          key="model"
          label="model "
          options={MODELS.map(m => ({ value: m.value, label: m.label }))}
          value={f.model}
          onSelect={(value: string) => update($, form, x => ({ ...x, model: value }))}
        />
        {pick.native || free ? (
          <Text dimColor>{pick.native ? "effort: session's" : 'effort: backend default'}</Text>
        ) : (
          <Select
            key="effort"
            label="effort "
            options={EFFORTS}
            value={f.effort}
            onSelect={(value: string) => update($, form, x => ({ ...x, effort: value }))}
          />
        )}
        {pick.native || free ? null : <Text dimColor>read-only · writes only report.md</Text>}
        <Input
          key="task"
          label="task "
          placeholder={`what should ${f.model} do?`}
          submitLabel="start"
          onSubmit={async (task: string) => {
            if (!task.trim()) return
            // One row per start: a second start of the same model+task is ignored while the first is still starting.
            const sig = pick.value + '\u0000' + task.trim()
            if ([...JOBS.values()].some(j => j.state === 'starting' && j.sig === sig)) return
            let stamp = String(Date.now())
            while (JOBS.has(stamp)) stamp = String(Number(stamp) + 1)
            const dir = `.scratch/pane/${stamp}`
            const kind: JobKind = pick.native ? 'native' : free ? 'free' : 'dispatch'
            const job: Job = {
              stamp,
              kind,
              model: pick.value,
              task,
              sig,
              state: 'starting',
              note: '',
              dir,
              slots: kind === 'dispatch' ? `${CWD}/${dir}/slots.json` : '',
              before: new Set(LAST_AGENTS),
            }
            JOBS.set(stamp, job)
            const show = () => update($, view, x => ({ ...x, rows: compose(), summary: SUMMARY }))
            await show()
            try {
              if (pick.native) {
                await $.agent.spawn({ prompt: task, description: clip(task, 40), subagentType: pick.native.subagentType, model: pick.native.model })
                job.state = 'running'
                job.note = "native; effort is the session's"
              } else {
                // Free models are not dispatch kinds; they run through the governed agent.sh leg.
                if (!free) await $.fs.write(`${dir}/slots.json`, JSON.stringify(slotsFor(pick.value, task, dir), null, 1))
                const argv = free
                  ? [`${CWD}/skills/codex-bridge/scripts/agent.sh`, 'submit', '--backend', pick.value, '--wait', task]
                  : ['agents-inc', 'dispatch', '--slots', job.slots, '--model', pick.value, '--effort', f.effort]
                // A free start also gets a run-style dir, so it lists and opens like a dispatch run.
                if (free) await $.fs.write(`${dir}/task.txt`, task)
                const freeRun = free ? await startFreeRun((path, text) => $.fs.write(path, text), pick.value, task, `${CWD}/${dir}/task.txt`) : null
                const child = $.process.spawn({ argv })
                job.state = 'running'
                job.note = `report: ${dir}/report.md`
                // Drain in the background; the exit code and last output line land on this job's row.
                void (async () => {
                  let tail = ''
                  for await (const piece of child as AsyncIterable<{ text: string }>) {
                    tail = (tail + piece.text).slice(-4000)
                    if (freeRun) await freeRun.out(piece.text)
                  }
                  const end = await (child as any).result
                  const code = end?.code ?? null
                  if (free) await $.fs.write(`${dir}/report.md`, tail)
                  if (freeRun) await freeRun.end(code)
                  job.state = code === 0 ? 'done' : 'failed'
                  job.note = `exit ${code}: ${tail.trim().split('\n').pop() ?? ''}`
                  await show()
                })()
              }
            } catch (err) {
              job.state = 'failed'
              job.note = 'start failed: ' + String((err as Error)?.message ?? err)
            }
            await show()
          }}
        />
        {f.note ? <Text dimColor>{clip(f.note, cols)}</Text> : null}
        <Text> </Text>
        <Text dimColor>{clip(v.note, cols)}</Text>
        {topts.length ? (
          <Select
            key="target"
            label="to "
            options={topts}
            value={cur}
            onSelect={(value: string) =>
              update($, form, x => ({ ...x, target: value, targetLabel: topts.find(o => o.value === value)?.label ?? value }))
            }
          />
        ) : (
          <Text dimColor>no target yet</Text>
        )}
        <Input
          key="msg"
          label="message "
          placeholder="message to the selected target"
          submitLabel="send"
          onSubmit={async (text: string) => {
            const msg = text.trim()
            if (!msg) return
            // Re-read the rows: the target is found by kind:id in the current list, never by position.
            const now = await read($, view)
            const row = now.rows.find(r => r.kind !== 'job' && key(r) === cur)
            let note: string
            if (!cur) note = 'no target'
            else if (!row) note = `target gone: ${f.targetLabel || cur}`
            else if (row.kind === 'run' && isFreeRun(row)) note = 'free-model runs take no messages; start a new one'
            else if (row.kind === 'run') {
              resume(
                argv => $.process.spawn({ argv }),
                n => update($, runs, x => ({ ...x, [row.id]: { lines: x[row.id]?.lines ?? [], note: n } })),
                row.id,
                msg,
              )
              open.add(row.id)
              await $.ui.open({ id: RUN_PANE + row.id, title: runTitle(row.id) })
              note = `resuming row ${row.n}`
            } else {
              try {
                await $.session.send({ to: { agentId: row.id }, text: msg })
                note = `sent to row ${row.n}`
              } catch (err) {
                note = 'send failed: ' + String((err as Error)?.message ?? err)
              }
            }
            await update($, view, x => ({ ...x, note }))
          }}
        />
      </Box>
    )
  })
}
