import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { PaneView } from '../types'

const RUNS = '.scratch/agents-inc-runs'
const KEEP = 60
const POLL_MS = 1000
const EMPTY: PaneView = { run: '', lines: [] }

// One pane per delegate model, opened the first time a run for that model appears. Run dirs are named <UTC stamp>-<model>-<id>.
const views = atom({ plugin: 'delegate-pane', key: 'views' } as const, {} as Record<string, PaneView>, { shape: 'view-2' })
const paneId = (m: string): string => `agents-inc-${m}`

const clip = (s: string, n: number): string => {
  const one = s.replace(/\s+/g, ' ').trim()
  return one.length > n ? one.slice(0, n - 1) + '…' : one
}

const unwrap = (cmd: string): string => cmd.replace(/^\/bin\/(?:ba|z)?sh -lc\s+/, '').replace(/^['"]|['"]$/g, '')

// One events.jsonl row -> one pane line, or '' to skip it.
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


export const register: Register = on => {
  const opened = new Set<string>()

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'delegate-pane', description: 'Open a live pane for every agents-inc delegate model seen so far' })

    // Only runs started in this session open a pane: older run dirs (hundreds pile up) used to open one stale pane per model.
    const since = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z'

    $.clock.every(POLL_MS, async () => {
      try {
        const dirs = (await $.fs.list(RUNS)).filter(d => d.kind === 'dir' && /^\d{8}T\d{6}Z-/.test(d.name) && d.name >= since)
        const newest: Record<string, string> = {}
        for (const d of dirs) {
          const m = d.name.replace(/^\d{8}T\d{6}Z-/, '').split('-')[0]
          if (m && (!newest[m] || d.name > newest[m])) newest[m] = d.name
        }
        const next: Record<string, PaneView> = {}
        const cur = await read($, views)
        for (const [m, name] of Object.entries(newest)) {
          if (!opened.has(m)) {
            opened.add(m)
            void $.ui.open({ id: paneId(m), title: `agents-inc ${m}` })
          }
          const text = await $.fs.read(`${RUNS}/${name}/events.jsonl`).catch(() => '')
          const lines: string[] = []
          for (const raw of text.split('\n')) {
            if (!raw.trim()) continue
            try {
              const l = describe(JSON.parse(raw))
              if (l) lines.push(l)
            } catch {}
          }
          next[m] = { run: name, lines: lines.slice(-KEEP) }
        }
        const same =
          Object.keys(next).length === Object.keys(cur).length &&
          Object.entries(next).every(([m, v]) => {
            const c = cur[m]
            return !!c && c.run === v.run && c.lines.length === v.lines.length && c.lines[c.lines.length - 1] === v.lines[v.lines.length - 1]
          })
        if (!same) await update($, views, () => next)
      } catch (err) {
        await update($, views, () => ({ error: { run: 'pane error', lines: [String((err as Error)?.message ?? err)] } }))
      }
    })

    return next(e)
  })

  on('command.run', { command: 'delegate-pane' }, async $ => {
    for (const m of opened) await $.ui.open({ id: paneId(m), title: `agents-inc ${m}` })
    return { text: opened.size ? `agents-inc panes opened: ${[...opened].join(', ')}.` : 'No delegate runs seen yet; a pane opens on the first run.' }
  })

  on('ui.render', { component: 'Pane' }, async ($, e) => {
    const id = String((e as any).requestId ?? '')
    if (!id.startsWith('agents-inc-')) return undefined
    const m = id.slice('agents-inc-'.length)
    const { Box, Text } = $.ui.resolve(e)
    const v = (await read($, views))[m] ?? EMPTY
    const rows = Math.max(1, (e.viewport?.rows ?? 24) - 4)
    const cols = Math.max(20, (e.viewport?.columns ?? 60) - 2)
    return (
      <Box flexDirection="column">
        <Text bold>{m}</Text>
        <Text dimColor>{v.run || `waiting for a ${m} dispatch…`}</Text>
        <Text> </Text>
        {v.lines.slice(-rows).map(l => {
          if (l.startsWith('●'))
            return (
              <Text>
                <Text color="green">●</Text>
                {clip(l.slice(1), cols - 1)}
              </Text>
            )
          if (l.startsWith('✓')) return <Text color="green">{clip(l, cols)}</Text>
          return <Text dimColor>{clip(l, cols)}</Text>
        })}
      </Box>
    )
  })
}
