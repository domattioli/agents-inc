import type { Register } from 'claude-code'
import { type Adapter, authKnown, type Outcome, type Reply } from './adapter'

// Spec 038 slice 1: the provider-neutral step loop. One state record per adapter (stateFor); the adapter supplies the
// model-specific prompt lines, pushes, argv and exit-code mapping (contracts/step-adapter.md).
export type { Adapter, Outcome, Reply } from './adapter'

const HANDBACK = 'SubagentHandback'
const HANDBACK_ARGS = '{ message: string }'
const HANDBACK_CUE = 'call SubagentHandback('
const RESULT_CAP = 20_000
const DESC_CAP = 500
const MCP_DESC_CAP = 200
// The step timer runs on $.clock.sleep, which is monotonic: time the host spends asleep does not count, so a Mac that
// sleeps mid-step does not fail the step on time alone (macOS stress run, 2026-10-25).
// Per run: the adapter's run timeout flag (`agents-inc run --timeout`) kills the model process at the limit; this
// hook's own timer is a backstop STEP_GRACE_S later. A Codex model call stalled with no output for the whole 300 s
// limit, then the step failed (macOS, 2026-11-11; rollout 01a1cb10 stops at 14:45:01). Default 60 s; normal steps take
// 3-25 s. The adapter's timeoutEnv (AGENTS_INC_LUNA_STEP_TIMEOUT_S for luna) overrides it.
export const STEP_TIMEOUT_S = 60
const STEP_GRACE_S = 15
// A stateless guest sleeps inside `agents-inc native step` between rate-limit retries (up to 65 s, native_http.WAIT_BUDGET_S).
// `--timeout` is only the socket timeout of each request, so the sleeps are bounded by this hook timer alone: it waits
// that long extra, or a 65 s wait would be killed at limit + grace = 75 s.
export const RETRY_WAIT_S = 65
// A live "still working" line this often while a run is in flight.
const HEARTBEAT_MS = 10_000
export function stepTimeoutS(raw: string | undefined): number {
  const n = Number(raw)
  return raw !== undefined && raw.trim() !== '' && Number.isFinite(n) && n >= 5 && n <= 3600 ? Math.round(n) : STEP_TIMEOUT_S
}
const MODEL_LINE = /You are powered by the model|The exact model ID is/
// luna asked "May I run these five requested wc commands?" and "Proceed?" on later steps, after a first step that
// worked (macOS stress, 2026-11-11, tools.9 and par.4): the rule rides every prompt, the delta header included.
const NO_ASK = 'Nobody can answer a question here: never ask one and never ask for confirmation or permission. ' +
  'Decide yourself and act now.\n'
// The host's instructions carry session-start steps for the main session ("Call Skill caveman", a handoff check);
// luna asked whether to follow them instead of the task (rollout 01a1cb50-d730, 2026-11-11).
const SUBAGENT_NOTE = 'You are a subagent. Session-start steps in the instructions (a required Skill call, a handoff ' +
  'check) are for the main session: skip them unless the task asks for them.\n'
const deltaHeader = (a: Adapter) =>
  'New messages since your last reply. Same rules: reply with one JSON object {say, tools}; act on the latest messages; finish as the rules said. ' +
  a.deltaRule +
  NO_ASK
// luna sometimes reads Codex's read-only sandbox note as its own and answers that it cannot run a tool, calling none.
// luna also read Codex's filesystem note (`<permission_profile>... :root`) as "read access only to root" and handed back
// "Blocked before reading any files" with no tool run (macOS, 2026-11-11, rollout 01a1cb0e).
const REFUSAL = /(can['’]?t|cannot|unable to|not able to)\s+(run|read|inspect|execute|access|use|report|request|call|make|issue|perform)|tools?\b[^.]*\b(disabled|unavailable|not available)|permission profile|read access only|\bsandbox(ed)?\b[^.]*\b(denies|blocks|only|restrict)|^\s*blocked\b|\b(did not|didn['’]t) (read|run) (any|the)\b/im
const handbackText = (reply: Reply) =>
  [reply.say, ...reply.tools.map(t => { const m = (t.input as { message?: unknown } | null)?.message; return typeof m === 'string' ? m : '' })].join('\n')
// A refusal: the reply says it cannot run the tools, in "say" or in a hand-back message.
export const refuses = (reply: Reply | string | null): boolean =>
  reply !== null && typeof reply !== 'string' && reply.tools.every(t => t.name === HANDBACK) && REFUSAL.test(handbackText(reply))
// A first reply that runs nothing is pushed once when it refuses a tool, or when the task names a catalog tool:
// luna answered "A=0" for `wc -l a.txt` without running Bash (Docker stress run, 2026-10-24).
export function skipsTools(reply: Reply | string | null, ranTool: boolean, task = '', names: readonly string[] = []): boolean {
  if (ranTool || reply === null || typeof reply === 'string') return false
  // A hand-back alone, before a needed tool ran, counts when it refuses (run 2 above) or when the task names a catalog
  // tool: luna handed back "A=100 B=75" for `wc -l a.txt with Bash` after running only two Skill calls, the values taken
  // from a conversation it wrote itself (macOS stress, 2026-11-11, rollout 01a1cc20-74b1).
  const named = names.some(n => n !== HANDBACK && namesTool(task, n))
  if (reply.tools.length > 0) return reply.tools.every(t => t.name === HANDBACK) && (refuses(reply) || named)
  return REFUSAL.test(reply.say) || named
}
// Whether the conversation already holds a tool run that counts for skipsTools: any tool result, unless the task names
// catalog tools, in which case one of those must have been called (a Skill call from a session-start rule does not count).
export function ranTool(messages: readonly unknown[], task: string, names: readonly string[]): boolean {
  const raw = JSON.stringify(messages)
  if (!raw.includes('"tool_result"')) return false
  const named = names.filter(n => n !== HANDBACK && namesTool(task, n))
  return named.length === 0 || named.some(n => raw.includes(`"name":${JSON.stringify(n)}`))
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
// steps5 run 9 (2026-11-11): "Results for d.txt and e.txt have not been provided, so their counts are unavailable."
// luna ran one of five commands and answered "A=173. I haven't run the other four commands yet." (steps5, spec 028 Docker run).
// luna also said "the other four remain unrun" and "their results have not arrived".
const UNFINISHED = /\b(haven['’]?t|have not|not yet|yet to)\b[^.]*\b(run|read|done|finish|complete|execute)|\bremaining (\w+ )?(commands?|steps?)\b|\bremain(s)? (unrun|to run|undone)\b|\bunrun\b|\b(have|has) not arrived\b|\b(haven|hasn)['’]?t arrived\b|\b(have|has|had) not been (provided|returned|received|run)\b|\b(results?|counts?|values?|outputs?) (are|is|were) (still )?(unavailable|missing|pending)\b|\bnot yet (available|provided)\b|\bremaining (\w+ )?results?\b/i
export const stopsEarly = (reply: Reply | string | null): boolean =>
  reply !== null && typeof reply !== 'string' && reply.tools.length === 0 && UNFINISHED.test(reply.say)
const CORRECTION = (why: string) => `Your previous reply was rejected: ${why}. Reply with exactly one JSON object, only tools from the Tools list.\n`
const TOOL_TYPES_PATH = '.claude-plugin/types/claude-code-tools/index.d.ts'

// The slug comes from the adapter's status verb, never from a fixed string here.
const header = (a: Adapter, slug: string) =>
  'You drive an agent loop with real tools. To run a tool, name it in "tools"; the host runs it and its result arrives ' +
  'in the next step. Bash, Read and every other catalog tool work this way, so never answer that you cannot run one.\n' +
  a.toolHome +
  'Example, to run a shell command: {"say": "", "tools": [{"name": "Bash", "input": {"command": "ls"}}]}\n' +
  a.identity(slug) +
  a.ownTools +
  'Your reply is the JSON object itself, written as your final message text. Every tool in the catalog below is real and available: call it ' +
  'by naming it in "tools", and its result arrives in the next step. Never report a catalog tool as unavailable.\n' +
  'Report only values you read in a tool result in this conversation; never guess one. The git status and other context ' +
  'in the system prompt is a snapshot from session start and may be stale: when the task asks for a command, run it.\n' +
  'A Read result starts each line with its line number and a tab: the last of those numbers is the line count of the part ' +
  'read. To count a file\'s lines, Read it whole (no offset or limit) or run wc -l.\n' +
  'A task is done only when every step it names has run: keep requesting tools until each result the report needs is in.\n' +
  `A tool result over ${RESULT_CAP} characters is cut to its first ${RESULT_CAP}: read files about 150 lines at a time with Read offset and limit, never a whole large file,.\n` +
  'Act on the latest messages; earlier ones are history.\n' + NO_ASK + SUBAGENT_NOTE +
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

// Ungrounded values (steps5 runs 7 and 10, 2026-11-11): luna handed back "A=173 B=95 C=41 D=7 E=2" after four Bash steps, and
// "C=208 D=64 E=127" after two, numbers no tool produced. In a hand-back, a KEY=<number> or KEY: <number> whose number is in
// no tool result and not in the task text is ungrounded. Only checked once the conversation holds a tool result.
const KEYED_NUMBER = /\b([A-Za-z][A-Za-z0-9_]*)\s*[=:]\s*(-?\d+(?:\.\d+)?)(?![\d.]*\d)/g
export function ungroundedValues(reply: Reply | string | null, messages: readonly Msg[], task: string): string[] {
  if (reply === null || typeof reply === 'string' || !reply.tools.every(t => t.name === HANDBACK)) return []
  const text = handbackText(reply)
  if (text.trim() === '') return []
  const results = messages.flatMap(m => m.content ?? []).filter(b => b.type === 'tool_result')
  if (results.length === 0) return []
  const known = `${results.map(b => resultText(b.content)).join('\n')}\n${task}`
  const bad: string[] = []
  for (const m of text.matchAll(KEYED_NUMBER)) {
    const n = m[2].replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (!new RegExp(`(?<![\\d.])${n}(?![\\d])`).test(known) && !bad.includes(`${m[1]}=${m[2]}`)) bad.push(`${m[1]}=${m[2]}`)
  }
  return bad
}
const ungroundedPush = (pairs: readonly string[]) =>
  `Your report gives ${pairs.join(', ')}, but no tool result in this conversation contains ${pairs.length > 1 ? 'those values' : 'that value'}. ` +
  'A reported value must come from a tool result in this conversation, never from a guess. Run the missing tool calls now: name them in "tools". ' +
  'Reply with exactly one JSON object.\n'
// Admitted gap (steps5 run 5, 2026-11-11): luna ran one wc -l and handed back "A=173 ... Results for b.txt through e.txt were not
// included in the messages available to me; their counts remain unverified." The value was grounded, so nothing else fired.
// A hand-back that says a result is not obtained gets one push. Cue: a result noun followed, in the same clause, by a
// not-obtained phrase, or the word "unverified". Guard: when the task has countable KEY=<n> tokens and the hand-back gives
// a grounded value for every one, whatever it says stands.
const NOUN = '(?:results?|counts?|outputs?|values?|files?)'
const GAP = new RegExp(`\\b${NOUN}\\b[^\\n;]{0,80}?\\b(?:not (?:included|provided|available|obtained)|unavailable)\\b|\\bunverified\\b`, 'i')
const TASK_KEY = /\b([A-Za-z][A-Za-z0-9_]*)=<n>/g
export function admitsGap(reply: Reply | string | null, messages: readonly Msg[], task: string): boolean {
  if (reply === null || typeof reply === 'string' || !reply.tools.every(t => t.name === HANDBACK)) return false
  const text = handbackText(reply)
  if (text.trim() === '' || !GAP.test(text)) return false
  const keys = [...new Set([...task.matchAll(TASK_KEY)].map(m => m[1]))]
  if (keys.length === 0) return true
  const bad = ungroundedValues(reply, messages, task).map(p => p.split('=')[0])
  const given = new Set([...text.matchAll(KEYED_NUMBER)].map(m => m[1]))
  return !keys.every(k => given.has(k) && !bad.includes(k))
}
const GAP_PUSH = 'You said some results are missing. Run the missing tool calls now, then hand back. Reply with exactly one JSON object.\n'
type Block = { type: string; [field: string]: unknown }
export type Msg = { role: 'user' | 'assistant'; content: Block[] }
type Tool = { name: string; description: string; mcp?: boolean }
type Thinking = { kind: 'thinking'; index: number; text: string }
type Usage = { input_tokens: number; cached_input_tokens: number; output_tokens: number }
type Cli = {
  process: { spawn: (a: { argv: string[]; cwd?: string; input?: string }) => AsyncGenerator<{ stream: 'stdout' | 'stderr'; text: string }, { code: number | null }> }
  ui: { log: (message: string, options: { to: 'debug' }) => unknown }
  session: { id: () => unknown }
}
export type Status = { offered: boolean; slug: string; reason?: string; write_dirs?: string[]; tools?: boolean }
type Ran = { outcome: 'done' | 'failed' | 'quota-paused' | 'aborted'; usage: Usage }
// Per subagent: the thread file it keeps, whether a run has used it, and how many api messages the model has seen.
type AgentState = { n: number; used: boolean; sent: number }
const ZERO: Usage = { input_tokens: 0, cached_input_tokens: 0, output_tokens: 0 }
let toolTypes: string | undefined // text of the engine-written built-in tool argument types, read once

type TurnUsageOut = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
  model: string
}

// The system prompt names a placeholder Claude model; luna is not that model, so those lines go.
// The harness's commit-attribution reminder names a Claude model to credit; luna read it as its own identity (2026-11-07).
const ATTRIBUTION = /<system-reminder>\s*Attribution for git commits[\s\S]*?<\/system-reminder>/g
const stripModelLines = (text: string) =>
  text.replace(ATTRIBUTION, '').split('\n').filter(l => !MODEL_LINE.test(l)).join('\n')

// The harness's skill-listing reminder, cut to the skill names: luna can still call Skill by name, without ~25k chars
// of descriptions in every fresh prompt.
const SKILL_LIST = /(<system-reminder>\nThe following skills are available for use with the Skill tool:\n)([\s\S]*?)(<\/system-reminder>)/
export const trimSkillList = (text: string) =>
  text.replace(SKILL_LIST, (_, head: string, body: string, tail: string) => {
    const names = body.split('\n').map(l => /^- (\S+?)(?::\s|$)/.exec(l)?.[1]).filter(Boolean)
    return `${head}${names.join(', ')}\n${tail}`
  })

const safe = (s: string) => s.replace(/[^\w.-]/g, '_')
// AGENTS_INC_LUNA_DEBUG for luna.
const debugOn = (nick: string) =>
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[`AGENTS_INC_${nick.toUpperCase()}_DEBUG`] === '1'

const cap = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}\n[truncated ${s.length - n} chars]` : s)
// #187: a tool result is cut to its head; the model is told so, and how to read the rest in pieces that fit.
export const capResult = (s: string, n = RESULT_CAP) =>
  s.length > n ? `${s.slice(0, n)}\n[truncated ${s.length - n} chars: this result was cut at ${n} chars, head only. Read about 150 lines at a time with offset and limit, or narrow with grep, to see the rest.]` : s

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

// The tools a stateless guest agent is offered: the core file and shell tools. A real session lists 70+ tools (MCP,
// deferred, orchestration); sent whole they pushed the first step of a codestral agent over its prompt cap (2026-11-11).
// SubagentHandback is added by the caller, not listed here.
export const GUEST_TOOLS: readonly string[] = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'NotebookEdit']
export const guestTools = (tools: readonly Tool[]): Tool[] => tools.filter(t => !t.mcp && GUEST_TOOLS.includes(t.name))

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
        out.push(`tool result${b.is_error ? ' (error)' : ''}: ${capResult(text)}`)
      }
      else out.push(`${m.role}: [${b.type}]`)
    }
  }
  return out.join('\n')
}

// A stateless guest sends the whole conversation to a third-party provider on every step. Four host reminders are
// pure noise there: the Bash sandbox allow and deny lists, the Skill tool listing (a guest has no Skill tool), the
// deferred-tools listing (a guest has no ToolSearch tool) and empty reminders. Only a text block that is exactly one whole reminder is ever removed, matched by what its body starts
// with; anything unrecognised, and every kept block, passes through untouched. Thread adapters never call this.
const WHOLE_REMINDER = /^<system-reminder>([\s\S]*)<\/system-reminder>$/
const NOISE_HEADS = [
  '## Bash command sandbox',
  'The following skills are available for use with the Skill tool:',
  'The following deferred tools are now available via ToolSearch.',
]
// The host's instruction-files reminder: fixed opening sentence, then "Contents of <path>" entries. Dropped whole, even
// when it also carries user-context sections (memory index, email, git status): none of it goes to a free provider.
const INSTRUCTIONS_HEAD = 'Codebase and user instructions are shown below.'
const isInstructions = (body: string) => body.startsWith(INSTRUCTIONS_HEAD) && /^Contents of /m.test(body)
export function isNoiseReminder(text: unknown): boolean {
  if (typeof text !== 'string') return false
  const m = WHOLE_REMINDER.exec(text.trim())
  if (!m || /<\/?system-reminder>/.test(m[1])) return false
  const body = m[1].trim()
  return body === '' || NOISE_HEADS.some(h => body.startsWith(h)) || isInstructions(body)
}
export function dropNoiseReminders(messages: readonly Msg[]): Msg[] {
  try {
    return messages.map(m => ({ ...m, content: (m.content ?? []).filter(b => !(b.type === 'text' && isNoiseReminder(b.text))) }))
      .filter((m, i) => m.content.length > 0 || (messages[i].content ?? []).length === 0)
  } catch {
    return Array.isArray(messages) ? [...messages] : [] // removal never fails a step
  }
}

// The system prompt's "# Memory" section (how to write memory files, with the memory directory) is of no use to a guest
// and holds a host path. Cut from its heading to the next top-level heading; no heading, no change.
export function dropMemorySection(system: string): string {
  try {
    return system.replace(/^# Memory\n[\s\S]*?(?=^# |(?![\s\S]))/m, '')
  } catch {
    return system
  }
}

// A chat-only model (failed tool probe, D76 condition 4) is never told to use tools.
const chatHeader = (a: Adapter, slug: string) =>
  a.identity(slug) +
  'You have no tools: nothing in this conversation can be run, read or written by you. Answer from the conversation alone and never ask for a tool.\n' +
  NO_ASK + SUBAGENT_NOTE +
  'Reply with exactly one JSON object and nothing else: {"say": "<your answer>", "tools": []}\n'
export function buildPrompt(a: Adapter, slug: string, system: string, tools: string, messages: readonly Msg[], hand = true, chat = false): string {
  return `${chat ? chatHeader(a, slug) : header(a, slug)}${hand ? HANDBACK_RULES : FINAL_RULES}\nSystem prompt:\n${system}\n\nTools:\n${tools}\n\nConversation:\n${render(messages) || '(empty)'}\n`
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

type Register$ = Cli & { agent: { register: (a: Record<string, unknown>) => Promise<unknown> } }

// Per adapter, the state that was module-level in luna.ts. One record per adapter for the life of the module, so state
// survives across steps the way luna.ts module variables did. The engine accepts `on` only when passed to a top-level
// function, so the hooks live in registerLoop (below) and read this record, not a closure.
type LoopState = {
  agent: string // nickname
  types: string[] // `agents-inc:<nickname>`
  log: string // debug-line prefix
  quota: string // `<nickname> quota-paused`
  ids: Set<string>
  agents: Map<string, AgentState>
  threadTotals: Map<string, Usage> // last running total a thread adapter reported per thread file
  cwd: string
  sessionId: string
  slug: string
  offered: boolean // what the adapter's status verb said at session start
  chatOnly: boolean // status said `tools: false` (probe failed): no tool catalog, no pushes to use tools
  writeDirs: string[] // write directories from status at session start (key-store adapters)
  dirs: Map<string, string[]> // per agent: write directories the begin call returned (authorization can come later)
  begun: Map<string, Promise<void>> // per agent: the begin call
  ran: Map<string, Ran> // per agent: what its steps cost and how the last one ended
  runTimeoutFlag: boolean // false once the installed runtime refused the timeout flag
}
const states = new Map<Adapter, LoopState>()
function stateFor(adapter: Adapter): LoopState {
  let S = states.get(adapter)
  if (!S) {
    const agent = adapter.nickname
    S = {
      agent, types: [`agents-inc:${agent}`], log: `agents-inc ${agent}:`, quota: `${agent} quota-paused`,
      ids: new Set(), agents: new Map(), threadTotals: new Map(), cwd: '', sessionId: 'session', slug: agent,
      offered: false, chatOnly: false, writeDirs: [], dirs: new Map(), begun: new Map(), ran: new Map(), runTimeoutFlag: true,
    }
    states.set(adapter, S)
  }
  return S
}

// The dir is git-ignored; agents-inc creates it. A fresh thread after a failed resume gets the suffix -2, -3...
const threadPath = (S: LoopState, agentId: string, n: number) =>
  `${S.cwd || '.'}/.scratch/agents-inc-${safe(S.agent)}/${safe(S.sessionId)}/${safe(agentId)}${n > 1 ? `-${n}` : ''}.thread`

// The adapter's status|begin|end verbs (`agents-inc luna ...` for luna).
async function verbCli($: Cli, adapter: Adapter, args: string[], cwd?: string): Promise<{ code: number | null; out: string; err: string }> {
  const argv = [...adapter.cli, ...args]
  const stream = $.process.spawn({ argv, cwd })
  let out = ''
  let err = ''
  for (;;) {
    const n = await stream.next()
    if (n.done) return { code: n.value.code, out, err }
    if (n.value.stream === 'stdout') out += n.value.text
    else err += n.value.text
  }
}

async function verbStatus($: Cli, adapter: Adapter): Promise<Status | null> {
  try {
    const r = await verbCli($, adapter, ['status', '--json'])
    const d = JSON.parse(r.out) as Status
    if (r.code === 0 && typeof d.offered === 'boolean' && typeof d.slug === 'string') return d
  } catch {
    // no readable status: the type is not offered
  }
  return null
}

// Spec 028 D6 item 1: pin the working tree once per agent. Failures are logged; the run goes on (Q2).
function ensureBegin($: Cli, adapter: Adapter, id: string, task: string): Promise<void> {
  const S = stateFor(adapter)
  let p = S.begun.get(id)
  if (!p) {
    p = verbCli($, adapter, ['begin', '--session', S.sessionId, '--agent', id, '--cwd', S.cwd || '.', '--task', task.slice(0, 200)])
      .then(r => {
        if (r.code !== 0) $.ui.log(`${S.log} begin exited ${r.code}: ${failureText(r.err)}`, { to: 'debug' })
        try {
          const dirs = (JSON.parse(r.out) as { write_dirs?: unknown }).write_dirs
          if (r.code === 0 && Array.isArray(dirs)) S.dirs.set(id, dirs.filter((d): d is string => typeof d === 'string'))
        } catch {
          // no readable begin answer: the status dirs stay in force
        }
      })
      .catch(err => { $.ui.log(`${S.log} begin failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' }) })
    S.begun.set(id, p)
  }
  return p
}

// Called from mod.ts (through luna.ts): a plugin's hooks.json names one module, and a module may register session.start once.
// The type is registered only when the engine gives what the native type needs and the adapter's status verb offers it.
// `known`: a status already read for this adapter (registry.ts reads every model in one `native status` call); omitted,
// the adapter's own status verb is asked (luna).
export async function registerAgent($: Register$, adapter: Adapter, e: { cwd: string }, known?: Status | null): Promise<void> {
  const S = stateFor(adapter)
  S.cwd = e.cwd
  S.offered = false
  S.runTimeoutFlag = true
  // T021a: an adapter whose auth the loop does not know registers nothing, so no step can reach it.
  if (!authKnown(adapter)) {
    $.ui.log(`${S.log} not registered: unknown auth ${JSON.stringify((adapter as { auth?: unknown }).auth)}`, { to: 'debug' })
    return
  }
  // The contract check: the status call needs a streaming $.process.spawn, the registration needs $.agent.register.
  // A build without either leaves the type unregistered, and the debug log says which.
  const status = known === undefined ? await verbStatus($, adapter) : known
  if (!status) {
    $.ui.log(`${S.log} not registered: ${adapter.cli.join(' ')} status gave no usable answer (needs a streaming $.process.spawn)`, { to: 'debug' })
    return
  }
  S.slug = status.slug
  S.chatOnly = status.tools === false
  S.writeDirs = Array.isArray(status.write_dirs) ? status.write_dirs.filter((d): d is string => typeof d === 'string') : []
  if (!status.offered) {
    $.ui.log(`${S.log} not registered: ${status.reason ?? 'not offered'}`, { to: 'debug' })
    return
  }
  try {
    S.sessionId = String((await $.session.id()) || S.sessionId)
  } catch {
    // keep the default
  }
  try {
    // No tools and no permissionMode: the agent inherits the parent's, like any native subagent.
    await $.agent.register({
      name: S.agent,
      description: S.chatOnly ? `${adapter.description(status.slug)} Chat only, no tools: its tool-protocol probe failed, so it answers from the conversation alone.` : adapter.description(status.slug),
      prompt: AGENT_PROMPT,
      model: 'haiku', // placeholder: turn.step never calls it for this agent
    })
    S.offered = true
  } catch (err) {
    $.ui.log(`${S.log} not registered: $.agent.register failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' })
  }
}

const FILE_WRITERS: Readonly<Record<string, string>> = { Write: 'file_path', Edit: 'file_path', NotebookEdit: 'notebook_path' }
// Lexical path resolution against the agent cwd (the mod has no filesystem stat, so symlinks are not followed).
function resolvePath(raw: string, cwd: string): string {
  const out: string[] = []
  for (const part of (raw.startsWith('/') ? raw : `${cwd || '.'}/${raw}`).split('/')) {
    if (part === '..') out.pop()
    else if (part !== '' && part !== '.') out.push(part)
  }
  return `/${out.join('/')}`
}
// D76 condition 3: the file-writing tool calls in a reply whose target lies outside every write directory (a missing
// path counts as outside). Bash is not checked.
export function outsideWrites(reply: Reply | string | null, cwd: string, dirs: readonly string[]): { name: string; path: string }[] {
  if (reply === null || typeof reply === 'string') return []
  const roots = dirs.map(d => resolvePath(d, cwd))
  const bad: { name: string; path: string }[] = []
  for (const t of reply.tools) {
    const field = FILE_WRITERS[t.name]
    if (field === undefined) continue
    const raw = (t.input as Record<string, unknown> | null)?.[field]
    const path = typeof raw === 'string' && raw !== '' ? resolvePath(raw, cwd) : ''
    if (path === '' || !roots.some(r => path === r || path.startsWith(`${r}/`))) bad.push({ name: t.name, path: typeof raw === 'string' ? raw : '(none)' })
  }
  return bad
}
const writeRefusal = (bad: readonly { name: string; path: string }[], dirs: readonly string[]) =>
  `Tool refused: ${bad.map(b => `${b.name} ${b.path}`).join(', ')} is outside the directories this agent may write in (${dirs.join(', ') || 'none recorded'}). ` +
  'Nothing was written. Write only inside those directories, or report without writing.'

const RETRIED = ' (after one retry on a fresh thread)'

// The hooks of one native type (loop.test.ts drives one adapter this way).
export function registerLoop(on: Parameters<Register>[0], adapter: Adapter): void {
  registerLoops(on, [adapter])
}

// The hooks of every native type, registered once: the engine refuses a second registration of an event in one module
// (`on("agent.spawn") registered twice`), so one set of hooks serves all adapters and picks the one that owns the agent.
export function registerLoops(on: Parameters<Register>[0], adapters: readonly Adapter[]): void {
  const byType = new Map<string, Adapter>(adapters.map(a => [stateFor(a).types[0], a]))
  const owner = (id: string) => adapters.find(a => stateFor(a).ids.has(id))

  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    const adapter = byType.get(e.subagentType)
    if (adapter && r.agentId) {
      stateFor(adapter).ids.add(r.agentId)
      void ensureBegin($, adapter, r.agentId, String(e.prompt ?? ''))
    }
    return r
  })

  // A session that registered the type before a switch-off still hides it; a failed guard hides it too. Other types
  // pass through untouched.
  on('agent.offer', (_$, e, next) => {
    const a = byType.get(e.agent)
    return a === undefined || stateFor(a).offered ? next(e) : { isOffered: false }
  }).catch((_$, e, next) => (byType.has(e.agent) ? (next.called ? next(e) : { isOffered: false }) : next(e)))

  // Spec 028 D6 item 2: verify the tree against the begin snapshot and write the return row. The parent verifies (Q2).
  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    const id = e.agentId
    const adapter = id === undefined ? undefined : owner(id)
    if (id === undefined || adapter === undefined) return r
    const S = stateFor(adapter)
    const done = S.ran.get(id) ?? { outcome: 'failed' as const, usage: ZERO }
    const outcome = e.isAborted ? 'aborted' : done.outcome
    try {
      await S.begun.get(id)
      const end = await verbCli($, adapter, ['end', '--session', S.sessionId, '--agent', id, '--cwd', S.cwd || '.', '--outcome', outcome, '--usage', JSON.stringify(done.usage)])
      if (end.code !== 0) {
        $.ui.log(`${S.log} end exited ${end.code}: ${failureText(end.err)}`, { to: 'debug' })
        return r
      }
      const rec = JSON.parse(end.out) as { snapshot?: string; changed?: string[] }
      if (typeof rec.snapshot === 'string' && rec.snapshot.startsWith('changed')) {
        const paths = (rec.changed ?? []).slice(0, 5).join(', ')
        return { ...r, text: `${r.text}\n[agents-inc ${S.agent}] The working tree changed while this agent ran (${rec.snapshot}): ${paths}. Check it before you rely on the report.` }
      }
    } catch (err) {
      $.ui.log(`${S.log} end failed: ${String((err as Error)?.message ?? err)}`, { to: 'debug' })
    }
    return r
  })

  on('turn.step', async function* ($, e, next) {
    const id = e.agentId
    const live = adapters.filter(a => stateFor(a).offered)
    if (id === undefined || live.length === 0) return yield* next(e)
    let adapter = owner(id)
    if (adapter === undefined) {
      // The spawn hook may not have recorded the id yet; the agent list knows the type.
      const listed = await $.agent.list().then(l => l.find(a => a.id === id)?.type ?? '', () => null)
      if (listed === null) {
        // Fail closed: a native step must never reach the placeholder model.
        const text = `${stateFor(live[0]).log} cannot identify agent ${id}; step not sent to the placeholder model`
        yield { kind: 'text', index: 0, text }
        yield { kind: 'stop', stopReason: 'end_turn', usage: null }
        return { turnId: e.turnId, index: e.index, answer: text, toolUses: [], stopReason: 'end_turn', usage: null }
      }
      adapter = byType.get(listed)
      if (adapter === undefined) return yield* next(e)
      stateFor(adapter).ids.add(id)
    }
    if (!stateFor(adapter).offered) return yield* next(e)
    const S = stateFor(adapter)
    await ensureBegin($, adapter, id, taskText((await $.session.messages({ agentId: id, as: 'api' }).catch(() => [])) as Msg[]))

    const t0 = await $.clock.now()
    // Shown live, not recorded: the window has something to show while luna works.
    yield { kind: 'thinking', index: 0, text: `${S.agent} is working on step ${e.index}…` }
    const aborted = new Promise<null>(res => {
      if (next.signal.aborted) res(null)
      else next.signal.addEventListener('abort', () => res(null), { once: true })
    })

    const acc: { usage: Usage | null; slug?: string; tools: string[] } = { usage: null, tools: [] } // summed over this step's runs
    const STOP = Symbol('stop')
    const TICK = Symbol('tick')
    // The engine takes only a literal name in $.env.get, so each adapter's env var is read here by name.
    const limitS = stepTimeoutS(adapter.timeoutEnv === 'AGENTS_INC_LUNA_STEP_TIMEOUT_S'
      ? await $.env.get('AGENTS_INC_LUNA_STEP_TIMEOUT_S').catch(() => undefined)
      : adapter.timeoutEnv === 'AGENTS_INC_NATIVE_STEP_TIMEOUT_S'
        ? await $.env.get('AGENTS_INC_NATIVE_STEP_TIMEOUT_S').catch(() => undefined)
        : undefined)
    const never = () => new Promise<never>(() => {})

    // One run: stderr progress lines become thinking chunks as they arrive; stdout is the reply.
    const ask = async function* (prompt: string, thread: string, allowed: ReadonlySet<string>): AsyncGenerator<Thinking, Outcome> {
      const timer = new AbortController()
      const started = await $.clock.now()
      const flag = S.runTimeoutFlag
      const stop = Promise.race([
        aborted.then(() => STOP),
        $.clock.sleep((flag ? limitS + STEP_GRACE_S + (adapter.kind === 'stateless' ? RETRY_WAIT_S : 0) : limitS) * 1000, { signal: timer.signal }).then(() => STOP, never),
      ])
      const stream = $.process.spawn({
        argv: adapter.argv({ nickname: S.agent, provider: adapter.provider, slug: S.slug }, { thread, cwd: S.cwd, timeoutS: flag ? limitS : null, session: S.sessionId, agent: id }),
        cwd: S.cwd || undefined,
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
          // A thread adapter (Codex) reports the thread's running total: this run's share is the rise since the last report.
          // A stateless adapter reports each run's own usage.
          const total: Usage = {
            input_tokens: Number(data.input_tokens) || 0,
            cached_input_tokens: Number(data.cached_input_tokens) || 0,
            output_tokens: Number(data.output_tokens) || 0,
          }
          const before = adapter.kind === 'thread' ? S.threadTotals.get(thread) ?? ZERO : ZERO
          if (adapter.kind === 'thread') S.threadTotals.set(thread, total)
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
        let chunk = stream.next() // held across heartbeats: a tick must not ask the stream twice
        for (;;) {
          const tick = new AbortController()
          const n = await Promise.race([chunk, stop, $.clock.sleep(HEARTBEAT_MS, { signal: tick.signal }).then(() => TICK, never)])
          tick.abort()
          if (n === TICK) {
            // Shown live while Codex is silent, so a slow or stalled step is visible before the limit.
            const s = Math.round(((await $.clock.now()) - started) / 1000)
            yield { kind: 'thinking', index: 0, text: `${S.agent} is still working on step ${e.index} (${s} s of ${limitS} s)…` }
            continue
          }
          if (n === STOP) {
            void stream.return(undefined as never).catch(() => {})
            return next.signal.aborted ? { reply: null, failed: false } : { reply: 'agents-inc run timed out', failed: true, fail: adapter.timeoutText(limitS) }
          }
          chunk = stream.next()
          if (n.done) {
            lastOut = stdout.slice(0, RESULT_CAP)
            if (pending) take(pending)
            for (const text of lines.splice(0)) yield { kind: 'thinking', index: 0, text }
            if (n.value.code === 0) return { reply: pickReply(said, stdout, allowed), failed: false }
            if (flag && adapter.rejectsTimeout(n.value.code, stderr)) {
              // An installed agents-inc older than this mod has no --timeout: run again without it; this hook's timer
              // then holds the limit alone.
              S.runTimeoutFlag = false
              $.ui.log(`${S.log} agents-inc run has no --timeout; the step limit falls back to this hook's timer`, { to: 'debug' })
              timer.abort()
              return yield* ask(prompt, thread, allowed)
            }
            const why = `agents-inc run exited ${n.value.code ?? n.value.signal}, stdout ${stdout.length} chars: ${failureText(stderr)}`
            $.ui.log(`${S.log} ${why}`, { to: 'debug' })
            return adapter.classify(n.value.code, stderr, why, limitS) ?? { reply: why, failed: true, fail: `${S.agent} failed: run exited ${n.value.code}: ${failureText(stderr)}` }
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
        return { reply: `agents-inc run failed: ${why}`, failed: true, fail: `${S.agent} failed: could not run agents-inc: ${why}` }
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
    // A chat-only model gets an empty catalog; the hand-back tool stays, because it is how the turn ends.
    const offeredTools = S.chatOnly ? [] : adapter.kind === 'stateless' ? guestTools(tools) : tools
    const names = [...offeredTools.filter(t => t.name !== HANDBACK).map(t => t.name), ...(hand ? [HANDBACK] : [])]
    const allowed = new Set(names)
    const composed = await $.prompt.compose({ tools: names }).catch(() => ({ sections: [] }))
    const fullSystem = [...composed.sections.map(s => stripModelLines(s.text)), AGENT_PROMPT].join('\n\n')
    const system = adapter.kind === 'stateless' ? dropMemorySection(fullSystem) : fullSystem
    const types = await readToolTypes($)
    // Stateless only: thread adapters (luna, sol, terra, astra) get the messages exactly as before.
    const sentMessages = adapter.kind === 'stateless' ? dropNoiseReminders(messages) : messages
    const full = () => buildPrompt(adapter, S.slug, system, catalog(offeredTools, types, hand), sentMessages, hand, S.chatOnly)
    // A stateless adapter keeps no thread: every run gets the whole conversation, and a correction or push rides after
    // it with the reply it answers (spec 038 R3). A thread adapter sends the follow-up text alone.
    const stateless = adapter.kind === 'stateless'
    let lastOut = ''
    const more = (text: string) => (stateless ? `${full()}\nYour previous reply:\n${lastOut || '(empty)'}\n${text}` : text)

    const st = S.agents.get(id) ?? { n: 1, used: false, sent: 0 }
    S.agents.set(id, st)
    // A compacted conversation holds fewer messages than luna has seen: the thread no longer matches it, so start over.
    if (st.used && messages.length < st.sent) Object.assign(st, { n: st.n + 1, used: false, sent: 0 })
    let resumed = st.used && !stateless
    const sentBefore = st.sent
    let prompt = resumed ? `${deltaHeader(adapter)}${render(messages.slice(st.sent)) || '(nothing new)'}\n` : full()
    let chars = prompt.length
    // Debug only: keep the last fresh prompt beside the thread file, to see what fills it.
    if (!resumed && debugOn(S.agent)) await $.fs.write(`${threadPath(S, id, st.n)}.prompt.txt`, prompt).catch(() => undefined)
    let run = yield* ask(prompt, threadPath(S, id, st.n), allowed)
    if (run.failed && run.retry !== false) {
      // A thread that failed may be half-written: start another one with the whole conversation.
      st.n++
      st.used = false
      resumed = false
      prompt = run.asked ? adapter.pushes.asked + full() : full()
      chars += prompt.length
      run = yield* ask(prompt, threadPath(S, id, st.n), allowed)
      if (run.failed && run.fail && !run.fail.startsWith(S.quota)) run = { ...run, fail: run.fail + RETRIED }
    }
    // After a retry too: the fresh thread answered in prose once and the step ended "unparsable reply" with no
    // correction (macOS, 2026-11-11, rollout 01a1cb16-2b78).
    if (!run.failed && typeof run.reply === 'string') {
      // The thread already holds the prompt: the correction alone is enough.
      prompt = more(CORRECTION(run.reply))
      chars += prompt.length
      run = yield* ask(prompt, threadPath(S, id, st.n), allowed)
    }
    if (!run.failed && !S.chatOnly && skipsTools(run.reply, ranTool(messages, taskText(messages), names), taskText(messages), names)) {
      // One push; a second reply without tools stands as luna's answer.
      prompt = more(adapter.pushes.refusal)
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(S, id, st.n), allowed)
      // An empty pushed reply keeps the first one: luna once answered the push with {"say": "", "tools": []}.
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
      // A refusal can stick to its thread: luna answered "I can't run Bash from this interface" to the push and then to
      // an unrelated follow-up (follow scenario, spec 028 Docker run). One fresh thread gets one more try.
      if (!run.failed && skipsTools(run.reply, false, taskText(messages), names) && refuses(run.reply)) {
        st.n++
        st.used = false
        resumed = false
        prompt = full()
        chars += prompt.length
        const fresh = yield* ask(prompt, threadPath(S, id, st.n), allowed)
        if (!fresh.failed && fresh.reply !== null && typeof fresh.reply !== 'string' && (fresh.reply.tools.length > 0 || fresh.reply.say)) run = fresh
      }
    } else if (!run.failed && !S.chatOnly && stopsEarly(run.reply)) {
      // One push to go on; a second early stop stands as luna's answer.
      prompt = more(adapter.pushes.unfinished)
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(S, id, st.n), allowed)
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
    } else if (!run.failed && !S.chatOnly && ungroundedValues(run.reply, messages, taskText(messages)).length > 0) {
      // One push naming the pairs (built here, since it needs the list); a second ungrounded report stands as the answer.
      prompt = more(ungroundedPush(ungroundedValues(run.reply, messages, taskText(messages))))
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(S, id, st.n), allowed)
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
    } else if (!run.failed && !S.chatOnly && admitsGap(run.reply, messages, taskText(messages))) {
      // One push; a second admitting reply stands as the answer. The chain is else-if: at most one push per step.
      prompt = more(GAP_PUSH)
      chars += prompt.length
      const again = yield* ask(prompt, threadPath(S, id, st.n), allowed)
      if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
    }
    // D76 condition 3: a free model's file-writing call outside the recorded write directories never reaches the host.
    // The model reads the refusal and gets one more try; a second violation is dropped and the step reports the refusal.
    if (!run.failed && adapter.auth === 'key-store') {
      const dirs = S.dirs.get(id) ?? S.writeDirs
      const bad = outsideWrites(run.reply, S.cwd, dirs)
      if (bad.length > 0) {
        prompt = more(`${writeRefusal(bad, dirs)} Reply with exactly one JSON object.\n`)
        chars += prompt.length
        const again = yield* ask(prompt, threadPath(S, id, st.n), allowed)
        if (!again.failed && again.reply !== null && typeof again.reply !== 'string' && (again.reply.tools.length > 0 || again.reply.say)) run = again
        const still = outsideWrites(run.reply, S.cwd, dirs)
        if (still.length > 0 && run.reply !== null && typeof run.reply !== 'string') {
          const kept = run.reply.tools.filter(t => outsideWrites({ say: '', tools: [t] }, S.cwd, dirs).length === 0)
          run = { ...run, reply: { say: kept.length > 0 ? run.reply.say : writeRefusal(still, dirs), tools: kept } }
        }
      }
    }
    // An aborted step is not marked used: the thread may be half-written, so the next step starts it over.
    const wasAborted = next.signal.aborted
    if (!run.failed && !wasAborted) st.used = true
    const reply = run.reply
    if (typeof reply !== 'string' && reply !== null) st.sent = messages.length
    const ms = (await $.clock.now()) - t0
    $.ui.log(`${S.log} step ${e.index} of ${id} took ${ms} ms, prompt ${chars} chars, ${resumed ? 'resumed' : 'fresh'} thread, system ${system.length} catalog ${catalog(offeredTools, types, hand).length} conversation ${render(sentMessages).length} chars, ${names.length} tools, handback ${hand ? 'on' : 'off'}, messages ${messages.length} sent ${sentBefore}, codex_tools ${acc.tools.length ? acc.tools.join(' ') : 'none'}, usage ${acc.usage ? `in ${acc.usage.input_tokens} cached ${acc.usage.cached_input_tokens} out ${acc.usage.output_tokens}` : 'none'}`, { to: 'debug' })
    const tokens = acc.usage
    const failure = run.failed ? (run.fail ?? `${S.agent} failed: run failed`) : typeof reply === 'string' ? `${S.agent} failed: unparsable reply` : null
    const before = S.ran.get(id)?.usage ?? ZERO
    S.ran.set(id, {
      outcome: wasAborted ? 'aborted' : failure === null ? 'done' : failure.startsWith(S.quota) ? 'quota-paused' : 'failed',
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
          model: acc.slug ?? S.agent,
        }
      : null

    if (reply === null) return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: null, usage: turnUsage }

    const out: Reply = failure !== null ? handback({ say: failure, tools: [] }, hand) : handback(reply as Reply, hand)
    let index = 1 // block 0 is the live thinking line
    if (out.say) yield { kind: 'text', index: index++, text: out.say }
    for (const [n, tool] of out.tools.entries()) {
      yield { kind: 'tool', index, id: `${S.agent}_${e.turnId}_${e.index}_${n}`, name: tool.name }
      yield { kind: 'input', index, json: JSON.stringify(tool.input) }
      index++
    }
    const stopReason = out.tools.length > 0 ? 'tool_use' : 'end_turn'
    yield { kind: 'stop', stopReason, usage: turnUsage }
    return { turnId: e.turnId, index: e.index, answer: out.say, toolUses: out.tools, stopReason, usage: turnUsage }
  })
}

