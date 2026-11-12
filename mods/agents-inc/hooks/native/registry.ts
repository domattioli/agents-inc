// Spec 038 T027: the guest agent types beyond luna. Session start reads every model in one `agents-inc native status
// --json` call (files only: no provider request, SC-006) and registers one type per offered model; each type's offer
// hook is its loop's (registerLoop). The set of adapters is fixed at load, because the engine binds hooks then.
import type { Register } from 'claude-code'
import type { Adapter } from './adapter'
import { CODEX_ADAPTERS, codexAdapter } from './codex'
import { HTTP_ADAPTERS } from './http'
import { registerAgent, registerLoops, type Status } from './loop'

// Every guest type registered from the one status read: the Codex nicknames beyond luna (luna registers through its
// own status verb, luna.ts) and one adapter per free nickname in agents_inc/models.json (Gemini, Mistral, OpenRouter).
export const ADAPTERS: readonly Adapter[] = [...CODEX_ADAPTERS.filter(a => a !== codexAdapter), ...HTTP_ADAPTERS]

type Spawn = { argv: string[]; cwd?: string }
type Chunk = { stream: 'stdout' | 'stderr'; text: string }
type Native$ = Parameters<typeof registerAgent>[0] & {
  process: { spawn: (a: Spawn) => AsyncGenerator<Chunk, { code: number | null }> }
}
type ModelStatus = Status & { nickname: string }

// A function declaration with `$` first: the engine follows `$` past an import only into one.
export async function readNativeStatus($: Native$, cwd: string): Promise<ModelStatus[] | null> {
  return (await readStatusReport($, cwd)).models
}

// The whole status answer: the models, and legacy_routes (spec 038 FR-016: true only after install --legacy-routes).
export async function readStatusReport($: Native$, cwd: string): Promise<{ models: ModelStatus[] | null; legacyRoutes: boolean }> {
  const none = { models: null, legacyRoutes: false }
  try {
    // `luna status --all` (same answer as `native status --json`): a luna verb, so hosts and fakes that already allow
    // the luna status call need no new rule.
    const stream = $.process.spawn({ argv: ['agents-inc', 'luna', 'status', '--json', '--all', '--cwd', cwd || '.'], cwd: cwd || undefined })
    let out = ''
    for (;;) {
      const n = await stream.next()
      if (n.done) {
        if (n.value.code !== 0) return none
        break
      }
      if (n.value.stream === 'stdout') out += n.value.text
    }
    const report = JSON.parse(out) as { models?: unknown; legacy_routes?: unknown }
    const models = report.models
    return {
      models: Array.isArray(models) ? (models as ModelStatus[]).filter(m => m && typeof m.nickname === 'string') : null,
      legacyRoutes: report.legacy_routes === true,
    }
  } catch {
    return none
  }
}

// Returns legacy_routes from the same read, so mod.ts registers the relay route only when it is kept.
export async function registerNativeAgents($: Native$, e: { cwd: string }): Promise<boolean> {
  const { models, legacyRoutes } = await readStatusReport($, e.cwd)
  if (models === null) $.ui.log('agents-inc native: not registered: agents-inc native status gave no usable answer', { to: 'debug' })
  for (const adapter of ADAPTERS) {
    const m = models?.find(x => x.nickname === adapter.nickname)
    // No entry: null, so the loop logs "no usable answer" and registers nothing; it never asks again.
    const known = m && typeof m.offered === 'boolean' && typeof m.slug === 'string' ? m : null
    await registerAgent($, adapter, e, known)
  }
  return legacyRoutes
}

// The engine reads `register` from source: a const function that passes `on` only to an imported function.
// One registration per event for every native type, luna included (luna.ts's own register is no longer called by mod.ts).
export const register: Register = on => {
  registerLoops(on, [codexAdapter, ...ADAPTERS])
}
