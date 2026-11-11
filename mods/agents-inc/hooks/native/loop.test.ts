// Spec 038 T015 / T021a: the shared step loop against a fake adapter, with no engine and no Codex.
// The hooks are captured from registerLoop through a stand-in `on` and driven with a stand-in `$`.
import { expect, test } from 'claude-code/testing'
import type { Adapter } from './adapter'
import { admitsGap, buildPrompt, catalog, guestTools, outsideWrites, ranTool, registerAgent, registerLoop, registerLoops, skipsTools, stopsEarly, ungroundedValues } from './loop'

type Run = { out?: string; code?: number; hang?: boolean }
type Chunk = { kind: string; [k: string]: unknown }

const fakeAdapter = (over: Partial<Adapter> = {}): Adapter => ({
  provider: 'gemini',
  kind: 'thread',
  auth: 'cli-login',
  nickname: 'fake',
  cli: ['agents-inc', 'fake'],
  description: slug => `fake agent (${slug})`,
  toolHome: 'TOOL-HOME. ',
  identity: slug => `You are fake (${slug}).\n`,
  ownTools: 'OWN-TOOLS. ',
  deltaRule: 'DELTA-RULE. ',
  pushes: { refusal: 'PUSH-REFUSAL\n', unfinished: 'PUSH-UNFINISHED\n', asked: 'PUSH-ASKED\n' },
  timeoutEnv: 'AGENTS_INC_FAKE_STEP_TIMEOUT_S',
  timeoutText: s => `fake failed: timeout after ${s} s`,
  argv: (_m, o) => ['fake-run', '--thread', o.thread, ...(o.timeoutS !== null ? ['--timeout', String(o.timeoutS)] : [])],
  rejectsTimeout: () => false,
  classify: () => null,
  ...over,
})

function harness(adapter: Adapter, o: { replies?: Run[]; task?: string; agents?: 'throw' | unknown[]; timeout?: boolean; also?: Adapter[]; writeDirs?: string[]; beginDirs?: string[]; tools?: boolean; messages?: unknown[] } = {}) {
  const hooks: Record<string, (...a: unknown[]) => unknown> = {}
  const on = (event: string, a: unknown, b?: unknown) => {
    hooks[event] = (b ?? a) as (...a: unknown[]) => unknown
    return { catch: () => undefined }
  }
  const runs: { argv: string[]; input?: string }[] = []
  const verbs: string[][] = []
  const registered: unknown[] = []
  const logs: string[] = []
  const replies = [...(o.replies ?? [])]
  const $ = {
    agent: {
      list: async () => { if (o.agents === 'throw') throw new Error('list down'); return o.agents ?? [] },
      register: async (a: unknown) => { registered.push(a) },
    },
    session: {
      messages: async () => [{ role: 'user', content: [{ type: 'text', text: o.task ?? 'Count the lines.' }] }, ...(o.messages ?? [])],
      id: async () => 's1',
    },
    // Heartbeats never fire; the step limit fires at once when the test asks for a timeout.
    clock: { now: async () => 0, sleep: (ms: number) => (o.timeout && ms >= 60_000 ? Promise.resolve() : new Promise<never>(() => {})) },
    env: { get: async () => undefined },
    tool: { list: async () => [{ name: 'Bash', description: 'Runs a command.' }, { name: 'Write', description: 'Writes a file.' }, { name: 'Edit', description: 'Edits a file.' }, { name: 'SubagentHandback', description: 'Hand back.' }] },
    prompt: { compose: async () => ({ sections: [{ text: 'System.' }] }) },
    fs: { read: async () => '', write: async () => undefined },
    plugin: { root: '/p' },
    ui: { log: (m: string) => { logs.push(m) } },
    process: {
      spawn: (a: { argv: string[]; input?: string }) => (async function* () {
        if (a.argv[0] === 'agents-inc') {
          verbs.push(a.argv)
          const out = a.argv[2] === 'status' ? JSON.stringify({ offered: true, slug: 'fake-1', write_dirs: o.writeDirs, tools: o.tools }) : a.argv[2] === 'begin' ? JSON.stringify({ snapshot: 'captured', write_dirs: o.beginDirs }) : JSON.stringify({ snapshot: 'unchanged', changed: [] })
          yield { stream: 'stdout' as const, text: out }
          return { code: 0 }
        }
        runs.push(a)
        const r = replies.shift() ?? { out: '' }
        if (r.hang) await new Promise<never>(() => {})
        if (r.out) yield { stream: 'stdout' as const, text: r.out }
        return { code: r.code ?? 0 }
      })(),
    },
  }
  if (o.also) registerLoops(on as never, [adapter, ...o.also])
  else registerLoop(on as never, adapter)
  let placeholder = 0
  const step = async (agentId: string, signal = new AbortController().signal) => {
    const next = Object.assign(function* () {
      placeholder++
      yield { kind: 'text', index: 0, text: 'placeholder' }
      return { answer: 'placeholder', toolUses: [], stopReason: 'end_turn', usage: null }
    }, { signal })
    const gen = hooks['turn.step']($, { agentId, turnId: 't1', index: 0 }, next) as AsyncGenerator<Chunk, Record<string, unknown>>
    const chunks: Chunk[] = []
    for (;;) {
      const n = await gen.next()
      if (n.done) return { chunks, result: n.value }
      chunks.push(n.value)
    }
  }
  const spawn = async (agentId: string, nick = adapter.nickname) => {
    await hooks['agent.spawn']($, { subagentType: `agents-inc:${nick}`, prompt: o.task ?? 'Count the lines.' }, async () => ({ agentId }))
  }
  return { $, hooks, runs, verbs, registered, logs, step, spawn, placeholderCalls: () => placeholder }
}

const BASH = JSON.stringify({ say: '', tools: [{ name: 'Bash', input: { command: 'wc -l a.txt' } }] })
const message = (r: Record<string, unknown>) => String(((r.toolUses as { input: { message?: string } }[])[0]?.input)?.message ?? r.answer)

test('the prompt carries the adapter fragments and the run uses the adapter argv', async () => {
  const a = fakeAdapter()
  const h = harness(a, { replies: [{ out: BASH }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('a1')
  const { result } = await h.step('a1')
  expect(h.registered).toMatchObject([{ name: 'fake', description: 'fake agent (fake-1)', model: 'haiku' }])
  expect(h.runs[0].argv).toEqual(['fake-run', '--thread', '/w/.scratch/agents-inc-fake/s1/a1.thread', '--timeout', '60'])
  expect(h.runs[0].input).toContain('TOOL-HOME. Example')
  expect(h.runs[0].input).toContain('You are fake (fake-1).\nOWN-TOOLS. Your reply')
  expect(result.toolUses).toEqual([{ name: 'Bash', input: { command: 'wc -l a.txt' } }])
})

test('an unparsable reply gets one correction, and a second one ends the step', async () => {
  const a = fakeAdapter()
  const ok = harness(a, { replies: [{ out: 'prose' }, { out: BASH }] })
  await registerAgent(ok.$ as never, a, { cwd: '/w' })
  await ok.spawn('c1')
  const fixed = await ok.step('c1')
  expect(ok.runs.length).toBe(2)
  expect(ok.runs[1].input).toContain('Your previous reply was rejected: no JSON object in the reply')
  expect(fixed.result.toolUses).toEqual([{ name: 'Bash', input: { command: 'wc -l a.txt' } }])

  const b = fakeAdapter()
  const bad = harness(b, { replies: [{ out: 'prose' }, { out: 'still prose' }, { out: BASH }] })
  await registerAgent(bad.$ as never, b, { cwd: '/w' })
  await bad.spawn('c2')
  const { result } = await bad.step('c2')
  expect(bad.runs.length).toBe(2)
  expect(message(result)).toBe('fake failed: unparsable reply')
})

test('a reply that skips the tool the task names gets the adapter push once', async () => {
  const a = fakeAdapter()
  const guess = JSON.stringify({ say: 'A=0', tools: [] })
  const h = harness(a, { replies: [{ out: guess }, { out: guess }, { out: BASH }], task: 'Run wc -l a.txt with Bash; report A=<n>.' })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('p1')
  const { result } = await h.step('p1')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].input).toBe('PUSH-REFUSAL\n')
  expect(message(result)).toBe('A=0')
})

test('an agent that cannot be identified fails closed: no run, no placeholder model', async () => {
  const a = fakeAdapter()
  const h = harness(a, { agents: 'throw' })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  const { chunks, result } = await h.step('unknown-1')
  expect(h.runs.length).toBe(0)
  expect(h.placeholderCalls()).toBe(0)
  expect(String(chunks[0].text)).toContain('agents-inc fake: cannot identify agent unknown-1; step not sent to the placeholder model')
  expect(result.answer).not.toBe('placeholder')
})

test('an aborted step returns no answer and the next step starts the thread over', async () => {
  const a = fakeAdapter()
  const h = harness(a, { replies: [{ hang: true }, { out: BASH }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('ab1')
  const ctl = new AbortController()
  const pending = h.step('ab1', ctl.signal)
  for (let i = 0; i < 20; i++) await Promise.resolve()
  ctl.abort()
  const { result } = await pending
  expect(result).toMatchObject({ answer: '', toolUses: [], stopReason: null })
  expect(h.runs.length).toBe(1)
  expect(h.placeholderCalls()).toBe(0)
  await h.step('ab1')
  expect(h.runs[1].input).toContain('System prompt:') // not resumed: the aborted step did not mark the thread used
})

test('a run that never answers times out, retries once fresh, then names the adapter timeout', async () => {
  const a = fakeAdapter()
  const h = harness(a, { replies: [{ hang: true }, { hang: true }], timeout: true })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('t1')
  const { result } = await h.step('t1')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].argv[2]).toMatch(/t1-2\.thread$/)
  expect(message(result)).toBe('fake failed: timeout after 60 s (after one retry on a fresh thread)')
  expect(h.placeholderCalls()).toBe(0)
})

test('failed runs never reach the placeholder model; an unclassified exit reads run exited', async () => {
  const a = fakeAdapter()
  const h = harness(a, { replies: [{ code: 1 }, { code: 1 }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('f1')
  const { result } = await h.step('f1')
  expect(h.runs.length).toBe(2)
  expect(h.placeholderCalls()).toBe(0)
  expect(message(result)).toContain('fake failed: run exited 1:')
})

test('an unknown auth value fails closed: no status call, no registration, no run', async () => {
  const a = fakeAdapter({ auth: 'api-key' as never })
  const h = harness(a, { replies: [{ out: BASH }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  expect(h.verbs.length).toBe(0)
  expect(h.registered).toEqual([])
  expect(h.logs.some(l => l.includes('not registered: unknown auth "api-key"'))).toBe(true)
  await h.step('x1')
  expect(h.runs.length).toBe(0)
})

test('key-store is a known auth value', async () => {
  const a = fakeAdapter({ auth: 'key-store' })
  const h = harness(a)
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  expect(h.registered.length).toBe(1)
})

test('a hand-back before a tool the task names ran is pushed; Skill calls do not count as that tool', () => {
  const hb = { say: '', tools: [{ name: 'SubagentHandback', input: { message: 'A=100 B=75 L=line 50' } }] }
  const task = 'Run wc -l a.txt with Bash, then Read b.txt'
  const names = ['Bash', 'Read', 'Skill', 'SubagentHandback']
  const skill = [
    { role: 'assistant', content: [{ type: 'tool_use', id: 't1', name: 'Skill', input: { skill: 'caveman' } }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't1', content: 'ok' }] },
  ]
  const bash = [
    { role: 'assistant', content: [{ type: 'tool_use', id: 't2', name: 'Bash', input: { command: 'wc -l a.txt' } }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't2', content: '173 a.txt' }] },
  ]
  expect(ranTool([], task, names)).toBe(false)
  expect(ranTool(skill, task, names)).toBe(false)
  expect(ranTool(bash, task, names)).toBe(true)
  expect(ranTool(skill, 'Write one Latin sentence.', names)).toBe(true) // no tool named: any result counts
  expect(skipsTools(hb, ranTool(skill, task, names), task, names)).toBe(true)
  expect(skipsTools(hb, ranTool(bash, task, names), task, names)).toBe(false)
  expect(skipsTools(hb, false, 'Summarise the plan.', names)).toBe(false) // no tool named: the answer stands
})

test('a stateless adapter resends the whole conversation with its previous reply on a push', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const guess = JSON.stringify({ say: 'A=0', tools: [] })
  const h = harness(a, { replies: [{ out: guess }, { out: BASH }, { out: BASH }], task: 'Run wc -l a.txt with Bash; report A=<n>.' })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('s1')
  await h.step('s1')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].input).toContain('System prompt:')
  expect(h.runs[1].input).toContain(`Your previous reply:\n${guess}\nPUSH-REFUSAL`)
  await h.step('s1')
  expect(h.runs[2].input).toContain('System prompt:') // a later step is never a delta
  expect(h.runs[2].input).not.toContain('DELTA-RULE')
})

test('one set of hooks serves several adapters: each agent runs on its own adapter, other types pass through', async () => {
  const a = fakeAdapter()
  const b = fakeAdapter({ nickname: 'other', argv: () => ['other-run'] })
  const h = harness(a, { replies: [{ out: BASH }, { out: BASH }, { out: BASH }], also: [b], agents: [{ id: 'b2', type: 'agents-inc:other' }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await registerAgent(h.$ as never, b, { cwd: '/w' })
  await h.spawn('a1')
  await h.spawn('b1', 'other')
  await h.step('a1')
  await h.step('b1')
  await h.step('b2') // known only from the agent list
  expect(h.runs.map(r => r.argv[0])).toEqual(['fake-run', 'other-run', 'other-run'])
  await h.step('claude-1')
  expect(h.placeholderCalls()).toBe(1)
  const offer = h.hooks['agent.offer'] as (...x: unknown[]) => unknown
  expect(offer(h.$, { agent: 'general-purpose' }, () => 'next')).toBe('next')
  expect(offer(h.$, { agent: 'agents-inc:other' }, () => 'next')).toBe('next')
})

const WRITE = (path: string, tool = 'Write') => JSON.stringify({ say: '', tools: [{ name: tool, input: tool === 'NotebookEdit' ? { notebook_path: path } : { file_path: path, content: 'x' } }] })
const nameOf = (r: Record<string, unknown>) => (r.toolUses as { name: string }[])[0].name

test('a key-store agent: a write inside the recorded directories passes to the host', async () => {
  const a = fakeAdapter({ auth: 'key-store' })
  const h = harness(a, { replies: [{ out: WRITE('/w/.scratch/out.txt') }], writeDirs: ['/w/.scratch'] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('w1')
  const { result } = await h.step('w1')
  expect(h.runs.length).toBe(1)
  expect(result.toolUses).toEqual([{ name: 'Write', input: { file_path: '/w/.scratch/out.txt', content: 'x' } }])
})

test('a key-store agent: a write outside is refused, the model reads the refusal, a second violation is dropped', async () => {
  const a = fakeAdapter({ auth: 'key-store' })
  const h = harness(a, { replies: [{ out: WRITE('/elsewhere/passwd') }, { out: WRITE('.scratch/../src/x.py', 'Edit') }], writeDirs: ['/w/.scratch'] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('w2')
  const { result } = await h.step('w2')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].input).toContain('Tool refused: Write /elsewhere/passwd is outside the directories this agent may write in (/w/.scratch)')
  expect(nameOf(result)).toBe('SubagentHandback')
  expect(message(result)).toContain('Tool refused: Edit .scratch/../src/x.py')
})

test('a key-store agent: the begin directories replace the status directories (authorization after session start)', async () => {
  const a = fakeAdapter({ auth: 'key-store' })
  const h = harness(a, { replies: [{ out: WRITE('/w/src/a.py') }], writeDirs: [], beginDirs: ['/w/src'] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('w3')
  const { result } = await h.step('w3')
  expect(h.runs.length).toBe(1)
  expect(nameOf(result)).toBe('Write')
})

test('a cli-login agent (luna) is not path-checked', async () => {
  const a = fakeAdapter({ auth: 'cli-login' })
  const h = harness(a, { replies: [{ out: WRITE('/elsewhere/passwd') }] })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('w4')
  const { result } = await h.step('w4')
  expect(h.runs.length).toBe(1)
  expect(nameOf(result)).toBe('Write')
})

test('outsideWrites resolves relative paths against the cwd and treats a missing path as outside', () => {
  const r = (t: unknown) => ({ say: '', tools: [t as never] })
  expect(outsideWrites(r({ name: 'Write', input: { file_path: 'a.txt' } }), '/w/.scratch', ['/w/.scratch'])).toEqual([])
  expect(outsideWrites(r({ name: 'Write', input: { file_path: '/w/.scratch2/a' } }), '/w', ['/w/.scratch']).length).toBe(1)
  expect(outsideWrites(r({ name: 'Write', input: {} }), '/w', ['/w']).length).toBe(1)
  expect(outsideWrites(r({ name: 'Bash', input: { command: 'rm -rf x' } }), '/w', [])).toEqual([])
})

test('a chat-only model (status tools false) is registered as chat only, gets no tool catalog and is never pushed to use tools', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const guess = JSON.stringify({ say: 'A=0', tools: [] })
  const h = harness(a, { replies: [{ out: guess }, { out: BASH }], tools: false, task: 'Run wc -l a.txt with Bash; report A=<n>.' })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  expect(h.registered).toMatchObject([{ description: expect.stringContaining('Chat only, no tools') }])
  await h.spawn('c1')
  const { result } = await h.step('c1')
  expect(h.runs.length).toBe(1) // no refusal push
  expect(h.runs[0].input).toContain('You have no tools')
  expect(h.runs[0].input).not.toContain('- Bash:')
  expect(h.runs[0].input).toContain('- SubagentHandback:') // the hand-back tool still ends the turn
  expect(message(result)).toBe('A=0')
})

test('a chat-only model that names a tool is corrected, since the catalog is empty', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const h = harness(a, { replies: [{ out: BASH }, { out: JSON.stringify({ say: 'done', tools: [] }) }], tools: false })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('c2')
  const { result } = await h.step('c2')
  expect(h.runs[1].input).toContain('unknown tool "Bash"')
  expect(message(result)).toBe('done')
})

test('a model with tools true or no tools field keeps the normal prompt and description', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const h = harness(a, { replies: [{ out: BASH }], tools: true })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  expect(String((h.registered[0] as { description: string }).description)).not.toContain('Chat only')
  await h.spawn('c3')
  await h.step('c3')
  expect(h.runs[0].input).toContain('- Bash:')
})

const FIVE = 'Run five wc -l commands, each its own Bash call. Report A=<n> B=<n> C=<n> D=<n> E=<n>.'
const ran = (...counts: [string, string][]) => counts.flatMap(([cmd, out], i) => [
  { role: 'assistant', content: [{ type: 'tool_use', id: `t${i}`, name: 'Bash', input: { command: cmd } }] },
  { role: 'user', content: [{ type: 'tool_result', tool_use_id: `t${i}`, content: out }] },
])
const FOUR = ran(['wc -l a.txt', '173 a.txt'], ['wc -l b.txt', '95 b.txt'], ['wc -l c.txt', '41 c.txt'], ['wc -l d.txt', '7 d.txt'])
const TWO = FOUR.slice(0, 4)
const hb = (m: string) => ({ say: '', tools: [{ name: 'SubagentHandback', input: { message: m } }] })
const asMsgs = (m: unknown[]) => m as never

test('ungroundedValues: a grounded report is clean; run 7 and run 10 reports name their invented values', () => {
  const task = [{ role: 'user', content: [{ type: 'text', text: FIVE }] }]
  expect(ungroundedValues(hb('A=173 B=95 C=41 D=7'), asMsgs(FOUR), FIVE)).toEqual([])
  expect(ungroundedValues(hb('A=173 B=95 C=41 D=7 E=2'), asMsgs(FOUR), FIVE)).toEqual(['E=2'])
  expect(ungroundedValues(hb('A=173 B=95 C=208 D=64 E=127'), asMsgs(TWO), FIVE)).toEqual(['C=208', 'D=64', 'E=127'])
  expect(ungroundedValues(hb('A: 999'), asMsgs(TWO), FIVE)).toEqual(['A=999'])
  expect(ungroundedValues(hb('A=173 B=95 C=208'), asMsgs(task), FIVE)).toEqual([]) // no tool result yet: skipsTools' business
  expect(ungroundedValues(hb('A=173 B=95 E=12'), asMsgs(TWO), `${FIVE} The expected E=12.`)).toEqual([]) // number in the task text
  expect(ungroundedValues({ say: 'x=5', tools: [{ name: 'Bash', input: {} }] }, asMsgs(TWO), FIVE)).toEqual([]) // not a hand-back
})

test('an ungrounded hand-back is pushed once, naming the pairs; a second ungrounded reply stands', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const bad = JSON.stringify({ say: '', tools: [{ name: 'SubagentHandback', input: { message: 'A=173 B=95 C=208' } }] })
  const h = harness(a, { replies: [{ out: bad }, { out: bad }], task: FIVE, messages: TWO })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('g1')
  const { result } = await h.step('g1')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].input).toContain('Your report gives C=208, but no tool result in this conversation contains that value')
  expect(message(result)).toBe('A=173 B=95 C=208')
  const good = harness(a, { replies: [{ out: bad }, { out: BASH }], task: FIVE, messages: TWO })
  await registerAgent(good.$ as never, a, { cwd: '/w' })
  await good.spawn('g2')
  expect(nameOf((await good.step('g2')).result)).toBe('Bash')
})

test('a grounded hand-back runs once with no push', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const ok = JSON.stringify({ say: '', tools: [{ name: 'SubagentHandback', input: { message: 'A=173 B=95' } }] })
  const h = harness(a, { replies: [{ out: ok }], task: FIVE, messages: TWO })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('g3')
  await h.step('g3')
  expect(h.runs.length).toBe(1)
})

test('stopsEarly catches run 9 and similar wording, not a finished report', () => {
  const say = (t: string) => ({ say: t, tools: [] })
  expect(stopsEarly(say('Ran each requested command in its own Bash call. Visible results: a.txt 173; b.txt 95; c.txt 41. Results for d.txt and e.txt have not been provided, so their counts are unavailable.'))).toBe(true)
  expect(stopsEarly(say('A=173. The counts are unavailable for the rest.'))).toBe(true)
  expect(stopsEarly(say('A=173 so far; the remaining results are not in.'))).toBe(true)
  expect(stopsEarly(say('d.txt has not yet run through wc.'))).toBe(true)
  expect(stopsEarly(say('Done. No errors were provided by the tool. A=173 B=95 C=41 D=7 E=12.'))).toBe(false)
  expect(stopsEarly(say('A=173 B=95 C=41 D=7 E=12'))).toBe(false)
})

// A real session lists 77 tools (MCP and deferred included); the first codestral step was 50032 chars against a 48000 cap.
test('a stateless guest agent is offered only the core tools, so step 0 of a real session fits', () => {
  const core = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'NotebookEdit', 'Agent', 'Skill', 'WebFetch', 'TodoWrite', 'ToolSearch']
  const all = Array.from({ length: 77 }, (_, i) => {
    const name = i < core.length ? core[i] : `mcp__server${i % 5}__tool_${i}`
    return { name, description: `Does thing ${i}. `.repeat(i < core.length ? 60 : 4) + 'x'.repeat(i < core.length ? 800 : 200), mcp: i >= core.length }
  })
  const offered = guestTools(all)
  expect(offered.map(t => t.name)).toEqual(['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'NotebookEdit'])
  expect(catalog(all, '').length).toBeGreaterThan(catalog(offered, '').length * 2)
  const system = 's'.repeat(7457)
  const turn = [{ role: 'user', content: [{ type: 'text', text: 'c'.repeat(14655) }] }]
  const a = fakeAdapter({ kind: 'stateless' })
  const prompt = buildPrompt(a, 'codestral-latest', system, catalog(offered, ''), turn as never)
  expect(prompt.length).toBeLessThan(48000)
})

const ADMIT = 'Verified result received: `wc -l a.txt` returned 173, so A=173. Results for b.txt through e.txt were not included in the messages available to me; their counts remain unverified.'
const ONE = ran(['wc -l a.txt', '173 a.txt'])

test('admitsGap: run 5 fixture fires; a fully grounded five-key report never does; no keys lets the cue decide', () => {
  expect(admitsGap(hb(ADMIT), asMsgs(ONE), FIVE)).toBe(true)
  expect(admitsGap(hb('A=173 B=95 C=41 D=7 E=2 (the sandbox note is unverified)'), asMsgs(ran(['a', '173 a'], ['b', '95 b'], ['c', '41 c'], ['d', '7 d'], ['e', '2 e'])), FIVE)).toBe(false)
  expect(admitsGap(hb('Counts are unavailable.'), asMsgs(ONE), 'Count the lines.')).toBe(true)
  expect(admitsGap(hb('The count is 173.'), asMsgs(ONE), 'Count the lines.')).toBe(false)
  expect(admitsGap({ say: ADMIT, tools: [{ name: 'Bash', input: {} }] }, asMsgs(ONE), FIVE)).toBe(false) // not a hand-back
})

test('an admitted gap is pushed once; a second admitting reply stands; chat-only is not pushed', async () => {
  const a = fakeAdapter({ kind: 'stateless' })
  const adm = JSON.stringify(hb(ADMIT))
  const h = harness(a, { replies: [{ out: adm }, { out: adm }], task: FIVE, messages: ONE })
  await registerAgent(h.$ as never, a, { cwd: '/w' })
  await h.spawn('g1')
  const { result } = await h.step('g1')
  expect(h.runs.length).toBe(2)
  expect(h.runs[1].input).toContain('You said some results are missing')
  expect(message(result)).toBe(ADMIT)
  const cont = harness(a, { replies: [{ out: adm }, { out: BASH }], task: FIVE, messages: ONE })
  await registerAgent(cont.$ as never, a, { cwd: '/w' })
  await cont.spawn('g2')
  expect(nameOf((await cont.step('g2')).result)).toBe('Bash')
  const chat = harness(a, { replies: [{ out: adm }], task: FIVE, messages: ONE, tools: false })
  await registerAgent(chat.$ as never, a, { cwd: '/w' })
  await chat.spawn('g3')
  await chat.step('g3')
  expect(chat.runs.length).toBe(1)
})
