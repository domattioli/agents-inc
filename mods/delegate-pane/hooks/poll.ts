import type { PaneAgent, PaneDelegate } from '../types'
import { categoryOf, dirTime, isAlert, isDryRun, lifecycleOf, runFromFiles, rungOf, sessionRuns, withLost } from './mission'
import { PRE_CAP, RUNS, STALE_MS, STAMP, agentRows, describe, isFreeRun, parse, runTitle, stampOf, treeRuns } from './tree'
import type { PaneState, RunDelegate, TreeRow, View } from './tree'

const PREFIX = 'agents-inc:'

export type Listed = { id: string; type?: string; name?: string; description?: string; status?: string; parentId?: string }

// What one poll found. The caller writes it to the view; the poll itself writes nothing but the PaneState it is given.
export type PollResult = {
  // the map's delegates: every subagent of the session, then every dispatch run of the session
  delegates: PaneDelegate[]
  finalRuns: Record<string, PaneDelegate>
  lostRuns: Record<string, PaneDelegate>
  alertAt: Record<string, number>
  seen: Record<string, [number, number | null]>
  mapNote: string
  model: string
  // tree rows without the job rows (the same rows are in `PaneState.base`), and the run count line
  rows: TreeRow[]
  summary: string
  // session-style lines of every open run pane, by run dir name
  runLines: Record<string, string[]>
  // agent ids the engine listed
  agentIds: string[]
}

// Merge one agent.list answer into the session's agents, by agent id. An agent the engine no longer lists stays,
// marked finished unless it already ended: the map keeps every subagent of the session (FR-003).
export function mergeAgents(prev: PaneAgent[], listed: Listed[]): PaneAgent[] {
  const now = new Map(listed.filter(a => a && typeof a.type === 'string').map(a => [a.id, a] as const))
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
  return out
}

export const subagentDelegate = (a: PaneAgent): PaneDelegate => {
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

type RunScan = {
  runs: PaneDelegate[]
  finalRuns: Record<string, PaneDelegate>
  lostRuns: Record<string, PaneDelegate>
  mapNote: string
  runRows: TreeRow[]
  slotsSeen: string[]
  names: Set<string>
}

// One poll of the run root: one list, then run files only for runs that are not yet final (plan R1 bound).
// A failed read is told apart from a missing file by $.fs.exists, called only after a failure.
// Runs of this session feed the map and the tree; older run dirs (the newest PRE_CAP) feed the tree only, so a run
// that is still running stays listed however old it is.
async function readRuns($: any, st: PaneState, v: View, now: number): Promise<RunScan> {
  const exists = async (path: string): Promise<boolean | undefined> => {
    try {
      return Boolean(await $.fs.exists(path))
    } catch {
      return undefined
    }
  }
  const none: RunScan = { runs: [], finalRuns: v.finalRuns, lostRuns: v.lostRuns, mapNote: '', runRows: [], slotsSeen: [], names: new Set() }
  let names: string[]
  try {
    names = ((await $.fs.list(RUNS)) as Array<{ name: string; kind: string }>).filter(x => x.kind === 'dir').map(x => x.name)
  } catch (err) {
    // No run root: no dispatch has run in this cwd yet. Nothing to draw, nothing to say.
    if ((await exists(RUNS)) === false) return none
    // The root is there (or unknown) but the list failed: keep the dispatch markers already known, say only that.
    const known = v.delegates.filter(d => d.source === 'dispatch')
    return { ...none, runs: known, mapNote: `dispatch runs not listed: ${String((err as Error)?.message ?? err)}; showing last known` }
  }
  // One entry per run dir name.
  names = names.filter((n, i) => names.indexOf(n) === i)
  const runs: PaneDelegate[] = []
  const finalRuns: Record<string, PaneDelegate> = {}
  const lostRuns: Record<string, PaneDelegate> = {}
  const runRows: TreeRow[] = []
  const slotsSeen: string[] = []
  const unreadable: string[] = []
  // undefined: missing (normal before the first write); a read that fails on a file that exists is noted.
  const attempt = async (path: string): Promise<string | undefined> => {
    try {
      return (await $.fs.read(path)) as string
    } catch {
      if ((await exists(path)) !== false) unreadable.push(path.slice(RUNS.length + 1))
      return undefined
    }
  }
  const quiet = async (path: string): Promise<string | undefined> => {
    try {
      return (await $.fs.read(path)) as string
    } catch {
      return undefined
    }
  }
  const sess = sessionRuns(names, v.sessionStart)
  const inSession = new Set(sess)
  const pre = names.filter(n => !inSession.has(n) && STAMP.test(n) && dirTime(n) !== undefined).sort().reverse().slice(0, PRE_CAP)
  for (const name of [...sess, ...pre]) {
    const mine = inSession.has(name)
    const dir = `${RUNS}/${name}`
    const row = (d: RunDelegate, state: string): void => {
      runRows.push({ n: 0, depth: 1, kind: 'run', id: name, label: runTitle(name), state, meta: d.meta ?? name.split('-')[1] ?? '' })
      if (d.slots) slotsSeen.push(d.slots)
      const at = typeof d.endedAt === 'number' ? d.endedAt : undefined
      if (at !== undefined) st.at.set(name, at)
    }
    const again = st.resumed.has(name)
    const cached = v.finalRuns[name] as RunDelegate | undefined
    if (cached && !again) {
      if (mine) runs.push(cached)
      finalRuns[name] = cached
      row(cached, cached.state)
      continue
    }
    // Last event (FR-012): the newest mtimeMs among the run's files, from one $.fs.list of the run dir (the listing
    // reads a regular file's time in its one call). No file yet: the run id's start time. A failed list: unknown,
    // and a run whose last event is unknown is never called lost.
    let files: Array<{ name: string; kind: string; mtimeMs: number }> | undefined
    try {
      files = ((await $.fs.list(dir)) as Array<{ name: string; kind: string; mtimeMs: number }>).filter(x => x.kind === 'file')
    } catch {
      files = undefined
    }
    const newest = files === undefined ? undefined : files.length ? Math.max(...files.map(f => Number(f.mtimeMs) || 0)) : dirTime(name)
    // A lost run is not read again until one of its files changes; the list above still notices that.
    const lost = v.lostRuns[name] as RunDelegate | undefined
    if (mine && !again && lost && newest !== undefined && lost.newest !== undefined && newest <= lost.newest) {
      runs.push(lost)
      lostRuns[name] = lost
      row(lost, 'lost')
      continue
    }
    const runJson = await attempt(`${dir}/run.json`)
    if (isDryRun(runJson)) continue
    const slotsJson = await attempt(`${dir}/slots.json`)
    let events = runJson === undefined ? await attempt(`${dir}/events.jsonl`) : undefined
    // Draw from what was read; a folder with no file yet draws from its name (model from the dir, state running).
    const r0 = runFromFiles(runJson, slotsJson, name, events)
    // A run whose run.json still says running (a free run writes none) is judged by its events.jsonl run.end row.
    let state: PaneDelegate['state'] = r0.state
    if (state === 'running') {
      events = events ?? (await quiet(`${dir}/events.jsonl`))
      const rows = events === undefined ? [] : parse(events)
      const end = [...rows].reverse().find((x: any) => x?.event?.type === 'run.end')
      if (end) state = lifecycleOf('dispatch', String(end.event.outcome ?? 'done'))
    }
    let meta = name.split('-')[1] ?? ''
    let slots = ''
    try {
      const rj = JSON.parse(runJson as string)
      meta = `${rj.model ?? meta}${rj.effort ? ' · ' + rj.effort : ''} · ${rj.kind === 'free' ? (rj.via === 'agent.sh' ? 'agent.sh' : 'free dispatch') : 'dispatch'}`
      if (typeof rj.slots === 'string') slots = rj.slots
    } catch {
      // no readable run.json: the model from the dir name, no suffix
    }
    // Start: the run id's stamp. End (a final run): its newest file time.
    const read1: RunDelegate = {
      ...r0, state, meta, ...(slots ? { slots } : {}), startedAt: dirTime(name),
      ...(state !== 'running' && newest !== undefined ? { endedAt: newest } : {}),
    }
    let d: RunDelegate = read1
    if (mine) {
      // A failed run's alert event is named by its last event, stable across reloads and resumes.
      d = withLost(read1.state === 'failed' ? { ...read1, alertAt: newest ?? dirTime(name) ?? 0 } : read1, newest, now) as RunDelegate
      runs.push(d)
    }
    if (d.state === 'lost') lostRuns[name] = d
    // A final run is cached only when its files were listed: no file times, no way to notice a change, so it is read again.
    else if (d.state !== 'running' && files !== undefined && files.length > 0) finalRuns[name] = d
    st.resumed.delete(name)
    // A pre-session run with no event for 30 minutes died without closing: stale, not running. Unknown times never make it stale.
    const moved = files?.find(f => f.name === 'events.jsonl')?.mtimeMs
    if (typeof moved === 'number' && moved > 0) st.at.set(name, moved)
    const stale = !mine && d.state === 'running' && typeof moved === 'number' && moved > 0 && now - moved > STALE_MS
    row(d, stale ? 'stale' : d.state)
  }
  const mapNote = unreadable.length
    ? `dispatch run file unreadable: ${unreadable[0]}${unreadable.length > 1 ? ` (+${unreadable.length - 1} more)` : ''}; drawn from what was read`
    : ''
  runRows.sort((a, b) => (a.id < b.id ? 1 : a.id > b.id ? -1 : 0))
  return { runs, finalRuns, lostRuns, mapNote, runRows, slotsSeen, names: new Set(names) }
}

// Lines of the run panes the person has open: events as session-style lines; a free run's reply (stdout.md, stderr.txt
// when it failed) is read once, and again only while the run is failed.
async function openLines($: any, st: PaneState, scan: RunScan): Promise<Record<string, string[]>> {
  const out: Record<string, string[]> = {}
  for (const name of st.open) {
    if (!scan.names.has(name)) continue
    const dir = `${RUNS}/${name}`
    let text = ''
    try {
      text = (await $.fs.read(`${dir}/events.jsonl`)) as string
    } catch {
      text = ''
    }
    const rows = parse(text)
    const lines = rows.map(describe).filter(Boolean)
    const row = scan.runRows.find(r => r.id === name)
    if (row && isFreeRun(row)) {
      const failed = row.state === 'failed' || row.state === 'red'
      let body = st.tails.get(name)
      if (!body || failed) {
        let reply = ''
        try {
          reply = (await $.fs.read(`${dir}/stdout.md`)) as string
        } catch {
          reply = ''
        }
        if (!reply.trim()) {
          try {
            reply = (await $.fs.read(`${dir}/stderr.txt`)) as string
          } catch {
            reply = ''
          }
        }
        body = reply.split('\n').filter(l => l.trim())
        st.tails.set(name, body)
      }
      if (body.length) lines.splice(Math.max(0, lines.length - 1), 0, '● ' + body[0], ...body.slice(1).map(l => '  ' + l))
    }
    out[name] = lines
  }
  return out
}

// The one poll: agents, run dirs and the delegates of the map, in one pass over the run root.
export async function poll($: any, st: PaneState, v: View, now: number): Promise<PollResult> {
  const listed = (await $.agent.list()) as Listed[]
  st.mapSubs = mergeAgents(st.mapSubs, listed)
  const rows: TreeRow[] = agentRows(listed)
  const scan = await readRuns($, st, v, now)
  const { shown, summary } = treeRuns(scan.runRows, st.at, stampOf(v.sessionStart), now)
  rows.push(...shown)

  // A job row ends once the real thing appears in the lists: a new agent (native) or a run dir with its slots path (dispatch).
  const claimed = new Set<string>()
  for (const j of [...st.jobs.values()]) {
    if (j.kind === 'native' && j.state !== 'failed') {
      const fresh = listed.find(a => !j.before.has(a.id) && !claimed.has(a.id))
      if (fresh) {
        claimed.add(fresh.id)
        st.jobs.delete(j.stamp)
      }
    } else if (j.kind !== 'native' && scan.slotsSeen.some(s => s.includes(`/${j.stamp}/`))) st.jobs.delete(j.stamp)
  }
  st.lastAgents = new Set(listed.map(a => a.id))
  st.base = rows
  st.summary = summary

  // A subagent's failure episode starts when the pane first sees it failed; it ends when the agent leaves failed
  // (a resumed agent runs again), so a later failure under the same id is a new event (FR-008).
  const alertAt: Record<string, number> = {}
  // Feed times: a subagent starts at the first poll that lists it and ends at the first poll that sees it end
  // (done or failed; paused is not an end).
  const seen: Record<string, [number, number | null]> = {}
  const subs = st.mapSubs.map(a => {
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
  return {
    delegates: [...subs, ...scan.runs], finalRuns: scan.finalRuns, lostRuns: scan.lostRuns, alertAt, seen, mapNote: scan.mapNote, model,
    rows, summary, runLines: await openLines($, st, scan), agentIds: listed.map(a => a.id),
  }
}
