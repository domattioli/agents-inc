import { expect, mock, test } from 'claude-code/testing'

const TOOL = 'mcp__agents-inc__run'
const RUN_DIR = '/work/.scratch/agents-inc-runs/20261024T000000Z-sonnet-aaaaaa'
const VERDICT = 'dispatch 20261024T000000Z-sonnet-aaaaaa sonnet green'

type On = Parameters<Parameters<typeof test>[1]>[1]
type Dollar = Parameters<Parameters<typeof test>[1]>[0]

async function start($: Dollar, on: On) {
  on('agent.register', (_$, e) => ({ value: { agent: `agents-inc:${e.name}` } }))
  on('tool.register', () => ({ value: {} }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
}

// Stands for the engine's process layer: dispatch announces its run dir, the follower prints one batch.
function fakeProcesses(on: On, seen: string[][]) {
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    if (e.argv.includes('dispatch')) {
      yield { stream: 'stderr', text: `agents-inc dispatch: run r1 dir ${RUN_DIR}\n` }
      yield { stream: 'stdout', text: `${VERDICT}\n` }
      return { value: { code: 0, signal: null } }
    }
    yield { stream: 'stdout', text: '[00:01] sonnet say: hello\n[00:02] sonnet tool: ls\n\n' }
    return { value: { code: 0, signal: null } }
  })
}

// The luna agent shares the plugin's one session.start (mod.ts), so it registers after the relay pair.
test('session.start registers the relay agent and the run tool', async ($, on) => {
  const registered: string[] = []
  on('agent.register', (_$, e) => {
    registered.push(`agent:${e.name}`)
    return { value: { agent: `agents-inc:${e.name}` } }
  })
  on('tool.register', (_$, e) => {
    registered.push(`tool:${e.name}`)
    return { value: {} }
  })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 's1' }))
  on('ui.log', () => ({ value: undefined }))
  on('process.spawn', async function* () {
    yield { stream: 'stdout' as const, text: JSON.stringify({ offered: true, slug: 'gpt-6-luna', reason: 'ready' }) }
    return { value: { code: 0, signal: null } }
  })
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  expect(registered).toEqual(['agent:relay', 'tool:run', 'agent:luna'])
})

test('a call outside the relay subagent is refused', async ($, on) => {
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/work/s.md' })
  expect(out.deny).toContain('agents-inc:relay')
})

test('an unknown model is refused', async ($, on) => {
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'gpt-9', slots: '/work/s.md', agentId: 'a1' })
  expect(out.deny).toBeDefined()
})

test('a free model is refused and names agent.sh', async ($, on) => {
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'gemini', slots: '/work/s.md', agentId: 'a1' })
  expect(out.deny).toContain('agent.sh')
})

test('a slots path outside the session cwd is refused', async ($, on) => {
  on('fs.stat', (_$, e) => ({ value: { kind: 'file', size: 0, mtimeMs: 0, isLink: false, realPath: e.path } }))
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/etc/passwd', agentId: 'a1' })
  expect(out.deny).toBeDefined()
})

test('happy path: rows reach the subagent and the verdict comes back', async ($, on) => {
  const seen: string[][] = []
  fakeProcesses(on, seen)
  on('fs.stat', (_$, e) => ({ value: { kind: 'file', size: 0, mtimeMs: 0, isLink: false, realPath: e.path } }))
  on('fs.read', () => ({ value: 'delegate answer' }))
  mock.clock(on)
  const session = mock.session(on)
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/work/s.md', agentId: 'a1' })
  expect(out.result).toBe(`delegate answer\n\n${VERDICT}`) // a string: the engine refuses an object
  expect(seen.some(a => a.includes('follow') && a.includes(RUN_DIR))).toBe(true)
  const notices = session.appended().map(r => JSON.stringify(r.message))
  expect(notices.some(n => n.includes('sonnet say: hello'))).toBe(true)
})

const STAT = (_$: unknown, e: { path: string }) => ({
  value: { kind: 'file', size: 0, mtimeMs: 0, isLink: false, realPath: e.path },
})

// Claude-rung rows, as `fixtures/live-events/claude.rows.txt` renders them.
test('Claude rung: rows with the haiku label reach the subagent in order', async ($, on) => {
  on('process.spawn', async function* (_$, e) {
    if (e.argv.includes('dispatch')) {
      yield { stream: 'stderr', text: `agents-inc dispatch: run r1 dir ${RUN_DIR}\n` }
      yield { stream: 'stdout', text: `${VERDICT.replace('sonnet', 'haiku')}\n` }
    } else {
      yield { stream: 'stdout', text: '[00:02] haiku think: Check the tree first.\n[00:04] haiku tool: git status --short\n\n' }
      yield { stream: 'stdout', text: '[00:06] haiku file: agents_inc/install/dispatch.py\n\n' }
    }
    return { value: { code: 0, signal: null } }
  })
  on('fs.stat', STAT)
  on('fs.read', () => ({ value: 'report' }))
  mock.clock(on)
  const session = mock.session(on)
  await start($, on)
  await $.tool.call({ tool: TOOL, model: 'haiku', slots: '/work/s.md', agentId: 'a1' })
  const notices = session.appended().map(r => JSON.stringify(r.message))
  expect(notices.length).toBe(2)
  expect(notices[0]).toContain('haiku think')
  expect(notices[1]).toContain('haiku file')
})

test('no run-dir line: a notice says the live view is unavailable', async ($, on) => {
  on('process.spawn', async function* () {
    yield { stream: 'stdout', text: 'dispatch r1 sonnet red\n' }
    return { value: { code: 1, signal: null } }
  })
  on('process.run', () => ({ value: { exitCode: 0, stdout: '', stderr: '' } }))
  on('fs.stat', STAT)
  mock.clock(on)
  const session = mock.session(on)
  await start($, on)
  await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/work/s.md', agentId: 'a1' })
  const notices = session.appended().map(r => JSON.stringify(r.message))
  expect(notices.some(n => n.includes('live view unavailable'))).toBe(true)
})

test('cap: 600 notices per call, the rest are held back', async ($, on) => {
  on('process.spawn', async function* (_$, e) {
    if (e.argv.includes('dispatch')) {
      yield { stream: 'stderr', text: `agents-inc dispatch: run r1 dir ${RUN_DIR}\n` }
      yield { stream: 'stdout', text: `${VERDICT}\n` }
    } else {
      for (let i = 0; i < 650; i++) yield { stream: 'stdout', text: `[00:01] sonnet say: row ${i}\n\n` }
    }
    return { value: { code: 0, signal: null } }
  })
  on('fs.stat', STAT)
  on('fs.read', () => ({ value: 'report' }))
  mock.clock(on)
  const session = mock.session(on)
  await start($, on)
  await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/work/s.md', agentId: 'a1' })
  expect(session.appended().length).toBe(600)
})

test('secrets: a planted key reaches no notice and no result unless redact let it through', async ($, on) => {
  const SECRET = 'sk-testABCDEFGHIJKLMNOPQRST'
  on('process.spawn', async function* () {
    yield { stream: 'stderr', text: `boom ${SECRET}\n` }
    return { value: { code: 1, signal: null } }
  })
  on('process.run', () => ({ value: { exitCode: 0, stdout: 'boom [redacted]\n', stderr: '' } }))
  on('fs.stat', STAT)
  mock.clock(on)
  const session = mock.session(on)
  await start($, on)
  const out = await $.tool.call({ tool: TOOL, model: 'sonnet', slots: '/work/s.md', agentId: 'a1' })
  expect(JSON.stringify(out)).not.toContain(SECRET)
  expect(JSON.stringify(session.appended())).not.toContain(SECRET)
})
