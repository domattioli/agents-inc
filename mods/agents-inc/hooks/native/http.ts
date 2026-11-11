// Spec 038 T025: the stateless adapter for free-provider guest agents (Gemini first). The provider call runs in Python
// (`agents-inc native step`, native_http.py): the key stays in that process and never reaches the mod. The loop resends
// the whole conversation each step (kind 'stateless'); a prompt over the model's limit is refused, never cut.
import type { Adapter, NativeModel, Outcome } from './adapter'
import { failureText } from './loop'

// One literal env name for every stateless adapter: the engine takes only a literal name in $.env.get.
export const NATIVE_TIMEOUT_ENV = 'AGENTS_INC_NATIVE_STEP_TIMEOUT_S'

type Spec = { nickname: string; provider: 'gemini' | 'mistral' | 'openrouter'; vendor: string }

const PUSH = 'You answered without running a tool the task needs. Every catalog tool is real and the host runs it for you: ' +
  'call one by naming it in "tools". A value you report must come from a tool result in this conversation, never from a guess. ' +
  'Request the tools the task needs in "tools" now. Reply with exactly one JSON object.\n'
const CONTINUE = 'Your reply says steps of the task remain. Request the tools for the remaining steps in "tools" now; report only when ' +
  'every result the report needs is in. Reply with exactly one JSON object.\n'
const ASKED = 'Your previous attempt at this step asked a question: nobody can answer. Do not ask. ' +
  'Request the catalog tools the task needs in "tools" now.\n'

// The line after a code marker, e.g. `WB_NATIVE_CONTEXT_OVER: context over 200000 chars ...` -> the text after the code.
const after = (stderr: string, code: string) =>
  stderr.split('\n').find(l => l.includes(code))?.replace(new RegExp(`^.*?${code}:?\\s*`), '').trim() ?? ''

export function classifyHttp(nick: string, code: number | null, stderr: string, why: string, limitS: number): Outcome | null {
  const fail = (text: string, retry = false): Outcome => ({ reply: why, failed: true, retry, fail: `${nick} ${text}` })
  if (code === 124) return fail(`failed: timeout: the provider sent no reply within ${limitS} s (limit ${NATIVE_TIMEOUT_ENV})`, true)
  if (code === 75) return fail(`quota-paused: ${failureText(stderr).split('\n').find(l => /usage or rate limit/.test(l))?.replace(/^agents-inc native step:\s*/, '') ?? 'provider quota'}`)
  if (code === 69) return fail(`failed: provider host blocked (WB_NATIVE_HOST_BLOCKED) ${after(stderr, 'WB_NATIVE_HOST_BLOCKED')}`.trim())
  if (code === 2 && stderr.includes('WB_NATIVE_CONTEXT_OVER')) {
    const n = /context over (\d+) chars/.exec(stderr)?.[1] ?? '?'
    return fail(`failed: context over ${n} chars; start a new agent with a shorter task`)
  }
  if (code === 3 && stderr.includes('WB_NATIVE_NEEDS_AUTHORIZATION')) {
    // Nothing was sent. The parent asks the operator once, and the allow command stores the record (D76).
    let ask: { provider?: string; workspace?: string; sends?: string; write_dirs?: string[]; allow?: string } = {}
    try {
      ask = JSON.parse(after(stderr, 'WB_NATIVE_NEEDS_AUTHORIZATION'))
    } catch {
      // keep the generic text
    }
    return fail(`failed: needs-authorization: ${ask.provider ?? 'this provider'} is not authorized for ${ask.workspace ?? 'this workspace'}. ` +
      `Nothing was sent. A ${nick} agent sends ${ask.sends ?? 'the whole conversation'} to ${ask.provider ?? 'the provider'}, and may write only in ` +
      `${(ask.write_dirs ?? []).join(', ') || 'the recorded directories'}. Ask the operator; on a yes run \`${ask.allow ?? 'agents-inc native allow <provider> --workspace <path>'}\` and start the agent again.`)
  }
  const missing = /WB_NATIVE_(KEY_MISSING|UNKNOWN_MODEL|UNKNOWN_PROVIDER|NOT_FREE)/.exec(stderr)
  if (missing) return fail(`failed: not available (${missing[0]}) ${after(stderr, missing[0])}`.trim())
  return null
}

export function httpAdapter(spec: Spec): Adapter {
  const nick = spec.nickname
  return {
    provider: spec.provider,
    kind: 'stateless',
    auth: 'key-store',
    nickname: nick,
    // `agents-inc native --model <nick> status|begin|end ...`
    cli: ['agents-inc', 'native', '--model', nick],
    description: slug => `General-purpose agent whose reasoning is done by ${nick} (${slug}, ${spec.vendor}, free tier). Sends the conversation to ${spec.vendor}.`,
    toolHome: 'The catalog tools live in the host: you have no tools of your own, and the host runs each tool you name. ',
    identity: slug => `You are ${nick} (${spec.vendor} model ${slug}, reached through agents-inc).\n`,
    ownTools: '',
    deltaRule: '',
    pushes: { refusal: PUSH, unfinished: CONTINUE, asked: ASKED },
    timeoutEnv: NATIVE_TIMEOUT_ENV,
    timeoutText: s => `${nick} failed: timeout: the provider sent no reply within ${s} s (limit ${NATIVE_TIMEOUT_ENV})`,
    // The thread path is ignored: a stateless model gets the whole conversation on stdin every run.
    argv: (_m: NativeModel, o) => ['agents-inc', 'native', 'step', '--model', nick, '--cwd', o.cwd || '.',
      ...(o.timeoutS !== null ? ['--timeout', String(o.timeoutS)] : [])],
    rejectsTimeout: () => false,
    classify: (code, stderr, why, limitS) => classifyHttp(nick, code, stderr, why, limitS),
  }
}

export const geminiFlash = httpAdapter({ nickname: 'gemini-flash', provider: 'gemini', vendor: 'Google Gemini' })

// T040/T041: one adapter per free nickname in agents_inc/models.json (tests/test_native_nicknames.py keeps the two in step).
// OpenRouter: native_http.free_only refuses any slug not ending ':free' before a request.
const mistral = (nickname: string) => httpAdapter({ nickname, provider: 'mistral', vendor: 'Mistral' })
const openrouter = (nickname: string) => httpAdapter({ nickname, provider: 'openrouter', vendor: 'OpenRouter' })
export const HTTP_ADAPTERS: readonly Adapter[] = [
  geminiFlash,
  mistral('ministral'),
  mistral('codestral'),
  openrouter('nemotron-lightning'),
  openrouter('nemotron-ultra'),
  openrouter('nemotron-nano'),
  openrouter('gemma-26b'),
  openrouter('gemma-31b'),
  openrouter('dots-note'),
]
