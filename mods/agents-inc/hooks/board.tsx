// Spec 050 Phase 1: Board, the one pane of the agents-inc mod. Mechanical state only, zero model calls.
// Host loader rule: `$` appears only as `$.noun.event(...)` at call sites; never passed, bound or read as a value, and
// every event name is a literal. The poll that feeds it starts in mod.ts's session.start (one registration per event).
import type { Register } from 'claude-code'
import { alias, board, buildBoard, clearHold, noteHold, STOP_TEXT } from './board-model'
import { extractMainTurnAnswer, ingestTurn, itemKey } from './board-items'
import { keyAction, renderBoard } from './board-render'
import { afterFill, closesOnSubmit, regionLines, replyText } from './board-reply'
import type { Line } from './board-render'
import { fillMemo, fillSend, isPerson, liveTeams, MEMO_CMD, memoRefText, parseTeam, screenText, TEAM_PREFIX, teamKey, parseMemo, parseSend, parseTell, planSend, SEND_CMD, settle, TELL_CMD } from './board-teams'

export const PANE = 'Board'
export const TITLE = 'Board'
export const POLL_MS = 2000

export const register: Register = on => {
  // The host announces an operator hold with this event (spike S3). The agent's status stays `running`, so the event
  // is the only signal. A hold in the main session has no agent id and makes no row.
  on('classic.PermissionRequest', async ($, e, next) => {
    const now = Number(await $.clock.now())
    if (noteHold(board, e as any, now)) {
      board.board = buildBoard(board, now) // a second prompt replaces the first hold's text at once, not at the next poll
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })
  on('classic.Notification', async ($, e, next) => {
    board.notice = String((e as any).message ?? '')
    return next(e)
  })
  // The host sends no "prompt answered" event. A hold ends when its agent stops, when its status changes (next poll), or
  // when the held tool finishes: PostToolUse, PostToolUseFailure, or PermissionDenied from the same agent. Limit: an
  // approved tool stays shown as NEEDS YOU while it runs, until PostToolUse. PermissionRequest carries no tool_use_id,
  // so the match is by agent_id; a main-session event has none and clears nothing.
  on('classic.SubagentStop', async ($, e, next) => {
    clearHold(board, String((e as any).agent_id ?? ''))
    return next(e)
  })
  on('classic.PostToolUse', async ($, e, next) => {
    if (clearHold(board, String((e as any).agent_id ?? ''))) {
      board.board = buildBoard(board, Number(await $.clock.now()))
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })
  on('classic.PostToolUseFailure', async ($, e, next) => {
    if (clearHold(board, String((e as any).agent_id ?? ''))) {
      board.board = buildBoard(board, Number(await $.clock.now()))
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })
  on('classic.PermissionDenied', async ($, e, next) => {
    if (clearHold(board, String((e as any).agent_id ?? ''))) {
      board.board = buildBoard(board, Number(await $.clock.now()))
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  // CoS markers: read the final answer of a successful main-loop turn (spec 050 T023). No model call, no `next` change.
  on('turn.complete', { reason: 'answer' }, async ($, e, next) => {
    const turn = extractMainTurnAnswer(e)
    if (turn) {
      const now = Number(await $.clock.now())
      ingestTurn(board.items, String((e as any).sessionId ?? ''), turn, now)
      board.board = buildBoard(board, now)
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  // Send and Memo through the chat composer. The operator's own Enter on the slash command is the deliberate act; a run that
  // came from a plugin, the model or the bridge is refused, so a CoS marker or reply can never send. Plugin provenance stays.
  const finish = (plan: ReturnType<typeof planSend>, text: string, result: unknown, now: number) => {
    const out = settle(plan, text, result, board.items, board.sent, now)
    board.board = buildBoard(board, now)
    return { text: out.delivered ? (plan.how === 'fyi' ? "FYI queued for that Team's Chief." : 'Queued.') : (out.line ?? 'not delivered') }
  }
  const failed = (err: unknown) => ({ isDelivered: false, reason: String((err as Error)?.message ?? 'send failed') })
  const NOT_PERSON = { text: 'not delivered: only the operator typing this in the chat sends from Board' }
  on('command.run', { command: SEND_CMD }, async ($, e) => {
    if (!isPerson((e as any).origin)) return NOT_PERSON
    // Candidates are read now, not from the last poll: every live team.* key, so a ref that became ambiguous or stale
    // is refused. Own key and stale heartbeats are left out (S1: the store cannot tell live from dead).
    const now0 = Number(await $.clock.now())
    const found: Array<ReturnType<typeof parseTeam>> = []
    for (const k of (await $.store.keys()) as string[]) if (k.startsWith(TEAM_PREFIX)) found.push(parseTeam(k, await $.store.get(k)))
    const fresh = liveTeams(found, board.sessionId, now0)
    const p = parseSend(String((e as any).args ?? ''), fresh)
    if (!p.ok) return { text: p.line }
    const bad = screenText(p.text)
    if (bad) return { text: `not delivered: ${bad}` }
    const plan = planSend(p.target, p.text, board.sessionId)
    const tooBig = screenText(plan.text) // the 64 KiB cap applies to the final payload, prefix included
    if (tooBig) return { text: `not delivered: ${tooBig}` }
    let result: unknown
    try {
      result = await $.session.send({ to: plan.to, text: plan.text })
    } catch (err) {
      result = failed(err)
    }
    const r = finish(plan, p.text, result, Number(await $.clock.now()))
    $.ui.invalidate('ui.render')
    return r
  })
  on('command.run', { command: MEMO_CMD }, async ($, e) => {
    if (!isPerson((e as any).origin)) return NOT_PERSON
    const live = ['pending', 'running', 'waiting', 'idle']
    const agents = Object.values(board.agents).filter(a => live.includes(a.status)).map(a => ({ id: a.id, alias: alias(a.type) }))
    const p = parseMemo(String((e as any).args ?? ''), agents, board.sessionId, board.teamName)
    if (!p.ok) {
      // D91: an undeliverable Memo is one FYI row. A ref that matches no live delegate but exactly one agent this session
      // has seen (its last known type is kept in board.agents) is a Worker that has gone: send nothing, keep the text.
      const [ref, text] = memoRefText(String((e as any).args ?? ''))
      const seen = ref ? Object.values(board.agents).filter(a => a.id.startsWith(ref)) : []
      if (seen.length !== 1 || !text) return { text: p.line }
      const badText = screenText(text)
      if (badText) return { text: `not delivered: ${badText}` }
      const gone = planSend({ kind: 'memo', agentId: seen[0]!.id, alias: alias(seen[0]!.type), teamId: board.sessionId, teamName: board.teamName }, text, board.sessionId)
      const goneBig = screenText(gone.text)
      if (goneBig) return { text: `not delivered: ${goneBig}` }
      const g = finish(gone, text, { isDelivered: false, reason: 'worker finished' }, Number(await $.clock.now()))
      $.ui.invalidate('ui.render')
      return g
    }
    const bad = screenText(p.text)
    if (bad) return { text: `not delivered: ${bad}` }
    const plan = planSend(p.target, p.text, board.sessionId)
    const tooBig = screenText(plan.text) // the 64 KiB cap applies to the final payload, prefix included
    if (tooBig) return { text: `not delivered: ${tooBig}` }
    // D91: a Memo never starts a resume. A `{ agentId }` send to a finished subagent makes the host resume it from its
    // transcript, so send only while the host lists the agent as running at this moment. Known limit: a Worker that
    // finishes between this check and delivery is still resumed by the host (no atomic check-and-send exists).
    let result: unknown
    let running = false
    try {
      const listed = ((await $.agent.list()) as Array<{ id?: string; status?: string }>) ?? []
      running = listed.some(a => p.target.kind === 'memo' && a.id === p.target.agentId && a.status === 'running')
      if (!running) result = { isDelivered: false, reason: 'worker finished' }
    } catch {
      result = { isDelivered: false, reason: 'could not check that the worker is running' }
    }
    if (running) {
      try {
        result = await $.session.send({ to: plan.to, text: plan.text })
      } catch (err) {
        result = failed(err)
      }
    }
    const r = finish(plan, p.text, result, Number(await $.clock.now()))
    $.ui.invalidate('ui.render')
    return r
  })
  on('command.run', { command: TELL_CMD }, async ($, e) => {
    if (!isPerson((e as any).origin)) return NOT_PERSON
    const now0 = Number(await $.clock.now())
    const found: Array<ReturnType<typeof parseTeam>> = []
    for (const k of (await $.store.keys()) as string[]) if (k.startsWith(TEAM_PREFIX)) found.push(parseTeam(k, await $.store.get(k)))
    const fresh = liveTeams(found, board.sessionId, now0)
    const p = parseTell(String((e as any).args ?? ''), fresh)
    if (!p.ok) return { text: p.line }
    const bad = screenText(p.text)
    if (bad) return { text: `not delivered: ${bad}` }
    const plan = planSend(p.target, p.text, board.sessionId)
    const tooBig = screenText(plan.text) // the 64 KiB cap applies to the final payload, prefix included
    if (tooBig) return { text: `not delivered: ${tooBig}` }
    let result: unknown
    try {
      result = await $.session.send({ to: plan.to, text: plan.text })
    } catch (err) {
      result = failed(err)
    }
    const r = finish(plan, p.text, result, Number(await $.clock.now()))
    $.ui.invalidate('ui.render')
    return r
  })

  on('ui.close', { id: PANE }, async ($, e, next) => {
    if ((e as any).origin?.kind === 'person') board.closedByPerson = true
    return next(e)
  })

  // Reopen: asked open and focused. Escape returns keys; the pane stays. It resets the person's close, so the poll may open again.
  on('command.run', { command: 'board' }, async $ => {
    board.closedByPerson = false
    board.opened = true
    await $.ui.open({ id: PANE, title: TITLE, focus: true })
    return { text: 'Board opened.' }
  })

  // Keys come from the footer Client. They move the selection or act on it; the actions use the person's own press.
  // With the reply region open: x closes it, a digit fills the chat box with that quick reply (the operator presses
  // Enter in chat), and a `reply` message fills free text. Nothing here sends: no `$.session.send` for replies.
  on('ui.message', { requestId: PANE }, async ($, e, next) => {
    const data = ((e as any).data ?? {}) as { kind?: string; key?: string; text?: string }
    const open = board.reply ? board.items.items.find(i => i.id === board.reply!.itemId) : undefined
    if (board.reply && !open) board.reply = undefined
    if (open && board.reply && (data.kind === 'reply' || (data.kind === 'key' && typeof data.key === 'string'))) {
      const text = data.kind === 'reply' ? String(data.text ?? '').trim() : (replyText(open, String(data.key)) ?? '')
      if (data.kind === 'key' && data.key === 'x') board.reply = undefined
      else if (text) {
        const r = await $.prompt.fill({ text, mode: 'replace' })
        board.reply = afterFill(board.reply, text, (r as any)?.isFilled)
        board.fillHint = true
      }
      $.ui.invalidate('ui.render')
      return next(e)
    }
    if (data.kind !== 'key' || typeof data.key !== 'string') return next(e)
    board.fillHint = false
    const r = keyAction(board.board, board.selected, data.key)
    board.selected = r.selected
    if (r.act === 'dismiss' && r.entry) {
      board.dismissed[r.entry.key] = true
      board.board = buildBoard(board, Number(await $.clock.now()))
    } else if (r.act === 'reply' && r.entry?.teamId) {
      board.reply = undefined
      await $.prompt.fill({ text: fillSend({ id: r.entry.teamId }), mode: 'replace' })
      board.fillHint = true
    } else if (r.act === 'memo' && r.entry?.agentId) {
      board.reply = undefined
      await $.prompt.fill({ text: fillMemo({ id: r.entry.agentId }), mode: 'replace' })
      board.fillHint = true
    } else if (r.act === 'reply' && r.entry) {
      const item = board.items.items.find(i => itemKey(i) === r.entry!.key)
      if (item) board.reply = { itemId: item.id }
    } else if (r.act === 'open' && r.entry?.agentId) {
      await $.ui.view({ agentId: r.entry.agentId })
    } else if (r.act === 'stop' && r.entry?.agentId) {
      await $.session.send({ to: { agentId: r.entry.agentId }, text: STOP_TEXT })
    }
    $.ui.invalidate('ui.render')
    return next(e)
  })

  // The Item closes only when the operator's own chat submission carries exactly the text Board filled for it.
  on('prompt.submit', async ($, e, next) => {
    board.fillHint = false
    if (closesOnSubmit(board.reply, e as any)) {
      const item = board.items.items.find(i => i.id === board.reply!.itemId)
      if (item) {
        board.dismissed[itemKey(item)] = true
        board.sent.push(board.reply!.pending!)
      }
      board.reply = undefined
      board.board = buildBoard(board, Number(await $.clock.now()))
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (String((e as any).requestId ?? '') !== PANE) return next(e)
    const { Box, Text, Client } = $.ui.resolve(e) as any
    const columns = Number((e as any).props?.bodyColumns ?? (e as any).viewport?.columns ?? 80)
    const r = renderBoard(board.board, { width: columns, selected: board.selected })
    const item = board.reply ? board.items.items.find(i => i.id === board.reply!.itemId) : undefined
    const region = item ? regionLines(item, Number(await $.clock.now()), board.sent, columns) : []
    // Host fact: no API returns the keys to the composer (ui.focus only moves the ring inside the pane; a re-open cannot
    // drop focus). After a fill the Board keeps the keys until the operator presses Escape.
    const footer = board.fillHint ? 'Esc, then type' : item ? `1-${Math.max(3, item.options.length)} fill reply  x close` : r.footer
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
        {region.map((l, i) => spans(l, 'r' + i))}
        {footer ? <Text key="gap"> </Text> : null}
        {footer && Client ? <Client key="footer" module="./board-footer.tsx" props={{ keys: footer, hint: r.hint }} height={1} /> : null}
        {footer && !Client ? <Text key="footer" dimColor>{footer}</Text> : null}
      </Box>
    )
  })
}
