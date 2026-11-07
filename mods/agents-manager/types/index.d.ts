// meta: model and effort (run rows) or agent type and vendor (agent rows), shown in the delegation graph.
export type Row = { n: number; depth: number; kind: 'agent' | 'run'; id: string; label: string; state: string; meta?: string }
export type ManagerView = { rows: Row[]; note: string }
// Session-style lines per open run pane, keyed by run dir name.
export type RunLines = Record<string, { lines: string[]; note: string }>
// The new-agent form: picked model and effort, and the last spawn's result.
export type Form = { model: string; effort: string; note: string }

declare module 'claude-code' {
  interface PluginState {
    'agents-manager': { view: Shaped<ManagerView>; runs: Shaped<RunLines>; form: Shaped<Form> }
  }
}
