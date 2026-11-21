// Spec 050 Phase 1: Board, the one pane of the agents-inc mod. Mechanical state only, zero model calls.
// Host loader rule: `$` appears only as `$.noun.event(...)` at call sites; never passed, bound or read as a value, and
// every event name is a literal. The poll that feeds it starts in mod.ts's session.start (one registration per event).
import type { Register } from 'claude-code'
import { board, buildBoard, clearHold, noteHold, STOP_TEXT } from './board-model'
import { keyAction, renderBoard } from './board-render'
import type { Line } from './board-render'

export const PANE = 'Board'
export const TITLE = 'Board'
export const POLL_MS = 2000

export const register: Register = on => {
  // The host announces an operator hold with this event (spike S3). The agent's status stays `running`, so the event
  // is the only signal. A hold in the main session has no agent id and makes no row.
  on('classic.PermissionRequest', async ($, e, next) => {
    const now = Number(await $.clock.now())
    if (noteHold(board, e as any, now)) $.ui.invalidate('ui.render')
    return next(e)
  })
  on('classic.Notification', async ($, e, next) => {
    board.notice = String((e as any).message ?? '')
    return next(e)
  })
  // No event says a prompt was answered: a stopped agent clears its hold, and a status change does at the next poll.
  on('classic.SubagentStop', async ($, e, next) => {
    clearHold(board, String((e as any).agent_id ?? ''))
    return next(e)
  })

  on('ui.close', { id: PANE }, async ($, e, next) => {
    if ((e as any).origin?.kind === 'person') board.closedByPerson = true
    return next(e)
  })

  // Reopen: asked open and focused, closed again by Escape. It resets the person's close, so the poll may open again.
  on('command.run', { command: 'board' }, async $ => {
    board.closedByPerson = false
    board.opened = true
    await $.ui.open({ id: PANE, title: TITLE, focus: true, closeOnEscape: true })
    return { text: 'Board opened.' }
  })

  // Keys come from the footer Client. They move the selection or act on it; the actions use the person's own press.
  on('ui.message', { requestId: PANE }, async ($, e, next) => {
    const data = ((e as any).data ?? {}) as { kind?: string; key?: string }
    if (data.kind !== 'key' || typeof data.key !== 'string') return next(e)
    const r = keyAction(board.board, board.selected, data.key)
    board.selected = r.selected
    if (r.act === 'dismiss' && r.entry) {
      board.dismissed[r.entry.key] = true
      board.board = buildBoard(board, Number(await $.clock.now()))
    } else if (r.act === 'open' && r.entry?.agentId) {
      await $.ui.view({ agentId: r.entry.agentId })
    } else if (r.act === 'stop' && r.entry?.agentId) {
      await $.session.send({ to: { agentId: r.entry.agentId }, text: STOP_TEXT })
    }
    $.ui.invalidate('ui.render')
    return next(e)
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (String((e as any).requestId ?? '') !== PANE) return next(e)
    const { Box, Text, Client } = $.ui.resolve(e) as any
    const columns = Number((e as any).props?.bodyColumns ?? (e as any).viewport?.columns ?? 80)
    const r = renderBoard(board.board, { width: columns, selected: board.selected })
    const spans = (line: Line, key: string) =>
      line.length === 0 ? (
        <Text key={key}> </Text>
      ) : (
        <Text key={key}>
          {line.map((s, i) => (
            <Text key={i} color={s.color} dimColor={s.dim}>{s.t}</Text>
          ))}
        </Text>
      )

    return (
      <Box flexDirection="column">
        {r.lines.map((l, i) => spans(l, 'l' + i))}
        {r.footer ? <Text key="gap"> </Text> : null}
        {r.footer && Client ? <Client key="footer" module="./board-footer.tsx" props={{ keys: r.footer, hint: r.hint }} height={1} /> : null}
        {r.footer && !Client ? <Text key="footer" dimColor>{r.footer}</Text> : null}
      </Box>
    )
  })
}
