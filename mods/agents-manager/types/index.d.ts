// meta: model and effort (run rows) or agent type and vendor (agent rows), shown in the delegation graph.
// A 'job' row is a start the pane itself made (id = launch stamp); note holds its exit code and last output line.
export type Row = { n: number; depth: number; kind: 'agent' | 'run' | 'job'; id: string; label: string; state: string; meta?: string; note?: string }
// summary: 'N running · M finished (showing K)' for the run rows.
export type ManagerView = { rows: Row[]; note: string; summary: string }
// Session-style lines per open run pane, keyed by run dir name.
export type RunLines = Record<string, { lines: string[]; note: string }>
// The new-agent form: picked model and effort, the message target ('<kind>:<id>', '' = first row) with its label, and a short note.
export type Form = { model: string; effort: string; note: string; target: string; targetLabel: string }

declare module 'claude-code' {
  interface PluginState {
    'agents-manager': { view: Shaped<ManagerView>; runs: Shaped<RunLines>; form: Shaped<Form> }
  }
}
