import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { PaneAgent, PaneDelegate, PaneView } from '../types'
import { MAIN_ROLE, ackId, hierarchyLines, categoryOf, dirTime, feed, isAlert, isDryRun, layoutFor, lifecycleOf, runFromFiles, rungOf, sessionRuns, stations, statusLine, withLost } from './mission'
import type { Delegate, State, Station } from './mission'
import { cosRoom, dispatchesOf, encodeCells, frame, FRAME_MS, landings, needsMotion, RASTER_ROWS, rasterColumns } from './frames'
import type { Return } from './frames'

// Spec 038 FR-020: the two top lists show only native agents (agents-inc:<nickname> subagents, running or finished in
// this session) and the registered native types. Spec 039: the mission map below them also draws every other subagent
// type and each dispatch run directory of this session (FR-003). A native agent's own transcript is Claude Code's
// subagent view; the pane names it, it does not copy it.
export const PANE = 'agents-inc-delegates'
const PREFIX = 'agents-inc:'
// The legacy relay type (install --legacy-routes) is a route, not a native agent.
const NOT_NATIVE = new Set(['agents-inc:relay'])
const POLL_MS = 1000
const KEEP = 40
// Spec 039: the mission map. Dispatch runs live under the run root (plan R1); a map station shows at most MAP_CAP markers.
const RUN_ROOT = '.scratch/agents-inc-runs'
const MAP_CAP = 4
const FEED_MIN = 3
const FEED_MAX = 10
// Spec 039 FR-013: session start, acks and subagent alert times are mirrored to $.store under `session:<session id>`,
// so `claude --resume` (a new process, empty $.state) keeps them. The store keeps the STORE_KEEP most recent sessions.
const STORE_PREFIX = 'session:'
const STORE_KEEP = 20
const EMPTY: PaneView = {
  types: [], agents: [], note: '', delegates: [], acked: {}, alertAt: {}, sessionStart: '', finalRuns: {}, lostRuns: {}, mapNote: '', model: '', seen: {},
}

// view-5: acks became `<id>@<alertAt>` keys; a view-4 value (plain-id acks) reads as EMPTY and the store record refills it.
const view = atom({ plugin: 'delegate-pane', key: 'view' } as const, EMPTY, { shape: 'view-5' })

type Saved = { sessionStart: string; acked: Record<string, string[]>; alertAt: Record<string, number>; savedAt: number }
const savedOf = (v: PaneView): Omit<Saved, 'savedAt'> => ({ sessionStart: v.sessionStart, acked: v.acked, alertAt: v.alertAt })

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
async function save($: any, v: PaneView): Promise<void> {
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

// A value an older code version wrote (no map fields) still renders.
export const normalizeView = (v: Partial<PaneView> | undefined): PaneView => ({ ...EMPTY, ...(v ?? {}) })

export const isNative = (type: unknown): boolean =>
  typeof type === 'string' && type.startsWith(PREFIX) && !NOT_NATIVE.has(type)

type Listed = { id: string; type?: string; name?: string; description?: string; status?: string; parentId?: string }

// Merge one agent.list answer into the session's agents. An agent the engine no longer lists stays, marked finished
// unless it already ended: the pane keeps every native agent of the session (FR-020).
// `cap` bounds the list (KEEP); the map passes Infinity so every subagent of the session keeps its marker (FR-003).
export function mergeAgents(prev: PaneAgent[], listed: Listed[], keep: (type: unknown) => boolean = isNative, cap = KEEP): PaneAgent[] {
  const now = new Map(listed.filter(a => a && keep(a.type)).map(a => [a.id, a] as const))
  const out: PaneAgent[] = prev.map(p => {
    const a = now.get(p.id)
    if (!a) return p.status === 'running' ? { ...p, status: 'finished' } : p
    now.delete(p.id)
    return { ...p, status: String(a.status ?? p.status), description: String(a.description ?? p.description) }
  })
  for (const a of now.values())
    out.push({
      id: a.id, type: String(a.type), description: String(a.description ?? a.name ?? ''), status: String(a.status ?? 'running'),
      ...(a.parentId ? { parentId: String(a.parentId) } : {}),
    })
  return Number.isFinite(cap) ? out.slice(-cap) : out
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

// One poll of the run root: one list, then run files only for runs of this session that are not yet final (plan R1 bound).
// A failed read is told apart from a missing file by $.fs.exists, called only after a failure.
async function readRuns(
  $: any,
  v: PaneView,
  now: number,
): Promise<{ runs: PaneDelegate[]; finalRuns: Record<string, PaneDelegate>; lostRuns: Record<string, PaneDelegate>; mapNote: string }> {
  const exists = async (path: string): Promise<boolean | undefined> => {
    try {
      return Boolean(await $.fs.exists(path))
    } catch {
      return undefined
    }
  }
  let names: string[]
  try {
    names = ((await $.fs.list(RUN_ROOT)) as Array<{ name: string; kind: string }>).filter(x => x.kind === 'dir').map(x => x.name)
  } catch (err) {
    // No run root: no dispatch has run in this cwd yet. Nothing to draw, nothing to say.
    if ((await exists(RUN_ROOT)) === false) return { runs: [], finalRuns: v.finalRuns, lostRuns: v.lostRuns, mapNote: '' }
    // The root is there (or unknown) but the list failed: keep the dispatch markers already known, say only that.
    const known = v.delegates.filter(d => d.source === 'dispatch')
    return { runs: known, finalRuns: v.finalRuns, lostRuns: v.lostRuns, mapNote: `dispatch runs not listed: ${String((err as Error)?.message ?? err)}; showing last known` }
  }
  const runs: PaneDelegate[] = []
  const finalRuns: Record<string, PaneDelegate> = {}
  const lostRuns: Record<string, PaneDelegate> = {}
  const newestOf = async (dir: string, name: string): Promise<number | undefined> => {
    try {
      const files = ((await $.fs.list(dir)) as Array<{ kind: string; mtimeMs: number }>).filter(x => x.kind === 'file')
      if (!files.length) return dirTime(name)
      return Math.max(...files.map(f => Number(f.mtimeMs) || 0))
    } catch {
      return undefined
    }
  }
  const unreadable: string[] = []
  // undefined: missing (normal before the first write); a read that fails on a file that exists is noted.
  const attempt = async (path: string): Promise<string | undefined> => {
    try {
      return (await $.fs.read(path)) as string
    } catch {
      if ((await exists(path)) !== false) unreadable.push(path.slice(RUN_ROOT.length + 1))
      return undefined
    }
  }
  for (const name of sessionRuns(names, v.sessionStart)) {
    const cached = v.finalRuns[name]
    if (cached) {
      runs.push(cached)
      finalRuns[name] = cached
      continue
    }
    const dir = `${RUN_ROOT}/${name}`
    // Last event (FR-012): the newest mtimeMs among the run's files, from one $.fs.list of the run dir (the listing
    // reads a regular file's time in its one call). No file yet: the run id's start time. A failed list: unknown,
    // and a run whose last event is unknown is never called lost.
    const newest = await newestOf(dir, name)
    // A lost run is not read again until one of its files changes; the list above still notices that.
    const lost = v.lostRuns[name]
    if (lost && newest !== undefined && lost.newest !== undefined && newest <= lost.newest) {
      runs.push(lost)
      lostRuns[name] = lost
      continue
    }
    const runJson = await attempt(`${dir}/run.json`)
    if (isDryRun(runJson)) continue
    const slotsJson = await attempt(`${dir}/slots.json`)
    const events = runJson === undefined ? await attempt(`${dir}/events.jsonl`) : undefined
    // Draw from what was read; a folder with no file yet draws from its name (model from the dir, state running).
    // Start: the run id's stamp. End (a final run): its newest file time.
    const r0 = runFromFiles(runJson, slotsJson, name, events)
    const startedAt = dirTime(name)
    const read1 = { ...r0, startedAt, ...(r0.state !== 'running' && newest !== undefined ? { endedAt: newest } : {}) }
    // A failed run's alert event is named by its last event, stable across reloads and resumes.
    const d = withLost(read1.state === 'failed' ? { ...read1, alertAt: newest ?? dirTime(name) ?? 0 } : read1, newest, now)
    runs.push(d)
    if (d.state === 'lost') lostRuns[name] = d
    else if (d.state !== 'running') finalRuns[name] = d
  }
  const mapNote = unreadable.length
    ? `dispatch run file unreadable: ${unreadable[0]}${unreadable.length > 1 ? ` (+${unreadable.length - 1} more)` : ''}; drawn from what was read`
    : ''
  return { runs, finalRuns, lostRuns, mapNote }
}

const subagentDelegate = (a: PaneAgent): PaneDelegate => {
  const rung = rungOf('', a.type)
  return {
    id: a.id,
    source: 'subagent',
    nickname: a.type.replace(PREFIX, ''),
    rung,
    task: a.description,
    category: categoryOf({ text: a.description, subagentType: a.type, rung }),
    state: lifecycleOf('subagent', a.status),
    ...(a.parentId ? { parentId: a.parentId } : {}),
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
export const cosLabel = (v: PaneView, room = Infinity): string => {
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
  let agents: PaneAgent[] = []
  let mapSubs: PaneAgent[] = [] // every subagent type of this session, for the map only
  let lastSig = ''
  on('session.start', async ($, e, next) => {
    agents = []
    mapSubs = []
    lastSig = ''
    stopMotion()
    motion.off = false
    motion.seen = {}
    motion.returns = []
    const nowIso = new Date(await $.clock.now()).toISOString()
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
    // sessionStart, acked and finalRuns survive a reload: sessionStart is set once. After `--resume` $.state is empty:
    // this session's $.store record (FR-013) gives back its start, acks and subagent alert times.
    const saved = normalizeView(await read($, view)).sessionStart ? undefined : await loadSaved($)
    const started = await update($, view, v => {
      const n = normalizeView(v)
      const restored = !n.sessionStart && saved ? { sessionStart: saved.sessionStart, acked: saved.acked ?? {}, alertAt: saved.alertAt ?? {} } : {}
      return { ...n, ...restored, types, agents: [], note, delegates: [], mapNote: '', sessionStart: (restored as any).sessionStart || n.sessionStart || nowIso }
    })
    await save($, normalizeView(started as PaneView))

    $.clock.every(POLL_MS, async () => {
      try {
        const listed = (await $.agent.list()) as Listed[]
        agents = mergeAgents(agents, listed)
        mapSubs = mergeAgents(mapSubs, listed, t => typeof t === 'string', Infinity)
        const v = normalizeView(await read($, view))
        const now = Number(await $.clock.now())
        const { runs, finalRuns, lostRuns, mapNote } = await readRuns($, v, now)
        // A subagent's failure episode starts when the pane first sees it failed; it ends when the agent leaves failed
        // (a resumed agent runs again), so a later failure under the same id is a new event (FR-008).
        const alertAt: Record<string, number> = {}
        // Feed times: a subagent starts at the first poll that lists it and ends at the first poll that sees it end
        // (done or failed; paused is not an end).
        const seen: Record<string, [number, number | null]> = {}
        const subs = mapSubs.map(a => {
          const d0 = subagentDelegate(a)
          const was = v.seen[d0.id]
          const ended = d0.state === 'done' || isAlert(d0.state)
          const times: [number, number | null] = [was?.[0] ?? now, ended ? (was?.[1] ?? now) : null]
          seen[d0.id] = times
          const d = { ...d0, startedAt: times[0], ...(times[1] !== null ? { endedAt: times[1] } : {}) }
          if (!isAlert(d.state)) return d
          alertAt[d.id] = v.alertAt[d.id] ?? now
          return { ...d, alertAt: alertAt[d.id] }
        })
        let model = v.model
        try {
          model = String((await $.session.model()) ?? '')
        } catch {
          // no model known: the centre shows its fixed label only
        }
        const delegates = [...subs, ...runs]
        const sig = JSON.stringify([agents.map(a => [a.id, a.status]), delegates, mapNote, model])
        if (sig !== lastSig) {
          lastSig = sig
          const alertsMoved = JSON.stringify(alertAt) !== JSON.stringify(v.alertAt)
          const next1 = await update($, view, x => ({ ...normalizeView(x), agents, delegates, finalRuns, lostRuns, alertAt, mapNote, model, seen }))
          if (alertsMoved) await save($, normalizeView(next1 as PaneView))
        }
      } catch (err) {
        await update($, view, v => ({ ...normalizeView(v), note: `pane error: ${String((err as Error)?.message ?? err)}` }))
      }
    })
    return next(e)
  })

  on('ui.close', ($, e, next) => {
    if (e.id === PANE) stopMotion()
    return next(e)
  })

  on('command.run', { command: 'delegate-pane' }, async $ => {
    motion.off = false
    await $.ui.open({ id: PANE, title: 'agents-inc native agents' })
    return { text: 'agents-inc pane opened.' }
  })

  on('ui.render', { component: 'Pane' }, async ($, e) => {
    if (String((e as any).requestId ?? '') !== PANE) return undefined
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
    motion.cols = (e as any).surface === 'terminal' && !motion.off && els.Raster ? rasterColumns(columns) : 0
    let now = 0
    try {
      now = Number(await $.clock.now())
    } catch {
      // no clock: the first frame draws at time 0
    }
    track(v.delegates, now)
    const dispatches = dispatchesOf(v.delegates, now)
    if (motion.cols && needsMotion(sts, motion.returns, now, dispatches)) startMotion($)
    else stopMotion()
    const raster = motion.cols ? (
      <els.Raster key="map" columns={motion.cols} rows={RASTER_ROWS} cells={encodeCells(frame(sts, now, motion.cols, RASTER_ROWS, motion.returns, { cos: cosLabel(v, cosRoom(motion.cols)), dispatches }))} />
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
        <Text> </Text>
        <Text bold>Mission map</Text>
        {map}
        {v.delegates.length ? null : <Text dimColor>no delegates</Text>}
        <Text bold>{statusLine(v.delegates, columns)}</Text>
        {feed(v.delegates, columns, feedCap).map(row => (
          <Text key={'feed-' + row.id} color={row.kind === 'running' ? 'yellow' : row.kind === 'failed' ? 'red' : undefined} dimColor={row.kind === 'done' || row.kind === 'paused'}>
            {row.lead}
            {row.roleCol ? <Text dimColor>{row.roleCol}</Text> : null}
            {row.tail}
          </Text>
        ))}
        {v.mapNote ? <Text dimColor>{v.mapNote}</Text> : null}
      </Box>
    )
  })
}
