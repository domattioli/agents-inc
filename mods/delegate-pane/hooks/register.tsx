import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { PaneView } from '../types'
import { MAIN_ROLE, ackId, hierarchyLines, layoutFor, stations, statusLine, feed, isAlert } from './mission'
import type { State, Station, Delegate } from './mission'
import { cosRoom, dispatchesOf, encodeCells, frame, FRAME_MS, landings, needsMotion, RASTER_ROWS, rasterColumns } from './frames'
import type { Return } from './frames'
import { controlsView, renderRun } from './controls'
import { applyRunLines } from './controls'
import { poll } from './poll'
import { EMPTY, compose, newState, normalizeView, resetState, RUN_PANE } from './tree'
import type { View } from './tree'

export { mergeAgents } from './poll'
export { normalizeView } from './tree'

// Spec 040: one pane for the delegates of the session. The map (spec 039) draws every subagent type and each dispatch
// run directory of this session; the tree, the new-agent form and the message box (hooks/controls.tsx) act on them.
// A native agent's own transcript is Claude Code's subagent view; the pane names it, it does not copy it.
// view-5: acks became `<id>@<alertAt>` keys; a view-4 value (plain-id acks) reads as EMPTY and the store record refills it.
// The state scan wants the atom spelled in each file that reads it, so controls.tsx and register.tsx both declare it.
const view = atom({ plugin: 'delegate-pane', key: 'view' } as const, EMPTY as any, { shape: 'view-5' })

export const PANE = 'agents-inc-delegates'
const TITLE = 'agents-inc'
const POLL_MS = 1000
const MAP_CAP = 4
const FEED_MIN = 3
const FEED_MAX = 10
// Spec 039 FR-013: session start, acks and subagent alert times are mirrored to $.store under `session:<session id>`,
// so `claude --resume` (a new process, empty $.state) keeps them. The store keeps the STORE_KEEP most recent sessions.
const STORE_PREFIX = 'session:'
const STORE_KEEP = 20

type Saved = { sessionStart: string; acked: Record<string, string[]>; alertAt: Record<string, number>; savedAt: number }
const savedOf = (v: View): Omit<Saved, 'savedAt'> => ({ sessionStart: v.sessionStart, acked: v.acked, alertAt: v.alertAt })

// Read this session's record from $.store; undefined when there is none or the store or session id is not reachable.
async function loadSaved($: any): Promise<Saved | undefined> {
  try {
    const id = String(await $.session.id())
    const rec = (await $.store.get(STORE_PREFIX + id)) as Saved | undefined
    return rec && typeof rec === 'object' && typeof rec.sessionStart === 'string' ? rec : undefined
  } catch {
    return undefined
  }
}

// Write this session's record and drop all but the STORE_KEEP most recent session records. A store that fails is let
// go: the pane keeps working from $.state.
async function save($: any, v: View): Promise<void> {
  try {
    const id = String(await $.session.id())
    const now = Number(await $.clock.now())
    await $.store.set(STORE_PREFIX + id, { ...savedOf(v), savedAt: now })
    const keys = ((await $.store.keys()) as string[]).filter(k => k.startsWith(STORE_PREFIX))
    if (keys.length <= STORE_KEEP) return
    const aged: Array<[string, number]> = []
    for (const k of keys) aged.push([k, Number(((await $.store.get(k)) as Saved | undefined)?.savedAt ?? 0)])
    aged.sort((a, b) => b[1] - a[1])
    for (const [k] of aged.slice(STORE_KEEP)) await $.store.delete(k)
  } catch {
    // nothing to do: $.state still holds the view
  }
}

// Motion (terminal only): one frame timer while the pane is shown in the terminal grid layout and a station moves.
// Module state, as the engine wants every $-taking helper declared at the top of the file. `motion.timer` is the only
// timer; stopMotion cancels it. `off`: a blit was refused, so the pane draws the static map until it is opened again.
// `seen` and `returns`: the delegate states of the last look and the return pulses still in flight (frames.landings).
const motion: { timer?: { cancel: () => void }; cols: number; off: boolean; seen: Record<string, State>; returns: Return[] } = {
  cols: 0,
  off: false,
  seen: {},
  returns: [],
}
// The CoS node's label on the Raster: the glossary term and the main session's model when the engine gives one; the
// model is dropped when it does not fit `room` cells.
export const cosLabel = (v: View, room = Infinity): string => {
  const full = v.model ? `CoS · ${v.model}` : 'CoS'
  return full.length <= room ? full : 'CoS'
}
function track(delegates: Delegate[], t: number): void {
  const r = landings(motion.seen, delegates, motion.returns, t)
  motion.seen = r.seen
  motion.returns = r.returns
}
function stopMotion(): void {
  motion.timer?.cancel()
  motion.timer = undefined
}
function startMotion($: any): void {
  if (motion.timer) return
  motion.timer = $.clock.every(FRAME_MS, async () => {
    try {
      const cur = normalizeView(await read($, view))
      const sts = stations(cur.delegates, cur.acked)
      const t = Number(await $.clock.now())
      track(cur.delegates, t)
      // a return pulse keeps the timer until it lands
      const dispatches = dispatchesOf(cur.delegates, t)
      if (!needsMotion(sts, motion.returns, t, dispatches) || !motion.cols) return stopMotion()
      const cells = encodeCells(frame(sts, t, motion.cols, RASTER_ROWS, motion.returns, { cos: cosLabel(cur, cosRoom(motion.cols)), dispatches }))
      const res = await $.ui.blit({ requestId: PANE, key: 'map', columns: motion.cols, rows: RASTER_ROWS, cells })
      if (res?.deny) throw new Error(res.deny)
    } catch {
      // Not mounted, another size, or refused: stop and fall back to the static map.
      stopMotion()
      motion.off = true
      try {
        $.ui.invalidate('ui.render')
      } catch {
        // nothing more to do
      }
    }
  })
}

export const register: Register = on => {
  const st = newState()
  on('session.start', async ($, e, next) => {
    resetState(st, e.cwd || '.')
    stopMotion()
    motion.off = false
    motion.seen = {}
    motion.returns = []
    const nowIso = new Date(await $.clock.now()).toISOString()
    await $.command.register({ name: 'delegate-pane', description: 'Open the agents-inc pane: the delegation tree, the mission map, a new-agent form and a message box' })
    // sessionStart, acked and finalRuns survive a reload: sessionStart is set once. After `--resume` $.state is empty:
    // this session's $.store record (FR-013) gives back its start, acks and subagent alert times.
    const saved = normalizeView(await read($, view)).sessionStart ? undefined : await loadSaved($)
    const started = await update($, view, v => {
      const n = normalizeView(v)
      const restored = !n.sessionStart && saved ? { sessionStart: saved.sessionStart, acked: saved.acked ?? {}, alertAt: saved.alertAt ?? {} } : {}
      return { ...n, ...restored, treeRows: [], summary: '', delegates: [], mapNote: '', note: '', sessionStart: (restored as any).sessionStart || n.sessionStart || nowIso }
    })
    await save($, normalizeView(started as PaneView))

    // One poll a second feeds the tree, the map, the status line and the feed.
    $.clock.every(POLL_MS, async () => {
      try {
        const v = normalizeView(await read($, view))
        const now = Number(await $.clock.now())
        const r = await poll($, st, v, now)
        const treeRows = compose(st)
        const sig = JSON.stringify([treeRows, st.summary, r.delegates, r.mapNote, r.model, r.runLines])
        if (sig !== st.lastSig || v.note.startsWith('poll error: ')) {
          st.lastSig = sig
          const alertsMoved = JSON.stringify(r.alertAt) !== JSON.stringify(v.alertAt)
          const next1 = await update($, view, x => {
            const n = normalizeView(x)
            return { ...n, treeRows, summary: r.summary, delegates: r.delegates, finalRuns: r.finalRuns, lostRuns: r.lostRuns, alertAt: r.alertAt, mapNote: r.mapNote, model: r.model, seen: r.seen, note: n.note.startsWith('poll error: ') ? '' : n.note }
          })
          if (alertsMoved) await save($, normalizeView(next1 as PaneView))
          await applyRunLines($, r.runLines)
        }
      } catch (err) {
        await update($, view, v => ({ ...normalizeView(v), note: `poll error: ${String((err as Error)?.message ?? err)}` }))
      }
    })
    // Open at session start; /delegate-pane reopens it. Non-blocking: a refused open must not break the start.
    motion.off = false
    try {
      void Promise.resolve($.ui.open({ id: PANE, title: TITLE })).catch(() => {})
    } catch {
      // open refused: the command still opens the pane
    }
    return next(e)
  })

  on('ui.close', ($, e, next) => {
    if (e.id === PANE) stopMotion()
    if (String(e.id).startsWith(RUN_PANE)) st.open.delete(String(e.id).slice(RUN_PANE.length))
    return next(e)
  })

  on('command.run', { command: 'delegate-pane' }, async $ => {
    motion.off = false
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: 'agents-inc pane opened.' }
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    const rid = String((e as any).requestId ?? '')
    if (rid.startsWith(RUN_PANE)) return renderRun($, e, st, rid.slice(RUN_PANE.length))
    if (rid !== PANE) return next(e)
    const els = $.ui.resolve(e) as any
    const { Box, Text, Button } = els
    const v = normalizeView(await read($, view))
    const columns = Number((e as any).props?.bodyColumns ?? (e as any).viewport?.columns ?? 80)
    // Feed rows: a third of the pane body, FEED_MIN to FEED_MAX.
    const bodyRows = Number((e as any).props?.scroll?.bodyRows ?? 24)
    const feedCap = Math.max(FEED_MIN, Math.min(FEED_MAX, Math.floor(bodyRows / 3)))
    const layout = layoutFor(columns)
    const sts = stations(v.delegates, v.acked)
    const working = v.delegates.filter(d => d.state === 'running' || d.state === 'review').length
    const ack = (s: Station) => async () => {
      const cur = normalizeView(await read($, view))
      const keys = stations(cur.delegates, cur.acked).find(x => x.category === s.category)?.unacked ?? []
      // No count trim: a key superseded by a newer event of the same delegate is dropped, so a station holds at most
      // one key per delegate of this session; the store keeps whole sessions, STORE_KEEP of them.
      const newIds = new Set(keys.map(ackId))
      const after = await update($, view, x => {
        const n = normalizeView(x)
        const kept = (n.acked[s.category] ?? []).filter(k => !newIds.has(ackId(k)))
        return { ...n, acked: { ...n.acked, [s.category]: [...kept, ...keys] } }
      })
      await save($, normalizeView(after as PaneView))
    }
    const title = (s: Station) => (
      <Text>
        <Text color={s.lit ? 'green' : undefined} dimColor={!s.lit}>{(s.lit ? '● ' : '○ ') + s.category}</Text>
        {s.unacked.length ? <Text color="red">{` ${s.unacked.length}✗`}</Text> : null}
      </Text>
    )
    const ackButton = (s: Station) =>
      s.unacked.length ? (
        <Button key={'ack-' + s.category} onPress={ack(s)}>
          <Text color="red">{' ack '}</Text>
        </Button>
      ) : null
    const markers = (s: Station) => {
      const shown = s.delegates.slice(0, MAP_CAP)
      return (
        <>
          {shown.map(d => (
            <Text color={isAlert(d.state) ? 'red' : undefined}>{`${d.nickname} · ${d.rung} · ${d.state}`}</Text>
          ))}
          {s.delegates.length > MAP_CAP ? <Text dimColor>{`+${s.delegates.length - MAP_CAP} more`}</Text> : null}
        </>
      )
    }
    const station = (s: Station) => (
      <Box key={s.category} flexDirection="column" width={22} borderStyle={s.delegates.length ? 'round' : undefined}>
        {title(s)}
        {markers(s)}
        {ackButton(s)}
      </Box>
    )
    const centreTail = ` · ${working} working${v.model ? ` · ${v.model}` : ''}`
    const centreRole = `◉ main session · ${MAIN_ROLE}${centreTail}`
    // The role goes first when the line does not fit: the line is wrapped in `──── … ────`.
    const centre = centreRole.length + 10 <= columns ? centreRole : `◉ main session${centreTail}`
    // Motion: terminal, at least RASTER_MIN_COLUMNS wide (grid or stacked), Raster in the element table, no refused blit. Otherwise the static map only.
    // The frame timer is shared by every mounted copy of the pane; only a terminal render may set its width or stop it,
    // or a desktop or too-narrow render would cancel the animation of the terminal one while an agent still runs (#191).
    const terminal = (e as any).surface === 'terminal'
    const cols = terminal && !motion.off && els.Raster ? rasterColumns(columns) : 0
    if (terminal) motion.cols = cols
    let now = 0
    try {
      now = Number(await $.clock.now())
    } catch {
      // no clock: the first frame draws at time 0
    }
    track(v.delegates, now)
    const dispatches = dispatchesOf(v.delegates, now)
    if (terminal) {
      if (cols && needsMotion(sts, motion.returns, now, dispatches)) startMotion($)
      else stopMotion()
    }
    const raster = cols ? (
      <els.Raster key="map" columns={cols} rows={RASTER_ROWS} cells={encodeCells(frame(sts, now, cols, RASTER_ROWS, motion.returns, { cos: cosLabel(v, cosRoom(cols)), dispatches }))} />
    ) : null
    // CoS, Lead and primary Worker in one or two dim lines, on every surface and layout (the static fallback included).
    const roles = hierarchyLines(v.delegates, v.model, columns).map((line, k) => <Text key={'roles-' + k} dimColor>{line}</Text>)
    const map =
      layout === 'grid' ? (
        <Box flexDirection="column">
          {raster}
          <Text>{`──── ${centre} ────`}</Text>
          {roles}
          <Box flexDirection="row">{sts.slice(0, 3).map(station)}</Box>
          <Box flexDirection="row">{sts.slice(3).map(station)}</Box>
        </Box>
      ) : layout === 'stacked' ? (
        <Box flexDirection="column">
          {raster}
          <Text>{centre}</Text>
          {roles}
          {sts.map(s => (
            <Box key={s.category} flexDirection="column">
              {title(s)}
              {s.delegates.length ? <Box flexDirection="column" paddingLeft={2}>{markers(s)}</Box> : null}
              {ackButton(s)}
            </Box>
          ))}
        </Box>
      ) : (
        <Box flexDirection="column">
          {roles}
          {sts.map(s => (
            <Box key={s.category} flexDirection="row">
              <Text>{`${s.category} ${s.delegates.filter(d => d.state === 'running' || d.state === 'review').length}● ${s.unacked.length}✗`}</Text>
              {ackButton(s)}
            </Box>
          ))}
        </Box>
      )
    return (
      <Box flexDirection="column">
        <Text bold>Mission map</Text>
        {map}
        <Text bold>{statusLine(v.delegates, columns)}</Text>
        {feed(v.delegates, columns, feedCap).map(row => (
          <Text key={'feed-' + row.id} color={row.kind === 'running' ? 'yellow' : row.kind === 'failed' ? 'red' : undefined} dimColor={row.kind === 'done' || row.kind === 'paused'}>
            {row.lead}
            {row.roleCol ? <Text dimColor>{row.roleCol}</Text> : null}
            {row.tail}
          </Text>
        ))}
        {v.mapNote ? <Text dimColor>{v.mapNote}</Text> : null}
        {await controlsView($, els, st, v, columns)}
      </Box>
    )
  })
}
