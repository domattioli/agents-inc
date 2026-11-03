import type { Register } from 'claude-code'
import { register as relay, registerRelay } from './relay'
import { register as luna, registerLunaAgent } from './luna'

// hooks.json allows one hooks module per plugin, and a module may register session.start once,
// so this entry owns session.start and hands it to both features.
export const register: Register = (on, options) => {
  on('session.start', async ($, e, next) => {
    await registerRelay($, e)
    await registerLunaAgent($, e)
    return next(e)
  })
  relay(on, options)
  luna(on, options)
}
