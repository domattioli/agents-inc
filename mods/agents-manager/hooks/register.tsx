import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Form, ManagerView, Row, RunLines } from '../types'

const RUNS = '.scratch/agents-inc-runs'
const PANE = 'agents-manager'
const RUN_PANE = 'run-'
const POLL_MS = 2000
const KEEP_RUNS = 8
const EMPTY: ManagerView = { rows: [], note: 'click a row to open it · or type "<row> <message>"' }

const view = atom({ plugin: 'agents-manager', key: 'view' } as const, EMPTY, { shape: 'view-2' })
const runs = atom({ plugin: 'agents-manager', key: 'runs' } as const, {} as RunLines, { shape: 'runs-1' })
const form = atom({ plugin: 'agents-manager', key: 'form' } as const, { model: 'luna', effort: 'low', note: '' } as Form, { shape: 'form-1' })

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
  { value: 'gemini', label: 'gemini · free (dispatch)' },
  { value: 'mistral', label: 'mistral · free (dispatch)' },
  { value: 'openrouter', label: 'openrouter · free (dispatch)' },
]
const EFFORTS = ['low', 'medium', 'high', 'max'].map(v => ({ value: v, label: v }))

// A read-only 14-field slots file for a task typed in the pane; the report is the one file it may write.
const slotsFor = (model: string, task: string, dir: string) => ({
  MODEL: model,
  ROLE: 'Read-only helper started from the agents-manager pane.',
  TASK: task,
  CONSTRAINTS: `Read only. Write only ${dir}/report.md. No network. No git writes.`,
  OUT_OF_SCOPE: `Any file outside ${dir}.`,
  FILES_IN_SCOPE: [`${dir}/report.md`],
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

// A dispatch run is done once its events.jsonl holds a run.end row.
const runState = (rows: any[]): string => {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i]?.event?.type === 'run.end') return String(rows[i].event.outcome ?? 'done')
  return rows.length ? 'running' : 'starting'
}

const color = (s: string): string | undefined =>
  s === 'running' || s === 'waiting' || s === 'resuming'
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
    await $.command.register({ name: 'agents-manager', description: 'Open the agents manager: a tree of live agents and a message box' })
    void $.ui.open({ id: PANE, title: 'agents-inc manager' })

    $.clock.every(POLL_MS, async () => {
      try {
        const rows: Row[] = []
        const agents = await $.agent.list()
        const known = new Set(agents.map(a => a.id))
        const add = (a: (typeof agents)[number], depth: number) => {
          const meta = a.type === 'agents-inc:luna' ? 'luna · OpenAI' : a.type
          rows.push({ n: rows.length + 1, depth, kind: 'agent', id: a.id, label: `${a.name ?? a.type} · ${a.description}`, state: a.status, meta })
          for (const c of agents.filter(x => x.parentId === a.id)) add(c, depth + 1)
        }
        for (const a of agents.filter(x => !x.parentId || !known.has(x.parentId))) add(a, 1)

        const dirs = (await $.fs.list(RUNS))
          .filter(d => d.kind === 'dir' && /^\d{8}T\d{6}Z-/.test(d.name))
          .map(d => d.name)
          .sort()
          .reverse()
          .slice(0, KEEP_RUNS)
        const fresh: RunLines = {}
        for (const name of dirs) {
          const evs = parse(await $.fs.read(`${RUNS}/${name}/events.jsonl`).catch(() => ''))
          let meta = name.split('-')[1] ?? ''
          try {
            const rj = JSON.parse(await $.fs.read(`${RUNS}/${name}/run.json`))
            meta = `${rj.model ?? meta}${rj.effort ? ' · ' + rj.effort : ''} · dispatch`
          } catch {}
          rows.push({ n: rows.length + 1, depth: 1, kind: 'run', id: name, label: runTitle(name), state: runState(evs), meta })
          if (open.has(name)) fresh[name] = { lines: evs.map(describe).filter(Boolean), note: '' }
        }

        const cur = await read($, view)
        const same = cur.rows.length === rows.length && cur.rows.every((r, i) => r.id === rows[i]?.id && r.state === rows[i]?.state)
        if (!same) await update($, view, v => ({ ...v, rows }))

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
    // Agent row: show its transcript in the main view (Enter then talks to it).
    // Run row: open a pane of its live rows.
    const press = (r: Row) => async () => {
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
        {v.rows.slice(0, rows).map((r, i, all) => {
          // ├─ unless no later row sits at this depth before the tree climbs back out.
          const later = all.slice(i + 1)
          const stop = later.findIndex(x => x.depth < r.depth)
          const last = !(stop < 0 ? later : later.slice(0, stop)).some(x => x.depth === r.depth)
          const indent = '│  '.repeat(r.depth - 1)
          return (
            <Button key={r.kind + r.id} onPress={press(r)}>
              <Text dimColor>{String(r.n).padStart(2) + ' ' + indent + (last ? '└─' : '├─')}</Text>
              <Text color={color(r.state)}>{r.state === 'running' ? '●' : '○'}</Text>
              {' ' + clip(r.label, cols - 34 - r.depth * 3) + ' '}
              <Text color={r.kind === 'run' ? 'magenta' : 'blue'}>{r.meta ?? ''}</Text>
              <Text dimColor>{' ' + r.state}</Text>
            </Button>
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
        <Select
          key="effort"
          label="effort "
          options={EFFORTS}
          value={f.effort}
          onSelect={(value: string) => update($, form, x => ({ ...x, effort: value }))}
        />
        <Input
          key="task"
          label="task "
          placeholder={`what should ${f.model} do?`}
          submitLabel="start"
          onSubmit={async (task: string) => {
            if (!task.trim()) return
            const pick = MODELS.find(m => m.value === f.model) ?? MODELS[0]!
            let note = ''
            try {
              if (pick.native) {
                await $.agent.spawn({ prompt: task, description: clip(task, 40), subagentType: pick.native.subagentType, model: pick.native.model })
                note = `started ${pick.value} (native; effort is the session's)`
              } else {
                const stamp = String(Date.now())
                const dir = `.scratch/pane/${stamp}`
                await $.fs.write(`${dir}/slots.json`, JSON.stringify(slotsFor(pick.value, task, dir), null, 1))
                const child = $.process.spawn({
                  argv: ['agents-inc', 'dispatch', '--slots', `${CWD}/${dir}/slots.json`, '--model', pick.value, '--effort', f.effort],
                })
                void (async () => {
                  for await (const _ of child) {
                  }
                })()
                note = `started ${pick.value} · ${f.effort} via dispatch (report: ${dir}/report.md)`
              }
            } catch (err) {
              note = 'start failed: ' + String((err as Error)?.message ?? err)
            }
            await update($, form, x => ({ ...x, note }))
          }}
        />
        {f.note ? <Text dimColor>{clip(f.note, cols)}</Text> : null}
        <Text> </Text>
        <Text dimColor>{clip(v.note, cols)}</Text>
        <Input
          key="msg"
          label="message "
          placeholder="<row> <message>"
          submitLabel="send"
          onSubmit={async (text: string) => {
            const m = /^\s*(\d+)\s+([\s\S]+)$/.exec(text)
            let note = 'format: <row> <message>'
            const msg = m?.[2] ?? ''
            if (m) {
              const row = v.rows.find(r => r.n === Number(m[1]))
              if (!row) note = `no row ${m[1]}`
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
            }
            await update($, view, x => ({ ...x, note }))
          }}
        />
      </Box>
    )
  })
}
