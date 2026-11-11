// Spec 038 slice 1: luna is the shared step loop (native/loop.ts) driven by the Codex adapter (native/codex.ts).
// This file keeps the import path mod.ts and luna.test.ts use and holds no step logic.
import type { Register } from 'claude-code'
import { codexAdapter } from './native/codex'
import { registerAgent, registerLoop } from './native/loop'

export * from './native/loop'

type AgentArgs = Parameters<typeof registerAgent>
// A function declaration: the engine follows `$` past an import only into one.
export function registerLunaAgent($: AgentArgs[0], e: AgentArgs[2]): Promise<void> {
  return registerAgent($, codexAdapter, e)
}

// The engine reads `register` from source: a const function that passes `on` only to an imported function.
export const register: Register = on => {
  registerLoop(on, codexAdapter)
}
