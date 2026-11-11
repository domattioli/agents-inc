export type PaneView = { run: string; lines: string[] }

declare module 'claude-code' {
  interface PluginState {
    'delegate-pane': { views: Shaped<Record<string, PaneView>> }
  }
}
