import { expect, mock, test } from 'claude-code/testing'

const RUN = '20991107T000000Z-luna-aaaaaa'
const PANE = {
  plugin: 'agents-manager',
  component: 'Pane',
  requestId: 'agents-manager',
  props: {
    title: 'agents-inc manager',
    isFocused: true,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

type On = Parameters<Parameters<typeof test>[1]>[1]
type Dollar = Parameters<Parameters<typeof test>[1]>[0]

const DONE = '{"event":{"type":"run.end","outcome":"green","rc":0}}\n'
const LIVE = '{"event":{"type":"assistant","message":{"content":[]}}}\n'

// What the engine lists. Tests change it between polls: agents, run dirs, and file contents by path.
type World = { agents: any[]; dirs: string[]; read: (path: string) => string; advance: (ms: number) => Promise<unknown> }

// Stands for the engine: one live subagent, one finished dispatch run. Row 1 = agent a1, row 2 = the run.
async function start($: Dollar, on: On): Promise<World> {
  const clock = mock.clock(on)
  const world: World = {
    agents: [{ id: 'a1', name: 'scout', type: 'Explore', description: 'scout', status: 'running' }],
    dirs: [RUN],
    read: () => DONE,
    advance: ms => clock.advance(ms),
  }
  on('command.register', () => ({ value: { command: 'agents-manager' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('agent.list', () => ({ value: world.agents as any }))
  on('fs.list', () => ({ value: world.dirs.map(name => ({ name, kind: 'dir' })) as any }))
  on('fs.read', (_$, e: any) => ({ value: world.read(String(e.path)) as any }))
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  await clock.advance(2100)
  return world
}

test('the poll lists the agent and the run as numbered rows', async ($, on) => {
  await start($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Button', text: /scout/ }))?.text).toContain('scout')
    expect((await ui.find({ type: 'Button', text: /luna-aaaaaa/ }))?.text).toContain('dispatch')
    await ui.unmount()
  }
})

test('a message to a run row resumes that run through dispatch', async ($, on) => {
  const seen: string[][] = []
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    yield { stream: 'stdout', text: 'ok\n' }
    return { value: { code: 0, signal: null } }
  })
  await start($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    seen.length = 0
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.select({ key: 'target', value: `run:${RUN}` })
    await ui.input({ key: 'msg', text: 'keep going' })
    const argv = seen.find(a => a.includes('dispatch')) ?? []
    expect(argv[argv.indexOf('--resume') + 1]).toBe(`/work/.scratch/agents-inc-runs/${RUN}`)
    expect(argv[argv.indexOf('--message') + 1]).toBe('keep going')
    await ui.unmount()
  }
})

test('a message to an agent row goes to that agent', async ($, on) => {
  const sent: any[] = []
  on('session.send', (_$, e) => {
    sent.push(e)
    return { isDelivered: true } as any
  })
  await start($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    sent.length = 0
    const ui = await $.ui.mount({ ...PANE, surface })
    // Default target is the first row: agent a1.
    await ui.input({ key: 'msg', text: 'stop after this file' })
    expect(sent[0]?.to?.agentId ?? sent[0]?.to).toBe('a1')
    expect(sent[0]?.text).toBe('stop after this file')
    await ui.unmount()
  }
})

test('the new-agent form starts a dispatch model with the picked effort', async ($, on) => {
  const seen: string[][] = []
  const wrote: string[] = []
  on('fs.write', (_$, e: any) => {
    wrote.push(e.path)
    return { value: undefined as any }
  })
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    return { value: { code: 0, signal: null } }
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'model', value: 'terra' })
  await ui.select({ key: 'effort', value: 'high' })
  await ui.input({ key: 'task', text: 'count lines in README.md' })
  const argv = seen.find(a => a.includes('dispatch')) ?? []
  expect(argv[argv.indexOf('--model') + 1]).toBe('terra')
  expect(argv[argv.indexOf('--effort') + 1]).toBe('high')
  expect(wrote[0]?.endsWith('/slots.json')).toBe(true)
  await ui.unmount()
})

test('the new-agent form starts luna as a native subagent', async ($, on) => {
  const spawned: any[] = []
  on('agent.spawn', (_$, e: any) => {
    spawned.push(e)
    return { model: 'gpt-6-luna' } as any
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.input({ key: 'task', text: 'say hi' })
  expect(spawned[0]?.subagent_type ?? spawned[0]?.subagentType).toBe('agents-inc:luna')
  expect(spawned[0]?.prompt).toBe('say hi')
  await ui.unmount()
})

test('a free model starts through agent.sh, not dispatch', async ($, on) => {
  const seen: string[][] = []
  on('fs.write', () => ({ value: undefined as any }))
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    yield { stream: 'stdout', text: 'hi\n' }
    return { value: { code: 0, signal: null } }
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'model', value: 'gemini' })
  await ui.input({ key: 'task', text: 'summarize README.md' })
  const argv = seen.find(a => a.includes('submit')) ?? []
  expect(argv[0]?.endsWith('skills/codex-bridge/scripts/agent.sh')).toBe(true)
  expect(argv[argv.indexOf('--backend') + 1]).toBe('gemini')
  expect(seen.some(a => a.includes('dispatch'))).toBe(false)
  await ui.unmount()
})

test('a failed start shows the exit code and last output line', async ($, on) => {
  on('fs.write', () => ({ value: undefined as any }))
  on('process.spawn', async function* () {
    yield { stream: 'stderr', text: 'dispatch: boom\n' }
    return { value: { code: 2, signal: null } }
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'model', value: 'terra' })
  await ui.input({ key: 'task', text: 'x' })
  await new Promise(r => setTimeout(r, 20))
  const t = await ui.find({ type: 'Text', text: /exit 2/ })
  expect(t?.text).toContain('dispatch: boom')
  await ui.unmount()
})

// 1 STABLE TARGET
test('a vanished target is refused, not retargeted to another row', async ($, on) => {
  const sent: any[] = []
  on('session.send', (_$, e) => {
    sent.push(e)
    return { isDelivered: true } as any
  })
  const world = await start($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    sent.length = 0
    world.agents = [{ id: 'a1', name: 'scout', type: 'Explore', description: 'scout', status: 'running' }]
    await world.advance(2100)
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.select({ key: 'target', value: 'agent:a1' })
    world.agents = []
    await world.advance(2100)
    await ui.input({ key: 'msg', text: 'hello' })
    expect(sent.length).toBe(0)
    expect((await ui.find({ type: 'Text', text: /target gone: .*scout/ }))?.text).toContain('target gone')
    await ui.unmount()
  }
})

// 2 ONE ROW PER START
test('a native start shows one job row until the agent appears', async ($, on) => {
  const spawned: any[] = []
  on('agent.spawn', (_$, e: any) => {
    spawned.push(e)
    return { model: 'm' } as any
  })
  const world = await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.input({ key: 'task', text: 'say hi' })
  expect((await ui.findAll({ type: 'Button', text: /say hi/ })).length).toBe(1)
  world.agents.push({ id: 'a2', name: 'luna', type: 'agents-inc:luna', description: 'new one', status: 'running' })
  await world.advance(2100)
  expect(await ui.find({ type: 'Button', text: /say hi/ })).toBeUndefined()
  expect((await ui.find({ type: 'Button', text: /new one/ }))?.text).toContain('luna')
  expect(spawned.length).toBe(1)
  await ui.unmount()
})

// The duplicate-start guard (same model+task while a job is 'starting') has no test: ui.input calls
// queue one after another in the harness, so a second start cannot overlap the first.

test('a dispatch job row ends once its run dir appears', async ($, on) => {
  const seen: string[][] = []
  on('fs.write', () => ({ value: undefined as any }))
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    return { value: { code: 0, signal: null } }
  })
  const world = await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'model', value: 'terra' })
  await ui.input({ key: 'task', text: 'count lines' })
  expect((await ui.findAll({ type: 'Button', text: /count lines/ })).length).toBe(1)
  const slots = seen[0]?.[seen[0].indexOf('--slots') + 1] ?? ''
  const NEW = '20991107T000100Z-terra-bbbbbb'
  world.dirs = [NEW, RUN]
  world.read = p => (p.endsWith('run.json') && p.includes(NEW) ? JSON.stringify({ model: 'terra', slots }) : DONE)
  await world.advance(2100)
  expect(await ui.find({ type: 'Button', text: /count lines/ })).toBeUndefined()
  expect((await ui.find({ type: 'Button', text: /bbbbbb|000100 terra/ }))?.text).toContain('dispatch')
  await ui.unmount()
})

test('a free job row ends done or failed with its exit code, with no stop control', async ($, on) => {
  on('fs.write', () => ({ value: undefined as any }))
  on('process.spawn', async function* () {
    yield { stream: 'stdout', text: 'all good\n' }
    return { value: { code: 0, signal: null } }
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.select({ key: 'model', value: 'mistral' })
  await ui.input({ key: 'task', text: 'free task' })
  expect((await ui.find({ type: 'Button', text: /free task/ }))?.text).toContain('done')
  expect((await ui.find({ type: 'Text', text: /exit 0: all good/ }))?.text).toContain('all good')
  expect(await ui.find({ type: 'Button', text: /cancel/ })).toBeUndefined()
  await ui.unmount()
})

test('a free start writes a run-style dir: run.json kind free, output rows, run.end', async ($, on) => {
  const wrote: Record<string, string> = {}
  on('fs.write', ($2: any, e: any) => {
    wrote[e.path] = e.text ?? e.content ?? e.data ?? ''
    return { value: undefined as any }
  })
  on('process.spawn', async function* () {
    yield { stream: 'stdout', text: 'line one\nline two\n' }
    return { value: { code: 0, signal: null } }
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.select({ key: 'model', value: 'gemini' })
  await ui.input({ key: 'task', text: 'free run dir' })
  await ui.find({ type: 'Button', text: /free run dir/ })
  const rj = Object.keys(wrote).find(k => /agents-inc-runs\/\d{8}T\d{6}Z-gemini-free\d+\/run\.json$/.test(k))
  expect(rj).toBeDefined()
  expect(JSON.parse(wrote[rj!]!).kind).toBe('free')
  const ev = wrote[rj!.replace('run.json', 'events.jsonl')]!
  expect(ev).toContain('line two')
  expect(ev).toContain('"run.end"')
  await ui.unmount()
})

// 3 HONEST FORM
test('the form shows effort only for dispatch models and says what the others use', async ($, on) => {
  await start($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.select({ key: 'model', value: 'luna' })
    expect(await ui.find({ key: 'effort' })).toBeUndefined()
    expect((await ui.find({ type: 'Text', text: /effort: session's/ }))?.text).toContain("session's")
    await ui.select({ key: 'model', value: 'gemini' })
    expect(await ui.find({ key: 'effort' })).toBeUndefined()
    expect((await ui.find({ type: 'Text', text: /backend default/ }))?.text).toContain('backend default')
    expect(await ui.find({ type: 'Text', text: /read-only · writes only report.md/ })).toBeUndefined()
    await ui.select({ key: 'model', value: 'sol' })
    expect(await ui.find({ key: 'effort' })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /read-only · writes only report.md/ }))?.text).toContain('read-only')
    await ui.unmount()
  }
})

// 4 STOP
test('a running run row has cancel, which calls dispatch --cancel', async ($, on) => {
  const seen: string[][] = []
  on('process.spawn', async function* (_$, e) {
    seen.push([...e.argv])
    return { value: { code: 0, signal: null } }
  })
  const world = await start($, on)
  world.read = () => LIVE
  await world.advance(2100)
  for (const surface of ['terminal', 'desktop'] as const) {
    seen.length = 0
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: `cancel-${RUN}` })
    expect(seen[0]).toEqual(['agents-inc', 'dispatch', '--cancel', `/work/.scratch/agents-inc-runs/${RUN}`])
    await ui.unmount()
  }
})

test('a finished run row has no cancel button', async ($, on) => {
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ key: `cancel-${RUN}` })).toBeUndefined()
  await ui.unmount()
})

test('ask to stop sends the stop text and says "stop requested", never "stopped"', async ($, on) => {
  const sent: any[] = []
  on('session.send', (_$, e) => {
    sent.push(e)
    return { isDelivered: true } as any
  })
  await start($, on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'stop-a1' })
  expect(sent[0]?.to?.agentId ?? sent[0]?.to).toBe('a1')
  expect(sent[0]?.text).toBe('Stop now and report what you have.')
  const row = await ui.find({ type: 'Button', text: /scout/ })
  expect(row?.text).toContain('stop requested')
  expect(row?.text).not.toContain('stopped')
  expect(await ui.find({ key: 'stop-a1' })).toBeUndefined()
  await ui.unmount()
})

// 5b OLD FINISHED RUNS ARE HISTORY
test('finished runs from before this session are not listed', async ($, on) => {
  const world = await start($, on)
  world.dirs = Array.from({ length: 12 }, (_, i) => `20200101T${String(i).padStart(2, '0')}0000Z-luna-old${String(i).padStart(3, '0')}`)
  world.read = () => DONE
  await world.advance(2100)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Button', text: /0000 luna/ })).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /0 running · 0 finished/ }))?.text).toContain('showing 0')
  await ui.unmount()
})

// 5 ACTIVE STAYS VISIBLE
test('every running run stays listed beyond the newest eight finished', async ($, on) => {
  const world = await start($, on)
  const OLD = '20261101T000000Z-luna-oldrun'
  const fin = Array.from({ length: 12 }, (_, i) => `20991107T${String(i).padStart(2, '0')}0000Z-luna-fin${String(i).padStart(3, '0')}`)
  world.dirs = [...fin, OLD]
  world.read = p => (p.includes(OLD) && p.endsWith('events.jsonl') ? LIVE : DONE)
  await world.advance(2100)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Button', text: /oldrun|0000 luna/ }))?.text).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /1 running · 12 finished \(showing 9\)/ }))?.text).toContain('showing 9')
    await ui.unmount()
  }
})
