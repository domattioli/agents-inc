// Spec 038: the Codex adapter. Everything here is about Codex or `agents-inc run`; the loop holds the rest.
import type { Adapter, Outcome } from './adapter'
import { failureText } from './loop'

const NICK = 'luna'

// luna refused twice with "the catalog Bash tool is not in my available tools" (par scenario, spec 028 Docker run): the
// push says where the catalog tools are, since luna looks for them in Codex's own tool list.
const PUSH = 'You answered without running a tool the task needs. The catalog tools are not in your own tool list, and that is ' +
  'expected: they are in the Tools list of the prompt, and you call one by naming it in "tools". Every catalog tool is real and the host runs it for you; ' +
  'a value you report must come from a tool result in this conversation, never from a snapshot or a guess. ' +
  'Request the tools the task needs in "tools" now. Reply with exactly one JSON object.\n'
const CONTINUE = 'Your reply says steps of the task remain. Request the tools for the remaining steps in "tools" now; report only when ' +
  'every result the report needs is in. Reply with exactly one JSON object.\n'
// A step stopped for asking (exit 77) is retried on a fresh thread that says so (macOS stress, 2026-11-11: the retry asked too).
const ASKED_NOTE = 'Your previous attempt at this step asked a question and was stopped: nobody can answer. ' +
  'Do not ask. Request the catalog tools the task needs in "tools" now.\n'

// Per run (one `agents-inc run`): `agents-inc run --timeout` kills Codex's process group at the limit and exits 124.
// Every Codex nickname shares this one variable: the engine takes only a literal name in $.env.get.
const TIMEOUT_ENV = 'AGENTS_INC_LUNA_STEP_TIMEOUT_S'
const timeoutFor = (nick: string) => (s: number) => `${nick} failed: timeout: Codex sent no reply within ${s} s (limit ${TIMEOUT_ENV})`
const timeoutText = timeoutFor(NICK)

// The text the parent sees when `agents-inc run` exits non-zero (D4). Quota, a missing catalog and a missing Codex are
// not cured by a fresh thread, so they are not retried.
function classify(code: number | null, stderr: string, why: string, limitS: number): Outcome | null {
  return classifyFor(NICK, code, stderr, why, limitS)
}

function classifyFor(NICK: string, code: number | null, stderr: string, why: string, limitS: number): Outcome | null {
  const clean = failureText(stderr)
  if (code === 124) return { reply: why, failed: true, fail: timeoutFor(NICK)(limitS) }
  if (code === 77 || stderr.includes('WB_LUNA_RUNAWAY')) {
    const line = clean.split('\n').find(l => l.includes('WB_LUNA_RUNAWAY'))?.replace(/^.*?WB_LUNA_RUNAWAY:?\s*/, '') ?? clean.split('\n')[0]
    return { reply: why, failed: true, asked: true, fail: `${NICK} failed: Codex looped on its own tools and was stopped to cap token use (${line})` }
  }
  if (code === 75) {
    const line = clean.split('\n').find(l => /usage or rate limit/.test(l)) ?? clean.split('\n')[0]
    return { reply: why, failed: true, retry: false, fail: `${NICK} quota-paused: ${line}` }
  }
  const missing = /WB_(CLI_NOT_FOUND|CODEX_AUTH_MISSING)/.exec(stderr)
  if (missing) return { reply: why, failed: true, retry: false, fail: `${NICK} failed: Codex missing (${missing[0]})` }
  if (code === 3 && stderr.includes('WB_LUNA_CATALOG_MISSING')) {
    const rest = clean.split('\n').find(l => l.includes('WB_LUNA_CATALOG_MISSING'))?.replace(/^.*?WB_LUNA_CATALOG_MISSING:?\s*/, '') ?? ''
    return { reply: why, failed: true, retry: false, fail: `${NICK} failed: catalog missing (WB_LUNA_CATALOG_MISSING) ${rest}`.trim() }
  }
  return null
}

export const codexAdapter: Adapter = {
  provider: 'codex',
  kind: 'thread',
  auth: 'cli-login',
  nickname: NICK,
  cli: ['agents-inc', 'luna'],
  description: slug => `General-purpose agent whose reasoning is done by luna (${slug}, run through Codex).`,
  toolHome: 'The catalog tools live in the host, not in Codex: they never appear in your own tool list, so never look for them there. ',
  identity: slug => `You are luna (OpenAI GPT-6 Luna, model ${slug}, run through Codex).\n`,
  // luna sometimes reads Codex's own tools as the way to run a catalog tool, or passes its reply to one.
  ownTools: 'Codex\'s own tools (exec, wait, request_user_input, list_agents, send_message, collaboration.*, and any other) are ' +
    'not yours in this loop: never call them, never search them for a catalog tool, and never pass your reply to one. ',
  deltaRule: 'Request catalog tools in "tools", never through exec or another Codex tool. ',
  pushes: { refusal: PUSH, unfinished: CONTINUE, asked: ASKED_NOTE },
  timeoutEnv: TIMEOUT_ENV,
  timeoutText,
  argv: (_model, o) => ['agents-inc', 'run', '--model', NICK, '--effort', 'low', '--no-tools', '--host-tools',
    ...(o.timeoutS !== null ? ['--timeout', String(o.timeoutS)] : []), '--cwd', o.cwd, '--thread', o.thread],
  // An installed agents-inc older than this mod has no --timeout.
  rejectsTimeout: (code, stderr) => code === 2 && /unrecognized arguments:.*--timeout/.test(stderr),
  classify,
}

// T042: the other Codex nicknames, the same adapter under their own name. Their status|begin|end verbs are
// `agents-inc native --model <nick> ...` (switch default off: they spend more of the Codex subscription than luna).
function codexNick(nick: string, vendorName: string): Adapter {
  return {
    ...codexAdapter,
    nickname: nick,
    cli: ['agents-inc', 'native', '--model', nick],
    description: slug => `General-purpose agent whose reasoning is done by ${nick} (${slug}, run through Codex).`,
    identity: slug => `You are ${nick} (${vendorName}, model ${slug}, run through Codex).\n`,
    timeoutText: timeoutFor(nick),
    argv: (_model, o) => ['agents-inc', 'run', '--model', nick, '--effort', 'low', '--no-tools', '--host-tools',
      ...(o.timeoutS !== null ? ['--timeout', String(o.timeoutS)] : []), '--cwd', o.cwd, '--thread', o.thread],
    classify: (code, stderr, why, limitS) => classifyFor(nick, code, stderr, why, limitS),
  }
}

export const CODEX_ADAPTERS: readonly Adapter[] = [
  codexAdapter,
  codexNick('sol', 'OpenAI GPT Sol'),
  codexNick('terra', 'OpenAI GPT Terra'),
  codexNick('astra', 'OpenAI GPT Astra'),
]
