export type PaneView = { run: string; lines: string[] }

declare module 'claude-code' {
  interface PluginState {
    'luna-pane': { luna: Shaped<PaneView>; haiku: Shaped<PaneView> }
  }
}
