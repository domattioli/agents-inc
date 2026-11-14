import { atom, read, update } from 'claude-code'

import { EFFORTS, FREE, HINT, MODELS, RUN_PANE, RUNS, STOP_TEXT, TREE_CAP, clip, color, compose, isFreeRun, normalizeView, runTitle, slotsFor, startFreeRun, EMPTY } from './tree'
import type { Form, Job, JobKind, PaneState, RunLines, TreeRow, View } from './tree'

// Panes narrower than this fold the new-agent form and the message box behind one Button line (spec 040 R4).
// The map's own thresholds live in mission.ts `layoutFor`; this one is the pane's, and the Raster map starts at the same width.
// view-5: acks became `<id>@<alertAt>` keys; a view-4 value (plain-id acks) reads as EMPTY and the store record refills it.
// The state scan wants the atom spelled in each file that reads it, so controls.tsx and register.tsx both declare it.
const view = atom({ plugin: 'delegate-pane', key: 'view' } as const, EMPTY as any, { shape: 'view-5' })

export const NARROW_COLS = 34

const runs = atom({ plugin: 'delegate-pane', key: 'runs' } as const, {} as RunLines, { shape: 'runs-1' })
const form = atom(
  { plugin: 'delegate-pane', key: 'form' } as const,
  { model: 'luna', effort: 'low', note: '', target: '', targetLabel: '' } as Form,
  { shape: 'form-2' },
)

// Resume a dispatch run with a message: `agents-inc dispatch --resume <dir> --message <m>`.
// The child runs in the background; its new rows land in events.jsonl and the poll shows them.
// The caller passes closures over its own `$`, so this helper never holds `$` itself.
export const resumeRun = (
  st: PaneState,
  spawn: (argv: string[]) => AsyncIterable<{ text: string }> & { result: Promise<{ code?: number | null }> },
  done: (note: string) => Promise<unknown>,
  name: string,
  message: string,
): void => {
  // A resume appends to events.jsonl: read the run again once and its reply tail again.
  st.resumed.add(name)
  st.tails.delete(name)
  void (async () => {
    const child = spawn(['agents-inc', 'dispatch', '--resume', `${st.cwd}/${RUNS}/${name}`, '--message', message])
    let tail = ''
    for await (const piece of child) tail = (tail + piece.text).slice(-400)
    const end = await child.result
    await done(end?.code === 0 ? 'resume finished' : 'resume failed: ' + clip(tail, 120))
  })()
}

// Write the poll's lines of the open run panes into the runs atom; a no-op when no line count moved.
export async function applyRunLines($: any, fresh: Record<string, string[]>): Promise<void> {
  const names = Object.keys(fresh)
  if (!names.length) return
  const had = await read($, runs)
  if (!names.some(k => had[k]?.lines.length !== fresh[k]!.length)) return
  await update($, runs, r => {
    const out = { ...r }
    for (const k of names) out[k] = { lines: fresh[k]!, note: r[k]?.note ?? '' }
    return out
  })
}

// Run panes: session-style rows of one dispatch run, with a box that resumes it.
export async function renderRun($: any, re: any, st: PaneState, name: string) {
  st.open.add(name)
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
          resumeRun(
            st,
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
}

// The tree of delegates, the new-agent form and the message box (spec 040 Design 2-5). A pane narrower than
// NARROW_COLS keeps the tree and folds the form and the message box behind one Button line.
export async function controlsView($: any, els: any, st: PaneState, v: View, columns: number) {
  const { Box, Text, Input, Button, Select } = els
  const f = await read($, form)
  const cols = Math.max(20, columns - 2)
  const pick = MODELS.find(m => m.value === f.model) ?? MODELS[0]!
  const free = FREE.has(pick.value)
  const note = (n: string) => update($, view, (x: any) => ({ ...normalizeView(x), note: n }))
  // Message targets: agent and run rows only, by kind:id so a poll never moves the choice.
  const targets = v.treeRows.filter(r => r.kind !== 'job')
  const key = (r: TreeRow) => `${r.kind}:${r.id}`
  const tlabel = (r: TreeRow) => clip(`${r.n} ${r.label}`, 44)
  const first = targets[0]
  const cur = f.target || (first ? key(first) : '')
  // A Select takes 1 to 64 options: keep 63 rows, leaving room for the "gone" entry.
  const topts = targets.slice(0, 63).map(r => ({ value: key(r), label: tlabel(r) }))
  if (cur && !topts.some(o => o.value === cur)) topts.unshift({ value: cur, label: 'gone: ' + (f.targetLabel || cur) })
  // Agent row: show its transcript in the main view (Enter then talks to it).
  // Run row: open a pane of its live rows. Job row: nothing to open.
  const press = (r: TreeRow) => async () => {
    if (r.kind === 'job') return
    if (r.kind === 'agent') {
      const res = await $.ui.view({ agentId: r.id })
      if ((res as any)?.deny) await note('cannot view: ' + (res as any).deny)
    } else {
      st.open.add(r.id)
      await $.ui.open({ id: RUN_PANE + r.id, title: runTitle(r.id) })
    }
  }
  const show = () => update($, view, (x: any) => ({ ...normalizeView(x), treeRows: compose(st), summary: st.summary }))
  const start = async (task: string) => {
    if (!task.trim()) return
    // One row per start: a second start of the same model+task is ignored while the first is still starting.
    const sig = pick.value + '\u0000' + task.trim()
    if ([...st.jobs.values()].some(j => j.state === 'starting' && j.sig === sig)) return
    let stamp = String(Date.now())
    while (st.jobs.has(stamp)) stamp = String(Number(stamp) + 1)
    const dir = `.scratch/pane/${stamp}`
    const kind: JobKind = pick.native ? 'native' : free ? 'free' : 'dispatch'
    const job: Job = {
      stamp, kind, model: pick.value, task, sig, state: 'starting', note: '', dir,
      slots: kind === 'dispatch' ? `${st.cwd}/${dir}/slots.json` : '',
      before: new Set(st.lastAgents),
    }
    st.jobs.set(stamp, job)
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
          ? [`${st.cwd}/skills/codex-bridge/scripts/agent.sh`, 'submit', '--backend', pick.value, '--wait', task]
          : ['agents-inc', 'dispatch', '--slots', job.slots, '--model', pick.value, '--effort', f.effort]
        // A free start also gets a run-style dir, so it lists and opens like a dispatch run.
        if (free) await $.fs.write(`${dir}/task.txt`, task)
        const freeRun = free ? await startFreeRun((path, text) => $.fs.write(path, text), pick.value, task, `${st.cwd}/${dir}/task.txt`) : null
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
  }
  const send = async (text: string) => {
    const msg = text.trim()
    if (!msg) return
    // Re-read the rows: the target is found by kind:id in the current list, never by position.
    const now = normalizeView(await read($, view))
    const row = now.treeRows.find(r => r.kind !== 'job' && key(r) === cur)
    let out: string
    if (!cur) out = 'no target'
    else if (!row) out = `target gone: ${f.targetLabel || cur}`
    else if (row.kind === 'run' && isFreeRun(row)) out = 'this run takes no messages'
    else if (row.kind === 'run') {
      resumeRun(
        st,
        argv => $.process.spawn({ argv }),
        n => update($, runs, x => ({ ...x, [row.id]: { lines: x[row.id]?.lines ?? [], note: n } })),
        row.id,
        msg,
      )
      st.open.add(row.id)
      await $.ui.open({ id: RUN_PANE + row.id, title: runTitle(row.id) })
      out = `resuming row ${row.n}`
    } else {
      try {
        await $.session.send({ to: { agentId: row.id }, text: msg })
        out = `sent to row ${row.n}`
      } catch (err) {
        out = 'send failed: ' + String((err as Error)?.message ?? err)
      }
    }
    await note(out)
  }
  const narrow = columns < NARROW_COLS
  const unfolded = !narrow || v.controlsOpen
  return (
    <Box flexDirection="column">
      <Text bold>who delegates to whom</Text>
      <Button key="main" onPress={() => $.ui.view({})}>
        <Text color="cyan">◆</Text>
        {' main session '}
        <Text dimColor>(you · click to return here)</Text>
      </Button>
      {v.summary ? <Text dimColor>{clip(v.summary, cols)}</Text> : null}
      {v.treeRows.slice(0, TREE_CAP).map((r, i, all) => {
        // ├─ unless no later row sits at this depth before the tree climbs back out.
        const later = all.slice(i + 1)
        const stop = later.findIndex(x => x.depth < r.depth)
        const last = !(stop < 0 ? later : later.slice(0, stop)).some(x => x.depth === r.depth)
        const indent = '│  '.repeat(r.depth - 1)
        const asked = r.kind === 'agent' && st.stopAsked.has(r.id)
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
                  let out: string
                  try {
                    const child = $.process.spawn({ argv: ['agents-inc', 'dispatch', '--cancel', `${st.cwd}/${RUNS}/${r.id}`] })
                    let tail = ''
                    for await (const piece of child as AsyncIterable<{ text: string }>) tail = (tail + piece.text).slice(-400)
                    const end = await (child as any).result
                    out = end?.code === 0 ? `cancel sent: ${r.label}` : `cancel failed (exit ${end?.code ?? '?'}): ${clip(tail, 100)}`
                  } catch (err) {
                    out = 'cancel failed: ' + String((err as Error)?.message ?? err)
                  }
                  await note(out)
                }}
              >
                <Text color="red">{'      cancel'}</Text>
              </Button>
            ) : null}
            {r.kind === 'agent' && r.state === 'running' && !asked ? (
              <Button
                key={'stop-' + r.id}
                onPress={async () => {
                  let out: string
                  try {
                    await $.session.send({ to: { agentId: r.id }, text: STOP_TEXT })
                    st.stopAsked.add(r.id)
                    out = `stop requested: ${r.label}`
                  } catch (err) {
                    out = 'stop request failed: ' + String((err as Error)?.message ?? err)
                  }
                  await note(out)
                }}
              >
                <Text color="yellow">{'      ask to stop'}</Text>
              </Button>
            ) : null}
          </Box>
        )
      })}
      {v.treeRows.length === 0 ? <Text dimColor>   └─ no delegates yet</Text> : null}
      <Text> </Text>
      {narrow ? (
        <Button key="controls" onPress={() => update($, view, (x: any) => ({ ...normalizeView(x), controlsOpen: !normalizeView(x).controlsOpen }))}>
          <Text bold>{(unfolded ? '▾' : '▸') + ' new agent / message'}</Text>
        </Button>
      ) : (
        <Text bold>new agent</Text>
      )}
      {unfolded ? (
        <>
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
          <Input key="task" label="task " placeholder={`what should ${f.model} do?`} submitLabel="start" onSubmit={start} />
          {f.note ? <Text dimColor>{clip(f.note, cols)}</Text> : null}
          <Text> </Text>
          <Text dimColor>{clip(v.note || HINT, cols)}</Text>
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
          <Input key="msg" label="message " placeholder="message to the selected target" submitLabel="send" onSubmit={send} />
        </>
      ) : v.note ? (
        <Text dimColor>{clip(v.note, cols)}</Text>
      ) : null}
    </Box>
  )
}
