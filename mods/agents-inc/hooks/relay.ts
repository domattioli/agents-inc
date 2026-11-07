import type { Register } from 'claude-code'

const TOOL = 'mcp__agents-inc__run'
const MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'astra', 'sol', 'terra', 'luna']
const FREE = ['gemini', 'mistral', 'openrouter']
const MAX_NOTICES = 600 // notices per call before the throttle (FR-018)
const THROTTLE_MS = 60_000
const DRAIN_MS = 3_000
const RUN_DIR_LINE = /^agents-inc dispatch: run \S+ dir (.+)$/
const VERDICT_LINE = /^dispatch \S+ \S+ \S+/

const RELAY_PROMPT =
  'Call the mcp__agents-inc__run tool once with the model and slots path you were given. ' +
  'Then answer with the tool text exactly, and add nothing.'

let sessionCwd = ''

const isInside = (real: string | undefined, root: string | undefined): boolean =>
  real !== undefined && root !== undefined && (real === root || real.startsWith(root.replace(/\/$/, '') + '/'))

// Called from mod.ts: a plugin's hooks.json names one module, and a module may register session.start once.
export async function registerRelay(
  $: {
    agent: { register: (a: Record<string, unknown>) => Promise<unknown> }
    tool: { register: (t: Record<string, unknown>) => Promise<unknown> }
  },
  e: { cwd: string },
): Promise<void> {
  sessionCwd = e.cwd
  await $.agent.register({
    name: 'relay',
    description: 'Runs one agents-inc delegate and relays its live rows. Use only for agents-inc dispatch.',
    prompt: RELAY_PROMPT,
    tools: [TOOL],
    model: 'haiku',
    maxTurns: 3,
  })
  await $.tool.register({
    name: 'run',
    description: 'Run one agents-inc dispatch and stream its rows into the subagent transcript.',
    inputSchema: {
      type: 'object',
      properties: { model: { type: 'string' }, slots: { type: 'string' }, effort: { type: 'string' } },
      required: ['model', 'slots'],
    },
    isDeferred: false,
  })
}

export const register: Register = on => {

  on('tool.call', { tool: TOOL }, async ($, e, next) => {
    const agentId = e.agentId as string | undefined
    const model = String(e.model ?? '')
    const slots = String(e.slots ?? '')
    const effort = e.effort === undefined ? undefined : String(e.effort)

    if (!agentId) return { deny: 'call through Agent subagent_type agents-inc:relay' }
    if (FREE.includes(model)) return { deny: `${model} is a free model: dispatch it with agent.sh, not the relay` }
    if (!MODELS.includes(model)) return { deny: `unknown model ${model}; use one of ${MODELS.join(' ')}` }
    const slotsReal = (await $.fs.stat(slots, { resolve: true }).catch(() => undefined))?.realPath
    const rootReal = (await $.fs.stat(sessionCwd, { resolve: true }).catch(() => undefined))?.realPath
    if (!isInside(slotsReal, rootReal)) return { deny: `slots must be a file inside ${sessionCwd}` }

    const argv = ['agents-inc', 'dispatch', '--model', model, '--slots', slots, '--cwd', sessionCwd]
    if (effort) argv.push('--effort', effort)

    let runDir: string | undefined
    let aborted = false
    let dispatchDone = false
    let followerP: Promise<void> | undefined
    let sent = 0
    let held = 0
    let lastNotice = 0
    const stderr: string[] = []
    let stdout = ''

    const notice = async (text: string) =>
      $.session
        .append({ message: { type: 'system', content: [{ type: 'text', text }] }, agentId })
        .catch(() => undefined)

    const relayBatch = async (batch: string) => {
      if (sent >= MAX_NOTICES) {
        held++
        const now = await $.clock.now()
        if (now - lastNotice >= THROTTLE_MS) {
          lastNotice = now
          await notice(`${held} rows held back; full log at ${runDir}/events.jsonl`)
        }
        return
      }
      sent++
      await notice(batch)
    }

    const follow = async (dir: string) => {
      let buf = ''
      for await (const piece of $.process.spawn({ argv: ['agents-inc', 'events', 'follow', dir] })) {
        if (aborted) break
        if (piece.stream !== 'stdout') continue
        buf += piece.text
        let at: number
        while ((at = buf.indexOf('\n\n')) >= 0) {
          const batch = buf.slice(0, at).trim()
          buf = buf.slice(at + 2)
          if (batch) await relayBatch(batch)
        }
      }
      if (buf.trim()) await relayBatch(buf.trim())
    }

    const onAbort = () => {
      aborted = true
      if (runDir) {
        $.process.run(['agents-inc', 'dispatch', '--cancel', runDir]).catch(() => undefined)
      }
    }
    next.signal.addEventListener('abort', onAbort)

    try {
      for await (const piece of $.process.spawn({ argv, cwd: sessionCwd })) {
        if (aborted) break
        if (piece.stream === 'stdout') {
          stdout += piece.text
          continue
        }
        for (const line of piece.text.split('\n')) {
          if (!line) continue
          stderr.push(line)
          const m = !runDir ? RUN_DIR_LINE.exec(line) : null
          if (m) {
            runDir = m[1]
            followerP = follow(runDir).catch(() => undefined)
          }
        }
      }
      dispatchDone = true
    } finally {
      next.signal.removeEventListener('abort', onAbort)
    }

    if (!runDir && !aborted) await notice('live view unavailable: dispatch did not announce its run dir')
    if (followerP) await Promise.race([followerP, $.clock.sleep(DRAIN_MS)])
    aborted = aborted || dispatchDone // stops the follower loop at its next piece

    const verdict = stdout.split('\n').find(l => VERDICT_LINE.test(l))
    let text: string
    if (verdict && runDir) {
      const body = await $.fs.read(`${runDir}/stdout.md`).catch(() => '')
      text = `${typeof body === 'string' ? body : ''}\n\n${verdict}`.trim()
    } else {
      const tail = stderr.slice(-20).join('\n')
      const redacted = await $.process.run(['agents-inc', 'events', 'redact'], { stdin: `${stdout}\n${tail}` })
        .then(r => r.stdout)
        .catch(() => '[output withheld: redaction failed]')
      text = `dispatch ended without a verdict\n${redacted}`
    }
    return { result: text } // the tool's output shape is a string (T043: an object was refused)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'agents-inc relay: its guard failed.' }))
}
