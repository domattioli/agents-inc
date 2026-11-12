import type { Register } from 'claude-code'
import { register as relay, registerRelay } from './relay'
import { registerLunaAgent } from './luna'
import { register as native, registerNativeAgents } from './native/registry'

// hooks.json allows one hooks module per plugin, and a module may register session.start once,
// so this entry owns session.start and hands it to every feature.
export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    await registerLunaAgent($, e)
    const legacyRoutes = await registerNativeAgents($, e)
    await registerRelay($, e, legacyRoutes)
    return next(e)
  })
  relay(on, options)
  // One set of loop hooks for luna and every guest type: the engine allows one registration per event.
  native(on, options)
}
