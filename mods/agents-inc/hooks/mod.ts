import type { Register } from 'claude-code'
import { register as relay, registerRelay } from './relay'
import { registerLunaAgent } from './luna'
import { register as native, registerNativeAgents } from './native/registry'
import { register as boardPane, PANE as BOARD_PANE, POLL_MS as BOARD_POLL_MS, TITLE as BOARD_TITLE } from './board'
import { liveTeams, parseTeam, summary, teamKey, TEAM_PREFIX } from './board-teams'
import { board, buildBoard, dirTime, hasActivity, ingestAgents, noteStep, resetMem, RUNS as BOARD_RUNS, runFrom, sessionRunNames, stepDue } from './board-model'

// hooks.json allows one hooks module per plugin, and a module may register session.start once,
// so this entry owns session.start and hands it to every feature.
// The Board poll of this process: one at a time. A new session.start or the session's end cancels the previous interval,
// and a callback already in flight sees a newer generation and does nothing more.
let stopPoll: unknown
let pollGen = 0
// The host hands back a function; accept a { cancel } handle too. The generation check stops a callback either way.
const cancelPoll = (h: unknown): void => {
  if (typeof h === 'function') h()
  else if (h && typeof (h as { cancel?: unknown }).cancel === 'function') (h as { cancel: () => void }).cancel()
}

export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    await registerLunaAgent($, e)
    // Board (spec 050): the one poll behind the pane. `$` calls stay inline here (host loader rule); every decision is a
    // pure function in board-model.ts. Zero model calls: the agent list, transcript tails and dispatch run files only.
    resetMem(board)
    board.teamName = String((e as any).cwd ?? '').split('/').filter(Boolean).pop() ?? ''
    try {
      await $.command.register({ name: 'board', description: 'Open the Board: what needs you, trouble, and what each delegate is doing' })
    } catch {
      // the command stays unregistered; the pane still opens on its first event
    }
    for (const [name, description] of [
      ['board-send', 'Send text to another Team\'s Chief: /board-send <teamRef> <text> (Board fills the ref)'],
      ['board-memo', 'Send a Memo to one of your own delegates: /board-memo <agentRef> <text>'],
      ['board-tell', 'Ask another Team\'s Chief to tell its delegate: /board-tell <teamRef> <delegate> <text>'],
    ] as const) {
      try {
        await $.command.register({ name, description })
      } catch {
        // an unregistered command only means the operator cannot type it
      }
    }
    cancelPoll(stopPoll)
    const mine = ++pollGen
    stopPoll = $.clock.every(BOARD_POLL_MS, async () => {
      if (mine !== pollGen || board.busy) return
      board.busy = true
      try {
        const now = Number(await $.clock.now())
        if (!board.start) board.start = now
        let listed: any[] = []
        try {
          listed = ((await $.agent.list()) as any[]) ?? []
        } catch {
          listed = []
        }
        if (mine !== pollGen) return
        ingestAgents(board, listed, now)
        for (const a of listed) {
          if (a.status !== 'running' || !stepDue(board, a.id, now)) continue
          try {
            const msgs = await $.session.messages({ agentId: a.id, as: 'api' })
            noteStep(board, a.id, msgs && typeof msgs === 'object' && 'deny' in (msgs as object) ? undefined : msgs, now)
          } catch {
            noteStep(board, a.id, undefined, now)
          }
        }
        let names: string[] = []
        try {
          names = ((await $.fs.list(BOARD_RUNS)) as Array<{ name: string; kind: string }>).filter(x => x.kind === 'dir').map(x => x.name)
        } catch {
          names = []
        }
        for (const name of sessionRunNames(names, board.start)) {
          let newest: number | undefined
          try {
            const files = ((await $.fs.list(`${BOARD_RUNS}/${name}`)) as Array<{ kind: string; mtimeMs: number }>).filter(x => x.kind === 'file')
            newest = files.length ? Math.max(...files.map(f => Number(f.mtimeMs) || 0)) : dirTime(name)
          } catch {
            newest = undefined
          }
          const had = board.runs[name]
          if (had && newest !== undefined && newest <= had.newest) continue
          let runJson: string | undefined
          let slotsJson: string | undefined
          let events: string | undefined
          try {
            runJson = (await $.fs.read(`${BOARD_RUNS}/${name}/run.json`)) as string
          } catch {
            runJson = undefined
          }
          try {
            slotsJson = (await $.fs.read(`${BOARD_RUNS}/${name}/slots.json`)) as string
          } catch {
            slotsJson = undefined
          }
          if (runJson === undefined) {
            try {
              events = (await $.fs.read(`${BOARD_RUNS}/${name}/events.jsonl`)) as string
            } catch {
              events = undefined
            }
          }
          board.runs[name] = runFrom(name, { runJson, slotsJson, events }, newest)
        }
        // Teams across sessions (spec 050 Phase 3): publish this session's own key, read the others, ignore stale heartbeats.
        // Never a shared counter: each key has one writer. Own Team is always the open one.
        try {
          if (mine !== pollGen) return
          if (!board.sessionId) board.sessionId = String(await $.session.id())
          const prior = buildBoard(board, now)
          await $.store.set(teamKey(board.sessionId), summary(board.sessionId, board.teamName, prior.needs.length, prior.working.length, now))
          if (mine !== pollGen) return
          const all: Array<[string, ReturnType<typeof parseTeam>]> = []
          for (const k of (await $.store.keys()) as string[]) {
            if (k.startsWith(TEAM_PREFIX) && k !== teamKey(board.sessionId)) all.push([k, parseTeam(k, await $.store.get(k))])
          }
          if (mine !== pollGen) return
          board.teams = liveTeams(all.map(x => x[1]), board.sessionId, now)
          // Never delete another session's key: readers only ignore stale or malformed peers (S1: one writer per key).
        } catch {
          board.teams = [] // the store is unreadable: show no other Teams rather than stale ones
        }
        if (mine !== pollGen) return
        const built = buildBoard(board, now)
        const sig = JSON.stringify(built)
        board.board = built
        if (sig !== board.sig) {
          board.sig = sig
          $.ui.invalidate('ui.render')
        }
        // Open without taking focus on the first delegate or first NEEDS YOU row; stay closed with nothing to show.
        if (!board.opened && !board.closedByPerson && hasActivity(built)) {
          board.opened = true
          await $.ui.open({ id: BOARD_PANE, title: BOARD_TITLE })
        }
      } catch {
        // one failed poll changes nothing: the next one runs
      } finally {
        if (mine === pollGen) board.busy = false
      }
    })
    const legacyRoutes = await registerNativeAgents($, e)
    await registerRelay($, e, legacyRoutes)
    return next(e)
  })
  // The session ends: stop polling and remove this session's own Team key (the only key it may delete).
  on('session.end', async ($, e, next) => {
    cancelPoll(stopPoll)
    stopPoll = undefined
    pollGen++
    if (board.sessionId) {
      try {
        await $.store.delete(teamKey(board.sessionId))
      } catch {
        // readers ignore the key once its heartbeat is stale
      }
    }
    return next(e)
  })
  relay(on, options)
  // One set of loop hooks for luna and every guest type: the engine allows one registration per event.
  native(on, options)
  boardPane(on, options)
}
