import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { PaneAgent, PaneView } from '../types'

// Spec 038 FR-020: the pane lists only native agents (agents-inc:<nickname> subagents, running or finished in this
// session) and the registered native types. It lists no dispatch run directory: those cannot be opened as a transcript.
// A native agent's own transcript is Claude Code's subagent view; the pane names it, it does not copy it.
export const PANE = 'agents-inc-delegates'
const PREFIX = 'agents-inc:'
// The legacy relay type (install --legacy-routes) is a route, not a native agent.
const NOT_NATIVE = new Set(['agents-inc:relay'])
const POLL_MS = 1000
const KEEP = 40
const EMPTY: PaneView = { types: [], agents: [], note: '' }

const view = atom({ plugin: 'delegate-pane', key: 'view' } as const, EMPTY, { shape: 'view-3' })

export const isNative = (type: unknown): boolean =>
  typeof type === 'string' && type.startsWith(PREFIX) && !NOT_NATIVE.has(type)

type Listed = { id: string; type?: string; name?: string; description?: string; status?: string }

// Merge one agent.list answer into the session's agents. An agent the engine no longer lists stays, marked finished
// unless it already ended: the pane keeps every native agent of the session (FR-020).
export function mergeAgents(prev: PaneAgent[], listed: Listed[]): PaneAgent[] {
  const now = new Map(listed.filter(a => a && isNative(a.type)).map(a => [a.id, a] as const))
  const out: PaneAgent[] = prev.map(p => {
    const a = now.get(p.id)
    if (!a) return p.status === 'running' ? { ...p, status: 'finished' } : p
    now.delete(p.id)
    return { ...p, status: String(a.status ?? p.status), description: String(a.description ?? p.description) }
  })
  for (const a of now.values())
    out.push({ id: a.id, type: String(a.type), description: String(a.description ?? a.name ?? ''), status: String(a.status ?? 'running') })
  return out.slice(-KEEP)
}

// The offered types from `agents-inc luna status --json --all` (the one read the agents-inc mod makes too).
export function offeredTypes(statusJson: string): string[] {
  try {
    const models = (JSON.parse(statusJson) as { models?: unknown }).models
    if (!Array.isArray(models)) return []
    return models
      .filter(m => m && typeof m.nickname === 'string' && m.offered === true)
      .map(m => PREFIX + String(m.nickname))
  } catch {
    return []
  }
}

export const register: Register = on => {
  let agents: PaneAgent[] = []

  on('session.start', async ($, e, next) => {
    agents = []
    await $.command.register({ name: 'delegate-pane', description: 'Open the agents-inc pane: native agent types and native agents of this session' })
    let types: string[] = []
    let note = ''
    try {
      const stream = $.process.spawn({ argv: ['agents-inc', 'luna', 'status', '--json', '--all', '--cwd', e.cwd || '.'], cwd: e.cwd || undefined })
      let out = ''
      for (;;) {
        const n = await stream.next()
        if (n.done) {
          if (n.value.code !== 0) note = 'agents-inc status gave no answer; no native types listed'
          break
        }
        if (n.value.stream === 'stdout') out += n.value.text
      }
      if (!note) types = offeredTypes(out)
    } catch {
      note = 'agents-inc status gave no answer; no native types listed'
    }
    await update($, view, () => ({ types, agents: [], note }))

    $.clock.every(POLL_MS, async () => {
      try {
        const merged = mergeAgents(agents, (await $.agent.list()) as Listed[])
        const same = merged.length === agents.length && merged.every((a, i) => a.status === agents[i].status && a.id === agents[i].id)
        agents = merged
        if (!same) await update($, view, v => ({ ...v, agents: merged }))
      } catch (err) {
        await update($, view, v => ({ ...v, note: `pane error: ${String((err as Error)?.message ?? err)}` }))
      }
    })
    return next(e)
  })

  on('command.run', { command: 'delegate-pane' }, async $ => {
    await $.ui.open({ id: PANE, title: 'agents-inc native agents' })
    return { text: 'agents-inc pane opened.' }
  })

  on('ui.render', { component: 'Pane' }, async ($, e) => {
    if (String((e as any).requestId ?? '') !== PANE) return undefined
    const { Box, Text } = $.ui.resolve(e)
    const v = await read($, view)
    return (
      <Box flexDirection="column">
        <Text bold>Native agent types</Text>
        {v.types.length ? v.types.map(t => <Text>{'  ' + t}</Text>) : <Text dimColor>  none registered</Text>}
        <Text> </Text>
        <Text bold>Native agents this session</Text>
        {v.agents.length ? (
          v.agents.map(a => (
            <Text>
              <Text color={a.status === 'running' ? 'green' : undefined}>{a.status === 'running' ? '● ' : '✓ '}</Text>
              {`${a.type} · ${a.description} · ${a.status}`}
            </Text>
          ))
        ) : (
          <Text dimColor>  none yet</Text>
        )}
        {v.note ? <Text dimColor>{v.note}</Text> : null}
      </Box>
    )
  })
}
