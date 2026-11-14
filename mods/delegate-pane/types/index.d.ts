export type PaneAgent = { id: string; type: string; description: string; status: string; parentId?: string }
export type PaneDelegate = {
  id: string
  source: 'subagent' | 'dispatch'
  nickname: string
  rung: string
  task: string
  category: 'Review' | 'Build' | 'Write' | 'Scout' | 'Plan' | 'Other'
  state: 'running' | 'review' | 'done' | 'failed' | 'paused' | 'lost'
  alertAt?: number
  newest?: number
  startedAt?: number
  endedAt?: number
  parentId?: string
}
export type TreeRow = { n: number; depth: number; kind: 'agent' | 'run' | 'job'; id: string; label: string; state: string; meta?: string; note?: string }
// run dir name -> session-style lines of its open run pane, and a note
export type RunLines = Record<string, { lines: string[]; note: string }>
export type Form = { model: string; effort: string; note: string; target: string; targetLabel: string }
export type PaneView = {
  note: string
  // Spec 040 delegation tree.
  treeRows: TreeRow[]
  summary: string
  controlsOpen: boolean
  // Spec 039 mission map.
  delegates: PaneDelegate[]
  // station -> ack keys `<id>@<alertAt>`: one key per acknowledged failure or lost event
  acked: Record<string, string[]>
  // subagent id -> when its current failure episode was first seen (ms)
  alertAt: Record<string, number>
  sessionStart: string
  finalRuns: Record<string, PaneDelegate>
  // run dir -> its lost delegate, kept so a lost run is re-read only when one of its files changes
  lostRuns: Record<string, PaneDelegate>
  mapNote: string
  // the main session's model ($.session.model()), '' when not known; the map centre's second line
  model: string
  // subagent id -> [first poll that listed it, first poll that saw it end or null] (ms): feed order and durations
  seen: Record<string, [number, number | null]>
}

declare module 'claude-code' {
  interface PluginState {
    'delegate-pane': { view: Shaped<PaneView>; runs: Shaped<RunLines>; form: Shaped<Form> }
  }
}
