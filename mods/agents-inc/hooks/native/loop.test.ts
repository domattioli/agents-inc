// Spec 038 T015 / T021a: the shared step loop against a fake adapter, with no engine and no Codex.
// The hooks are captured from registerLoop through a stand-in `on` and driven with a stand-in `$`.
import { expect, test } from 'claude-code/testing'
import type { Adapter } from './adapter'
import { ranTool, registerAgent, registerLoop, skipsTools } from './loop'

type Run = { out?: string; code?: number; hang?: boolean }
type Chunk = { kind: string; [k: string]: unknown }

const fakeAdapter = (over: Partial<Adapter> = {}): Adapter => ({
  provider: 'gemini',
  kind: 'stateless',
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

function harness(adapter: Adapter, o: { replies?: Run[]; task?: string; agents?: 'throw'; timeout?: boolean } = {}) {
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
      list: async () => { if (o.agents === 'throw') throw new Error('list down'); return [] },
      register: async (a: unknown) => { registered.push(a) },
    },
    session: {
      messages: async () => [{ role: 'user', content: [{ type: 'text', text: o.task ?? 'Count the lines.' }] }],
      id: async () => 's1',
    },
    // Heartbeats never fire; the step limit fires at once when the test asks for a timeout.
    clock: { now: async () => 0, sleep: (ms: number) => (o.timeout && ms >= 60_000 ? Promise.resolve() : new Promise<never>(() => {})) },
    env: { get: async () => undefined },
    tool: { list: async () => [{ name: 'Bash', description: 'Runs a command.' }, { name: 'SubagentHandback', description: 'Hand back.' }] },
    prompt: { compose: async () => ({ sections: [{ text: 'System.' }] }) },
    fs: { read: async () => '', write: async () => undefined },
    plugin: { root: '/p' },
    ui: { log: (m: string) => { logs.push(m) } },
    process: {
      spawn: (a: { argv: string[]; input?: string }) => (async function* () {
        if (a.argv[0] === 'agents-inc') {
          verbs.push(a.argv)
          const out = a.argv[2] === 'status' ? JSON.stringify({ offered: true, slug: 'fake-1' }) : JSON.stringify({ snapshot: 'unchanged', changed: [] })
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
  registerLoop(on as never, adapter)
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
  const spawn = async (agentId: string) => {
    await hooks['agent.spawn']($, { subagentType: `agents-inc:${adapter.nickname}`, prompt: o.task ?? 'Count the lines.' }, async () => ({ agentId }))
  }
  return { $, runs, verbs, registered, logs, step, spawn, placeholderCalls: () => placeholder }
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
