// Spec 038 T025 / T027: the stateless HTTP adapter's failure texts and the session-start registry. No provider, no network.
import { expect, test } from 'claude-code/testing'
import { classifyHttp, geminiFlash } from './http'
import { ADAPTERS, readNativeStatus, registerNativeAgents } from './registry'
import { CODEX_ADAPTERS, codexAdapter } from './codex'

test('the gemini adapter is stateless, key-store, and steps through agents-inc native step', () => {
  expect(geminiFlash.kind).toBe('stateless')
  expect(geminiFlash.auth).toBe('key-store')
  expect(geminiFlash.argv('gemini-3.8-flash' as never, { thread: '/t', cwd: '/w', timeoutS: 60 }))
    .toEqual(['agents-inc', 'native', 'step', '--model', 'gemini-flash', '--cwd', '/w', '--timeout', '60'])
  expect(ADAPTERS.map(a => a.nickname)).toContain('gemini-flash')
})

test('mistral and openrouter adapters step through agents-inc native step under their own nickname', () => {
  const byNick = new Map(ADAPTERS.map(a => [a.nickname, a]))
  for (const [nick, provider] of [['ministral', 'mistral'], ['codestral', 'mistral'], ['gemma-31b', 'openrouter'], ['nemotron-ultra', 'openrouter']] as const) {
    const a = byNick.get(nick)
    expect(a?.provider).toBe(provider)
    expect(a?.kind).toBe('stateless')
    expect(a?.auth).toBe('key-store')
    expect(a?.argv({} as never, { thread: '/t', cwd: '/w', timeoutS: null })).toEqual(['agents-inc', 'native', 'step', '--model', nick, '--cwd', '/w'])
  }
  expect(new Set(ADAPTERS.map(a => a.nickname)).size).toBe(ADAPTERS.length)
  expect(geminiFlash.argv({} as never, { thread: '/t', cwd: '/w', timeoutS: null, session: 's1', agent: 'a1' }))
    .toEqual(['agents-inc', 'native', 'step', '--model', 'gemini-flash', '--cwd', '/w', '--session', 's1', '--agent', 'a1'])
})

test('sol, terra and astra are thread types through agents-inc run under their own name; luna is unchanged', () => {
  expect(CODEX_ADAPTERS[0]).toBe(codexAdapter)
  for (const nick of ['sol', 'terra', 'astra']) {
    const a = ADAPTERS.find(x => x.nickname === nick)
    expect(a?.provider).toBe('codex')
    expect(a?.kind).toBe('thread')
    expect(a?.auth).toBe('cli-login')
    expect(a?.cli).toEqual(['agents-inc', 'native', '--model', nick])
    expect(a?.argv({} as never, { thread: '/t', cwd: '/w', timeoutS: 30 })).toEqual(['agents-inc', 'run', '--model', nick, '--effort', 'low',
      '--no-tools', '--host-tools', '--timeout', '30', '--cwd', '/w', '--thread', '/t'])
    expect(a?.identity('slug-x')).toContain(`You are ${nick}`)
    expect(a?.classify(124, '', 'why', 9)?.fail).toContain(`${nick} failed: timeout`)
    expect(a?.classify(75, 'usage or rate limit', 'why', 9)?.fail).toContain(`${nick} quota-paused`)
  }
  expect(ADAPTERS.find(x => x.nickname === 'luna')).toBeUndefined()
  expect(codexAdapter.cli).toEqual(['agents-inc', 'luna'])
})

test('a codex nickname switched off at status registers nothing; one switched on registers', async () => {
  const f = fake$(JSON.stringify({ models: [
    { nickname: 'sol', offered: false, slug: 'gpt-6.1-sol', reason: 'switched off' },
    { nickname: 'terra', offered: true, slug: 'gpt-6.1-terra' },
  ] }))
  await registerNativeAgents(f.$ as never, { cwd: '/w' })
  expect(f.registered).toMatchObject([{ name: 'terra' }])
})

test('exit codes map to fixed failure texts; only a timeout retries', () => {
  const c = (code: number, err = '') => classifyHttp('gemini-flash', code, err, 'why', 60)
  expect(c(124)).toMatchObject({ failed: true, retry: true })
  expect(c(75, 'agents-inc native step: usage or rate limit reached (429)')?.fail).toContain('gemini-flash quota-paused')
  expect(c(69, 'WB_NATIVE_HOST_BLOCKED: host')?.fail).toContain('provider host blocked')
  expect(c(2, 'WB_NATIVE_CONTEXT_OVER: context over 200000 chars')?.fail).toContain('context over 200000 chars')
  expect(c(3, 'WB_NATIVE_KEY_MISSING: no key')?.fail).toContain('not available (WB_NATIVE_KEY_MISSING)')
  expect(c(3, 'WB_NATIVE_NOT_FREE: slug x is not free')?.fail).toContain('not available (WB_NATIVE_NOT_FREE)')
  expect(c(1, 'boom')).toBeNull()
  for (const code of [75, 69, 3]) expect(c(code, 'WB_NATIVE_KEY_MISSING')?.retry).toBe(false)
})

test('needs-authorization tells the parent to ask the operator and names the allow command', () => {
  const ask = { provider: 'gemini', workspace: '/w', sends: 'the whole conversation', write_dirs: ['/w/.scratch'], allow: 'agents-inc native allow gemini --workspace /w' }
  const out = classifyHttp('gemini-flash', 3, `WB_NATIVE_NEEDS_AUTHORIZATION: ${JSON.stringify(ask)}`, 'why', 60)
  expect(out?.retry).toBe(false)
  expect(out?.fail).toContain('Nothing was sent')
  expect(out?.fail).toContain('Ask the operator')
  expect(out?.fail).toContain('`agents-inc native allow gemini --workspace /w`')
})

function fake$(out: string, code = 0) {
  const spawns: string[][] = []
  const registered: unknown[] = []
  const $ = {
    process: {
      spawn: (a: { argv: string[] }) => (async function* () {
        spawns.push(a.argv)
        if (out) yield { stream: 'stdout' as const, text: out }
        return { code }
      })(),
    },
    agent: { register: async (a: unknown) => { registered.push(a) } },
    plugin: { root: '/p' },
    ui: { log: () => undefined },
    env: { get: async () => undefined },
  }
  return { $, spawns, registered }
}

test('session start reads every model in one status call and sends no provider request (SC-006)', async () => {
  const f = fake$(JSON.stringify({ models: [{ nickname: 'luna', offered: true, slug: 'gpt-6-luna' }, { nickname: 'gemini-flash', offered: true, slug: 'gemini-3.8-flash' }] }))
  await registerNativeAgents(f.$ as never, { cwd: '/w' })
  expect(f.spawns).toEqual([['agents-inc', 'luna', 'status', '--json', '--all', '--cwd', '/w']])
  expect(f.registered).toMatchObject([{ name: 'gemini-flash' }])
})

test('a model that is not offered, or a failed status call, registers nothing', async () => {
  const off = fake$(JSON.stringify({ models: [{ nickname: 'gemini-flash', offered: false, slug: 'gemini-3.8-flash' }] }))
  await registerNativeAgents(off.$ as never, { cwd: '/w' })
  expect(off.registered).toEqual([])
  const bad = fake$('', 1)
  expect(await readNativeStatus(bad.$ as never, '/w')).toBeNull()
  await registerNativeAgents(bad.$ as never, { cwd: '/w' })
  expect(bad.registered).toEqual([])
  expect(bad.spawns.length).toBe(2) // one per call, never a retry
})
