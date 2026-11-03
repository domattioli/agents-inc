import type { Register } from 'claude-code'

const AGENT = 'luna'
const AGENT_TYPES = ['agents-inc:luna']
const LOG = 'agents-inc luna:'
const HANDBACK = 'SubagentHandback'
const HANDBACK_ARGS = '{ message: string }'
const HANDBACK_CUE = 'call SubagentHandback('
const RESULT_CAP = 20_000
const DESC_CAP = 500
const MCP_DESC_CAP = 200
// The step timer runs on $.clock.sleep, which is monotonic: time the host spends asleep does not count, so a Mac that
// sleeps mid-step does not fail the step on time alone (macOS stress run, 2026-10-25).
const RUN_TIMEOUT_MS = 300_000
const MODEL_LINE = /You are powered by the model|The exact model ID is/
const DELTA_HEADER =
  'New messages since your last reply. Same rules: reply with one JSON object {say, tools}; act on the latest messages; finish as the rules said. ' +
  'Request catalog tools in "tools", never through exec or another Codex tool.\n'
// luna sometimes reads Codex's read-only sandbox note as its own and answers that it cannot run a tool, calling none.
const REFUSAL = /(can['’]?t|cannot|unable to|not able to)\s+(run|read|inspect|execute|access|use|report|request|call|make|issue|perform)|tools?\b[^.]*\b(disabled|unavailable|not available)/i
// luna refused twice with "the catalog Bash tool is not in my available tools" (par scenario, spec 028 Docker run): the
// push says where the catalog tools are, since luna looks for them in Codex's own tool list.
const PUSH = 'You answered without running a tool the task needs. The catalog tools are not in your own tool list, and that is ' +
  'expected: they are in the Tools list of the prompt, and you call one by naming it in "tools". Every catalog tool is real and the host runs it for you; ' +
  'a value you report must come from a tool result in this conversation, never from a snapshot or a guess. ' +
  'Request the tools the task needs in "tools" now. Reply with exactly one JSON object.\n'
// A first reply that runs nothing is pushed once when it refuses a tool, or when the task names a catalog tool:
// luna answered "A=0" for `wc -l a.txt` without running Bash (Docker stress run, 2026-10-24).
export function skipsTools(reply: Reply | string | null, ranTool: boolean, task = '', names: readonly string[] = []): boolean {
  if (ranTool || reply === null || typeof reply === 'string' || reply.tools.length > 0) return false
  return REFUSAL.test(reply.say) || names.some(n => n !== HANDBACK && namesTool(task, n))
}
// A tool name counts only mid-sentence after a lowercase word ("with Bash", "then Read") or before "tool":
// "Write one Latin sentence" names no tool.
function namesTool(task: string, name: string): boolean {
  const n = name.replace(/[^\w]/g, '\\$&')
  return new RegExp(`(?<=[a-z,;:] )${n}\\b|\\b${n} tool\\b`).test(task)
}
// The task text: every user text block without harness reminders, which name tools the task never asked for.
export function taskText(messages: readonly Msg[]): string {
  return messages.filter(m => m.role === 'user').flatMap(m => m.content ?? []).filter(b => b.type === 'text')
    .map(b => String(b.text ?? '').replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '')).join('\n')
}
// luna ran one of five commands and answered "A=173. I haven't run the other four commands yet." (steps5, spec 028 Docker run).
// luna also said "the other four remain unrun" and "their results have not arrived".
const UNFINISHED = /\b(haven['’]?t|have not|not yet|yet to)\b[^.]*\b(run|read|done|finish|complete|execute)|\bremaining (\w+ )?(commands?|steps?)\b|\bremain(s)? (unrun|to run|undone)\b|\bunrun\b|\b(have|has) not arrived\b|\b(haven|hasn)['’]?t arrived\b/i
const CONTINUE = 'Your reply says steps of the task remain. Request the tools for the remaining steps in "tools" now; report only when ' +
  'every result the report needs is in. Reply with exactly one JSON object.\n'
export const stopsEarly = (reply: Reply | string | null): boolean =>
  reply !== null && typeof reply !== 'string' && reply.tools.length === 0 && UNFINISHED.test(reply.say)
const CORRECTION = (why: string) => `Your previous reply was rejected: ${why}. Reply with exactly one JSON object, only tools from the Tools list.\n`
const TOOL_TYPES_PATH = '.claude-plugin/types/claude-code-tools/index.d.ts'

// The slug comes from `agents-inc luna status`, never from a fixed string here.
const header = () =>
  'You drive an agent loop with real tools. To run a tool, name it in "tools"; the host runs it and its result arrives ' +
  'in the next step. Bash, Read and every other catalog tool work this way, so never answer that you cannot run one.\n' +
  'The catalog tools live in the host, not in Codex: they never appear in your own tool list, so never look for them there. ' +
  'Example, to run a shell command: {"say": "", "tools": [{"name": "Bash", "input": {"command": "ls"}}]}\n' +
  `You are luna (OpenAI GPT-6 Luna, model ${lunaSlug}, run through Codex).\n` +
  'Codex\'s own tools (exec, wait, request_user_input, list_agents, send_message, collaboration.*, and any other) are ' +
  'not yours in this loop: never call them, never search them for a catalog tool, and never pass your reply to one. ' +
  'Your reply is the JSON object itself, written as your final message text. Every tool in the catalog below is real and available: call it ' +
  'by naming it in "tools", and its result arrives in the next step. Never report a catalog tool as unavailable.\n' +
  'Report only values you read in a tool result in this conversation; never guess one. The git status and other context ' +
  'in the system prompt is a snapshot from session start and may be stale: when the task asks for a command, run it.\n' +
  'A Read result starts each line with its line number and a tab: the last of those numbers is the line count of the part ' +
  'read. To count a file\'s lines, Read it whole (no offset or limit) or run wc -l.\n' +
  'A task is done only when every step it names has run: keep requesting tools until each result the report needs is in.\n' +
  'Act on the latest messages; earlier ones are history.\n' +
  'Reply with exactly one JSON object and nothing else:\n' +
  '{"say": "<short text, may be empty>", "tools": [{"name": "<tool from the catalog>", "input": {...}}]}\n' +
  'Use "tools": [] only when you have nothing to call.\n'
const HANDBACK_RULES =
  'When the task is done, call SubagentHandback with your full report.\n' +
  'Call SubagentHandback alone, in a step after you have read the results it reports; never in the same step as another tool.\n'
// A background subagent on some builds has no SubagentHandback: its last plain reply is its report.
const FINAL_RULES =
  'When the task is done, reply with your full report in "say" and "tools": []. That reply ends your run.\n' +
  'There is no SubagentHandback tool here; never call it.\n'

const AGENT_PROMPT = 'You are a general-purpose agent. Complete the task you are given, then hand your report back.'

type Reply = { say: string; tools: { name: string; input: unknown }[] }
type Block = { type: string; [field: string]: unknown }
type Msg = { role: 'user' | 'assistant'; content: Block[] }
type Tool = { name: string; description: string; mcp?: boolean }
type Thinking = { kind: 'thinking'; index: number; text: string }
type Usage = { input_tokens: number; cached_input_tokens: number; output_tokens: number }
// One agents-inc run: the reply (or why it was rejected), whether the run itself failed, and what it cost.
// `fail` is the text the parent sees for a failed run; `retry: false` marks a failure a fresh thread cannot cure.
type Outcome = { reply: Reply | string | null; failed: boolean; fail?: string; retry?: boolean }
type Cli = {
  process: { spawn: (a: { argv: string[]; cwd?: string; input?: string }) => AsyncGenerator<{ stream: 'stdout' | 'stderr'; text: string }, { code: number | null }> }
  ui: { log: (message: string, options: { to: 'debug' }) => unknown }
  session: { id: () => unknown }
}
type Status = { offered: boolean; slug: string; reason?: string }
type Ran = { outcome: 'done' | 'failed' | 'quota-paused' | 'aborted'; usage: Usage }
// Per luna subagent: the Codex thread file it keeps, whether a run has used it, and how many api messages luna has seen.
type AgentState = { n: number; used: boolean; sent: number }

const lunaIds = new Set<string>()
const agents = new Map<string, AgentState>()
// Last running total Codex reported per thread file.
const threadTotals = new Map<string, Usage>()
const ZERO: Usage = { input_tokens: 0, cached_input_tokens: 0, output_tokens: 0 }
let sessionCwd = ''
let sessionId = 'session'
let lunaSlug = 'luna'
let offered = false // what `agents-inc luna status` said at session start
// Per luna agent: the `agents-inc luna begin` call, and what its steps cost and how the last one ended.
const begun = new Map<string, Promise<void>>()
const ran = new Map<string, Ran>()
let toolTypes: string | undefined // text of the engine-written built-in tool argument types, read once

type TurnUsageOut = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
  model: string
}

// The system prompt names a placeholder Claude model; luna is not that model, so those lines go.
const stripModelLines = (text: string) => text.split('\n').filter(l => !MODEL_LINE.test(l)).join('\n')

// The harness's skill-listing reminder, cut to the skill names: luna can still call Skill by name, without ~25k chars
// of descriptions in every fresh prompt.
const SKILL_LIST = /(<system-reminder>\nThe following skills are available for use with the Skill tool:\n)([\s\S]*?)(<\/system-reminder>)/
export const trimSkillList = (text: string) =>
  text.replace(SKILL_LIST, (_, head: string, body: string, tail: string) => {
    const names = body.split('\n').map(l => /^- (\S+?)(?::\s|$)/.exec(l)?.[1]).filter(Boolean)
    return `${head}${names.join(', ')}\n${tail}`
  })

// The dir is git-ignored; agents-inc creates it. A fresh thread after a failed resume gets the suffix -2, -3...
const safe = (s: string) => s.replace(/[^\w.-]/g, '_')
const threadPath = (agentId: string, n: number) =>
  `${sessionCwd || '.'}/.scratch/agents-inc-luna/${safe(sessionId)}/${safe(agentId)}${n > 1 ? `-${n}` : ''}.thread`
const debugOn = () => (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.AGENTS_INC_LUNA_DEBUG === '1'

const cap = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}\n[truncated ${s.length - n} chars]` : s)

// A field's `/** doc */` cut to its first sentence and FIELD_DOC_CAP chars; the field itself stays.
const FIELD_DOC_CAP = 160
const shortDoc = (line: string) =>
  line.replace(/\/\*\* (.*?) \*\//, (_, doc: string) => { const first = doc.split(/(?<=[.!?])\s/)[0]; return `/** ${first.length > FIELD_DOC_CAP ? `${first.slice(0, FIELD_DOC_CAP)}…` : first} */` })

// The stderr lines that explain a failed run: Codex's MCP start-up noise and the streamed progress lines left out.
const NOISE = /rmcp::|^agents-inc run: (event|usage|record|tools) /
export const failureText = (stderr: string) =>
  stderr.split('\n').filter(l => l.trim() && !NOISE.test(l)).join('\n').slice(-600) || '(no other stderr)'

// The `Name: {...}` block of one tool in the BuiltinToolInputs interface; '' when the tool has none.
export function argBlock(types: string, name: string): string {
  const lines = types.split('\n')
  const start = lines.findIndex(l => l.startsWith(`    ${name}: {`))
  if (start < 0) return ''
  if (lines[start].trimEnd().endsWith('{}')) return lines[start].trim()
  const end = lines.findIndex((l, i) => i > start && l === '    }')
  return end < 0 ? '' : lines.slice(start, end + 1).map(l => shortDoc(l.slice(4))).join('\n')
}

export function catalog(tools: readonly Tool[], types: string, hand = true): string {
  const entries = tools.map(t => {
    const block = argBlock(types, t.name)
    const description = t.mcp ? cap(t.description.split(/(?<=[.!?])\s/)[0], MCP_DESC_CAP) : cap(t.description, DESC_CAP)
    return `- ${t.name}: ${description}${block ? `\n  Arguments:\n${block.replace(/^/gm, '  ')}` : ''}`
  })
  if (hand) entries.push(`- ${HANDBACK}: Deliver your final report and end your run.\n  Arguments: ${HANDBACK_ARGS}`)
  return entries.join('\n')
}

function resultText(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return content === undefined ? '' : JSON.stringify(content)
  return content.map(b => (b && typeof b === 'object' && typeof (b as Block).text === 'string' ? (b as Block).text : `[${(b as Block)?.type ?? 'block'}]`)).join('\n')
}

// Every message in order, every block kept: text as written, calls as name + JSON, results capped.
export function render(messages: readonly Msg[]): string {
  const out: string[] = []
  const toolNames = new Map<unknown, string>()
  const toolInputs = new Map<unknown, Record<string, unknown>>()
  for (const m of messages) {
    for (const b of m.content ?? []) {
      if (b.type === 'text') out.push(`${m.role}: ${trimSkillList(stripModelLines(String(b.text ?? '')))}`)
      else if (b.type === 'tool_use') {
        toolNames.set(b.id, String(b.name))
        toolInputs.set(b.id, (b.input ?? {}) as Record<string, unknown>)
        out.push(`assistant tool call: ${String(b.name)} ${JSON.stringify(b.input ?? {})}`)
      } else if (b.type === 'tool_result') {
        let text = resultText(b.content)
        // Read numbers the empty line after a file's final newline: luna counted 96 lines in a 95-line file.
        // The harness may append reminders after the file text, so the empty line is found before them.
        if (toolNames.get(b.tool_use_id) === 'Read') text = text.replace(/\n[ \t]*\d+\t?[ \t]*(?=(\n*<system-reminder>[\s\S]*)?$)/, '')
        // luna read b.txt with offset or limit and reported the last line number shown as the file's line count
        // (B=1, B=50, B=60 for a 95-line file; spec 028 Docker runs), so a partial Read says it is partial.
        const input = toolInputs.get(b.tool_use_id) ?? {}
        if (toolNames.get(b.tool_use_id) === 'Read' && (input.offset !== undefined || input.limit !== undefined)) {
          text += `\n[partial Read (offset ${input.offset ?? 'none'}, limit ${input.limit ?? 'none'}): these lines are part of the file; the last line number is not the file's line count]`
        }
        out.push(`tool result${b.is_error ? ' (error)' : ''}: ${cap(text, RESULT_CAP)}`)
      }
      else out.push(`${m.role}: [${b.type}]`)
    }
  }
  return out.join('\n')
}

export function buildPrompt(system: string, tools: string, messages: readonly Msg[], hand = true): string {
  return `${header()}${hand ? HANDBACK_RULES : FINAL_RULES}\nSystem prompt:\n${system}\n\nTools:\n${tools}\n\nConversation:\n${render(messages) || '(empty)'}\n`
}

// First balanced {...} in the text, parsed; a reason string when none parses or the shape is wrong.
// luna may write a tool request as one message and, with no Codex tool to run it, go on to a final message that guesses
// the results ("B=1" for `wc -l b.txt`; Docker stress run, 2026-10-25). The first message that requests tools ends the step.
export function pickReply(messages: readonly string[], stdout: string, allowed?: ReadonlySet<string>): Reply | string {
  for (const text of messages) {
    const r = parseReply(text, allowed)
    if (typeof r !== 'string' && r.tools.length > 0) return r
  }
  return parseReply(stdout, allowed)
}

export function parseReply(stdout: string, allowed?: ReadonlySet<string>): Reply | string {
  for (let start = stdout.indexOf('{'); start >= 0; start = stdout.indexOf('{', start + 1)) {
    let depth = 0
    let inStr = false
    for (let i = start; i < stdout.length; i++) {
      const c = stdout[i]
      if (inStr) {
        if (c === '\\') i++
        else if (c === '"') inStr = false
      } else if (c === '"') inStr = true
      else if (c === '{') depth++
      else if (c === '}' && --depth === 0) {
        let obj: unknown
        try {
          obj = JSON.parse(stdout.slice(start, i + 1))
        } catch {
          break
        }
        return shape(obj, allowed)
      }
    }
  }
  return 'no JSON object in the reply'
}

function shape(obj: unknown, allowed?: ReadonlySet<string>): Reply | string {
  if (typeof obj !== 'object' || obj === null) return 'reply is not an object'
  const o = obj as { say?: unknown; tools?: unknown }
  const tools = o.tools === undefined ? [] : o.tools
  if (!Array.isArray(tools)) return '"tools" is not a list'
  const list: Reply['tools'] = []
  for (const t of tools) {
    const name = (t as { name?: unknown } | null)?.name
    if (typeof name !== 'string' || (allowed && !allowed.has(name))) return `unknown tool ${JSON.stringify(name)}; use only a tool name from the Tools list`
    list.push({ name, input: (t as { input?: unknown }).input ?? {} })
  }
  return { say: typeof o.say === 'string' ? o.say : '', tools: list }
}

// Where the harness offers SubagentHandback, plain final text is ignored: the report has to travel through it.
export function handback(out: Reply, hand = true): Reply {
  if (!hand) return out
  // A hand-back next to other calls would report before their results exist: drop it, the next step can hand back.
  const others = out.tools.filter(t => t.name !== HANDBACK)
  if (others.length > 0 && others.length < out.tools.length) return { ...out, tools: others }
  return out.tools.length === 0 && out.say ? { say: out.say, tools: [{ name: HANDBACK, input: { message: out.say } }] } : out
}

async function readToolTypes($: { plugin: { root: string }; fs: { read: (p: string) => Promise<unknown> } }): Promise<string> {
  if (toolTypes !== undefined) return toolTypes
  try {
    const text = await $.fs.read(`${$.plugin.root}/${TOOL_TYPES_PATH}`)
    if (typeof text === 'string') return (toolTypes = text)
  } catch {
    // missing file: descriptions only
  }
  return ''
}

// Called from mod.ts: a plugin's hooks.json names one module, and a module may register session.start once.
async function lunaCli($: Cli, args: string[], cwd?: string): Promise<{ code: number | null; out: string; err: string }> {
  const stream = $.process.spawn({ argv: ['agents-inc', 'luna', ...args], cwd })
  let out = ''
  let err = ''
  for (;;) {
    const n = await stream.next()
    if (n.done) return { code: n.value.code, out, err }
    if (n.value.stream === 'stdout') out += n.value.text
    else err += n.value.text
  }
}

async function lunaStatus($: Cli): Promise<Status | null> {
  try {
    const r = await lunaCli($, ['status', '--json'])
    const d = JSON.parse(r.out) as Status
    if (r.code === 0 && typeof d.offered === 'boolean' && typeof d.slug === 'string') return d
  } catch {
    // no readable status: the type is not offered
  }
  return null
}

// Spec 028 D6 item 1: pin the working tree once per luna agent. Failures are logged; the run goes on (Q2).
function ensureBegin($: Cli, id: string, task: string): Promise<void> {
  let p = begun.get(id)
  if (!p) {
    p = lunaCli($, ['begin', '--session', sessionId, '--agent', id, '--cwd', sessionCwd || '.', '--task', task.slice(0, 200)])
      .then(r => { if (r.code !== 0) $.ui.log(`${LOG} begin exited ${r.code}: ${failureText(r.err)}`, { to: 'debug' }) })
      .catch(err => { $.ui.log(`${LOG} begin failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' }) })
    begun.set(id, p)
  }
  return p
}

// Called from mod.ts: a plugin's hooks.json names one module, and a module may register session.start once.
// The type is registered only when the engine gives what the native type needs and `agents-inc luna status` offers it.
export async function registerLunaAgent(
  $: Cli & { agent: { register: (a: Record<string, unknown>) => Promise<unknown> } },
  e: { cwd: string },
): Promise<void> {
  sessionCwd = e.cwd
  offered = false
  // The contract check: the status call needs a streaming $.process.spawn, the registration needs $.agent.register.
  // A build without either leaves the type unregistered, and the debug log says which.
  const status = await lunaStatus($)
  if (!status) {
    $.ui.log(`${LOG} not registered: agents-inc luna status gave no usable answer (needs a streaming $.process.spawn)`, { to: 'debug' })
    return
  }
  lunaSlug = status.slug
  if (!status.offered) {
    $.ui.log(`${LOG} not registered: ${status.reason ?? 'not offered'}`, { to: 'debug' })
    return
  }
  try {
    sessionId = String((await $.session.id()) || sessionId)
  } catch {
    // keep the default
  }
  try {
    // No tools and no permissionMode: the agent inherits the parent's, like any native subagent.
    await $.agent.register({
      name: AGENT,
      description: `General-purpose agent whose reasoning is done by luna (${status.slug}, run through Codex).`,
      prompt: AGENT_PROMPT,
      model: 'haiku', // placeholder: turn.step never calls it for this agent
    })
    offered = true
  } catch (err) {
    $.ui.log(`${LOG} not registered: $.agent.register failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' })
  }
}

// The text the parent sees when `agents-inc run` exits non-zero (D4). Quota, a missing catalog and a missing Codex are
// not cured by a fresh thread, so they are not retried.
function exitFailure(code: number | null, stderr: string, why: string): Outcome {
  const clean = failureText(stderr)
  if (code === 75) {
    const line = clean.split('\n').find(l => /usage or rate limit/.test(l)) ?? clean.split('\n')[0]
    return { reply: why, failed: true, retry: false, fail: `luna quota-paused: ${line}` }
  }
  const missing = /WB_(CLI_NOT_FOUND|CODEX_AUTH_MISSING)/.exec(stderr)
  if (missing) return { reply: why, failed: true, retry: false, fail: `luna failed: Codex missing (${missing[0]})` }
  if (code === 3 && stderr.includes('WB_LUNA_CATALOG_MISSING')) {
    const rest = clean.split('\n').find(l => l.includes('WB_LUNA_CATALOG_MISSING'))?.replace(/^.*?WB_LUNA_CATALOG_MISSING:?\s*/, '') ?? ''
    return { reply: why, failed: true, retry: false, fail: `luna failed: catalog missing (WB_LUNA_CATALOG_MISSING) ${rest}`.trim() }
  }
  return { reply: why, failed: true, fail: `luna failed: run exited ${code}: ${clean}` }
}

const TIMEOUT_TEXT =`luna failed: timeout after ${RUN_TIMEOUT_MS / 1000} s`

export const register: Register = on => {

  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    if (AGENT_TYPES.includes(e.subagentType) && r.agentId) {
      lunaIds.add(r.agentId)
      void ensureBegin($, r.agentId, String(e.prompt ?? ''))
    }
    return r
  })

  // A session that registered the type before a switch-off still hides it; a failed guard hides it too.
  on('agent.offer', { agent: AGENT_TYPES[0] }, (_$, e, next) => (offered ? next(e) : { isOffered: false }))
    .catch((_$, e, next) => (next.called ? next(e) : { isOffered: false }))

  // Spec 028 D6 item 2: verify the tree against the begin snapshot and write the return row. The parent verifies (Q2).
  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    const id = e.agentId
    if (id === undefined || !lunaIds.has(id)) return r
    const done = ran.get(id) ?? { outcome: 'failed' as const, usage: ZERO }
    const outcome = e.isAborted ? 'aborted' : done.outcome
    try {
      await begun.get(id)
      const end = await lunaCli($, ['end', '--session', sessionId, '--agent', id, '--cwd', sessionCwd || '.', '--outcome', outcome, '--usage', JSON.stringify(done.usage)])
      if (end.code !== 0) {
        $.ui.log(`${LOG} end exited ${end.code}: ${failureText(end.err)}`, { to: 'debug' })
        return r
      }
      const rec = JSON.parse(end.out) as { snapshot?: string; changed?: string[] }
      if (typeof rec.snapshot === 'string' && rec.snapshot.startsWith('changed')) {
        const paths = (rec.changed ?? []).slice(0, 5).join(', ')
        return { ...r, text: `${r.text}\n[agents-inc luna] The working tree changed while this agent ran (${rec.snapshot}): ${paths}. Check it before you rely on the report.` }
      }
    } catch (err) {
      $.ui.log(`${LOG} end failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' })
    }
    return r
  })

  on('turn.step', async function* ($, e, next) {
    const id = e.agentId
    if (id === undefined || !offered) return yield* next(e)
    if (!lunaIds.has(id)) {
      // The spawn hook may not have recorded the id yet; the agent list knows the type.
      const listed = await $.agent.list().then(l => l.some(a => a.id === id && AGENT_TYPES.includes(a.type)), () => null)
      if (listed === null) {
        // Fail closed: a luna step must never reach the placeholder model.
        const text = `${LOG} cannot identify agent ${id}; step not sent to the placeholder model`
        yield { kind: 'text', index: 0, text }
        yield { kind: 'stop', stopReason: 'end_turn', usage: null }
        return { turnId: e.turnId, index: e.index, answer: text, toolUses: [], stopReason: 'end_turn', usage: null }
      }
      if (!listed) return yield* next(e)
      lunaIds.add(id)
    }
    await ensureBegin($, id, taskText((await $.session.messages({ agentId: id, as: 'api' }).catch(() => [])) as Msg[]))

    const t0 = await $.clock.now()
    // Shown live, not recorded: the window has something to show while luna works.
    yield { kind: 'thinking', index: 0, text: `luna is working on step ${e.index}…` }
    const aborted = new Promise<null>(res => {
      if (next.signal.aborted) res(null)
      else next.signal.addEventListener('abort', () => res(null), { once: true })
    })

    const acc: { usage: Usage | null; slug?: string; tools: string[] } = { usage: null, tools: [] } // summed over this step's runs
    const STOP = Symbol('stop')

    // One run: stderr progress lines become thinking chunks as they arrive; stdout is the reply.
    const ask = async function* (prompt: string, thread: string, allowed: ReadonlySet<string>): AsyncGenerator<Thinking, Outcome> {
      const timer = new AbortController()
      const stop = Promise.race([
        aborted.then(() => STOP),
        $.clock.sleep(RUN_TIMEOUT_MS, { signal: timer.signal }).then(() => STOP, () => new Promise<never>(() => {})),
      ])
      const stream = $.process.spawn({
        argv: ['agents-inc', 'run', '--model', 'luna', '--effort', 'low', '--no-tools', '--host-tools', '--cwd', sessionCwd, '--thread', thread],
        cwd: sessionCwd || undefined,
        input: prompt,
      })
      let stdout = ''
      let stderr = ''
      let pending = ''
      const lines: string[] = []
      const said: string[] = [] // agent_message texts, in order
      const take = (line: string) => {
        const m = /^agents-inc run: (event|usage|record|tools) (.*)$/.exec(line)
        if (!m) return
        if (m[1] === 'tools') {
          acc.tools.push(m[2])
          return
        }
        let data: Record<string, unknown>
        try {
          data = JSON.parse(m[2])
        } catch {
          return
        }
        if (m[1] === 'record' && typeof data.slug === 'string') acc.slug = data.slug
        else if (m[1] === 'usage') {
          // Codex reports the thread's running total: this run's share is the rise since the last report.
          const total: Usage = {
            input_tokens: Number(data.input_tokens) || 0,
            cached_input_tokens: Number(data.cached_input_tokens) || 0,
            output_tokens: Number(data.output_tokens) || 0,
          }
          const before = threadTotals.get(thread) ?? ZERO
          threadTotals.set(thread, total)
          const u = acc.usage ?? ZERO
          acc.usage = {
            input_tokens: u.input_tokens + Math.max(0, total.input_tokens - before.input_tokens),
            cached_input_tokens: u.cached_input_tokens + Math.max(0, total.cached_input_tokens - before.cached_input_tokens),
            output_tokens: u.output_tokens + Math.max(0, total.output_tokens - before.output_tokens),
          }
        } else if (m[1] === 'event' && typeof data.text === 'string') {
          lines.push(data.text)
          if (data.kind === 'agent_message') said.push(data.text)
        }
      }
      const feed = (text: string) => {
        pending += text
        const parts = pending.split('\n')
        pending = parts.pop() ?? ''
        parts.forEach(take)
      }
      try {
        for (;;) {
          const n = await Promise.race([stream.next(), stop])
          if (n === STOP) {
            void stream.return(undefined as never).catch(() => {})
            return next.signal.aborted ? { reply: null, failed: false } : { reply: 'agents-inc run timed out', failed: true, fail: TIMEOUT_TEXT }
          }
          if (n.done) {
            if (pending) take(pending)
            for (const text of lines.splice(0)) yield { kind: 'thinking', index: 0, text }
            if (n.value.code === 0) return { reply: pickReply(said, stdout, allowed), failed: false }
            const why = `agents-inc run exited ${n.value.code ?? n.value.signal}, stdout ${stdout.length} chars: ${failureText(stderr)}`
            $.ui.log(`${LOG} ${why}`, { to: 'debug' })
            return exitFailure(n.value.code, stderr, why)
          }
          if (n.value.stream === 'stdout') stdout += n.value.text
          else {
            stderr += n.value.text
            feed(n.value.text)
            for (const text of lines.splice(0)) yield { kind: 'thinking', index: 0, text }
          }
        }
      } catch (err) {
        const why = String((err as Error)?.message ?? err)
        return { reply: `agents-inc run failed: ${why}`, failed: true, fail: `luna failed: could not run agents-inc: ${why}` }
      } finally {
        timer.abort()
      }
    }

    const tools: Tool[] = await $.tool.list().catch(() => [])
    const api = await $.session.messages({ agentId: id, as: 'api' }).catch(() => [])
    const messages = Array.isArray(api) ? (api as Msg[]) : []
    // The harness announces SubagentHandback in a reminder when it serves it; a background agent on some builds has none
    // and loops on "No such tool available" if told to call it (Linux, Claude Code 2.1.310, 2026-10-24).
    const hand = tools.some(t => t.name === HANDBACK) || JSON.stringify(messages).includes(HANDBACK_CUE)
    const names = [...tools.filter(t => t.name !== HANDBACK).map(t => t.name), ...(hand ? [HANDBACK] : [])]
    const allowed = new Set(names)
    const composed = await $.prompt.compose({ tools: names }).catch(() => ({ sections: [] }))
    const system = [...composed.sections.map(s => stripModelLines(s.text)), AGENT_PROMPT].join('\n\n')
    const types = await readToolTypes($)
    const full = () => buildPrompt(system, catalog(tools, types, hand), messages, hand)

    const st = agents.get(id) ?? { n: 1, used: false, sent: 0 }
    agents.set(id, st)
    // A compacted conversation holds fewer messages than luna has seen: the thread no longer matches it, so start over.
    if (st.used && messages.length < st.sent) Object.assign(st, { n: st.n + 1, used: false, sent: 0 })
    let resumed = st.used
    const sentBefore = st.sent
    let prompt = resumed ? `${DELTA_HEADER}${render(messages.slice(st.sent)) || '(nothing new)'}\n` : full()
    let chars = prompt.length
    // Debug only: keep the last fresh prompt beside the thread file, to see what fills it.
    if (!resumed && debugOn()) await $.fs.write(`${threadPath(id, st.n)}.prompt.txt`, prompt).catch(() => undefined)
    let run = yield* ask(prompt, threadPath(id, st.n), allowed)
    if (run.failed && run.retry !== false) {
      // A thread that failed may be half-written: start another one with the whole conversation.
      st.n++
      st.used = false
      resumed = false
      prompt = full()
      chars += prompt.length
      run = yield* ask(prompt, threadPath(id, st.n), allowed)
    } else if (!run.failed && typeof run.reply === 'string') {
      // The thread already holds the prompt: the correction alone is enough.
      prompt = CORRECTION(run.reply)
      chars += prompt.length
      run = yield* ask(prompt, threadPath(id, st.n), allowed)
    }
    if (!run.failed && skipsTools(run.reply, JSON.stringify(messages).includes('"tool_result"'), taskText(messages), names)) {
      // One push; a second reply without tools stands as luna's answer.
      prompt = PUSH
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(id, st.n), allowed)
      // An empty pushed reply keeps the first one: luna once answered the push with {"say": "", "tools": []}.
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
      // A refusal can stick to its thread: luna answered "I can't run Bash from this interface" to the push and then to
      // an unrelated follow-up (follow scenario, spec 028 Docker run). One fresh thread gets one more try.
      if (!run.failed && skipsTools(run.reply, false, taskText(messages), names) && REFUSAL.test((run.reply as Reply).say)) {
        st.n++
        st.used = false
        resumed = false
        prompt = full()
        chars += prompt.length
        const fresh = yield* ask(prompt, threadPath(id, st.n), allowed)
        if (!fresh.failed && fresh.reply !== null && typeof fresh.reply !== 'string' && (fresh.reply.tools.length > 0 || fresh.reply.say)) run = fresh
      }
    } else if (!run.failed && stopsEarly(run.reply)) {
      // One push to go on; a second early stop stands as luna's answer.
      prompt = CONTINUE
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(id, st.n), allowed)
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
    }
    // An aborted step is not marked used: the thread may be half-written, so the next step starts it over.
    const wasAborted = next.signal.aborted
    if (!run.failed && !wasAborted) st.used = true
    const reply = run.reply
    if (typeof reply !== 'string' && reply !== null) st.sent = messages.length
    const ms = (await $.clock.now()) - t0
    $.ui.log(`${LOG} step ${e.index} of ${id} took ${ms} ms, prompt ${chars} chars, ${resumed ? 'resumed' : 'fresh'} thread, system ${system.length} catalog ${catalog(tools, types, hand).length} conversation ${render(messages).length} chars, ${names.length} tools, handback ${hand ? 'on' : 'off'}, messages ${messages.length} sent ${sentBefore}, codex_tools ${acc.tools.length ? acc.tools.join(' ') : 'none'}, usage ${acc.usage ? `in ${acc.usage.input_tokens} cached ${acc.usage.cached_input_tokens} out ${acc.usage.output_tokens}` : 'none'}`, { to: 'debug' })
    const tokens = acc.usage
    const failure = run.failed ? (run.fail ?? 'luna failed: run failed') : typeof reply === 'string' ? 'luna failed: unparsable reply' : null
    const before = ran.get(id)?.usage ?? ZERO
    ran.set(id, {
      outcome: wasAborted ? 'aborted' : failure === null ? 'done' : failure.startsWith('luna quota-paused') ? 'quota-paused' : 'failed',
      usage: {
        input_tokens: before.input_tokens + (tokens?.input_tokens ?? 0),
        cached_input_tokens: before.cached_input_tokens + (tokens?.cached_input_tokens ?? 0),
        output_tokens: before.output_tokens + (tokens?.output_tokens ?? 0),
      },
    })
    const turnUsage: TurnUsageOut | null = tokens
      ? {
          input_tokens: tokens.input_tokens - tokens.cached_input_tokens,
          output_tokens: tokens.output_tokens,
          cache_read_input_tokens: tokens.cached_input_tokens,
          cache_creation_input_tokens: 0,
          model: acc.slug ?? 'luna',
        }
      : null

    if (reply === null) return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: null, usage: turnUsage }

    const out: Reply = failure !== null ? handback({ say: failure, tools: [] }, hand) : handback(reply as Reply, hand)
    let index = 1 // block 0 is the live thinking line
    if (out.say) yield { kind: 'text', index: index++, text: out.say }
    for (const [n, tool] of out.tools.entries()) {
      yield { kind: 'tool', index, id: `luna_${e.turnId}_${e.index}_${n}`, name: tool.name }
      yield { kind: 'input', index, json: JSON.stringify(tool.input) }
      index++
    }
    const stopReason = out.tools.length > 0 ? 'tool_use' : 'end_turn'
    yield { kind: 'stop', stopReason, usage: turnUsage }
    return { turnId: e.turnId, index: e.index, answer: out.say, toolUses: out.tools, stopReason, usage: turnUsage }
  })
}
