import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { PaneView } from '../types'

const RUNS = '.scratch/agents-inc-runs'
const KEEP = 60
const POLL_MS = 1000
const EMPTY: PaneView = { run: '', lines: [] }

// One pane per delegate model: each shows the newest run dir whose name carries that model.
const MODELS = ['luna', 'haiku'] as const
type Model = (typeof MODELS)[number]

const lunaView = atom({ plugin: 'luna-pane', key: 'luna' } as const, EMPTY, { shape: 'view-2' })
const haikuView = atom({ plugin: 'luna-pane', key: 'haiku' } as const, EMPTY, { shape: 'view-2' })
const paneId = (m: Model): string => `agents-inc-${m}`

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
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'luna-pane', description: 'Open one live pane per agents-inc delegate (luna, haiku)' })
    for (const m of MODELS) void $.ui.open({ id: paneId(m), title: `agents-inc ${m}` })

    $.clock.every(POLL_MS, async () => {
      try {
        const dirs = (await $.fs.list(RUNS)).filter(d => d.kind === 'dir' && /^\d{8}T\d{6}Z-/.test(d.name))
        for (const m of MODELS) {
          const mine = dirs.filter(d => d.name.includes(`-${m}-`))
          if (mine.length === 0) continue
          const newest = [...mine].sort((a, b) => (a.name < b.name ? 1 : -1))[0]
          const text = await $.fs.read(`${RUNS}/${newest.name}/events.jsonl`).catch(() => '')
          const lines: string[] = []
          for (const raw of text.split('\n')) {
            if (!raw.trim()) continue
            try {
              const l = describe(JSON.parse(raw))
              if (l) lines.push(l)
            } catch {}
          }
          const nextView: PaneView = { run: newest.name, lines: lines.slice(-KEEP) }
          const cur = m === 'luna' ? await read($, lunaView) : await read($, haikuView)
          const changed =
            cur.run !== nextView.run ||
            cur.lines.length !== nextView.lines.length ||
            cur.lines[cur.lines.length - 1] !== nextView.lines[nextView.lines.length - 1]
          if (changed && m === 'luna') await update($, lunaView, () => nextView)
          if (changed && m === 'haiku') await update($, haikuView, () => nextView)
        }
      } catch (err) {
        await update($, lunaView, () => ({ run: 'pane error', lines: [String((err as Error)?.message ?? err)] }))
      }
    })

    return next(e)
  })

  on('command.run', { command: 'luna-pane' }, async $ => {
    for (const m of MODELS) await $.ui.open({ id: paneId(m), title: `agents-inc ${m}` })
    return { text: 'agents-inc luna and haiku panes opened.' }
  })

  for (const m of MODELS) {
    on('ui.render', { component: 'Pane', requestId: paneId(m) }, async ($, e) => {
      const { Box, Text } = $.ui.resolve(e)
      const v = m === 'luna' ? await read($, lunaView) : await read($, haikuView)
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
}
