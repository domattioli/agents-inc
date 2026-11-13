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
export type PaneView = {
  types: string[]
  agents: PaneAgent[]
  note: string
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
    'delegate-pane': { view: Shaped<PaneView> }
  }
}
