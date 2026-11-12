export type PaneAgent = { id: string; type: string; description: string; status: string }
export type PaneView = { types: string[]; agents: PaneAgent[]; note: string }

declare module 'claude-code' {
  interface PluginState {
    'delegate-pane': { view: Shaped<PaneView> }
  }
}
