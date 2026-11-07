import { expect, mock, test } from 'claude-code/testing'

const RUN = '20261107T000000Z-luna-aaaaaa'
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

// Stands for the engine: one live subagent, one finished dispatch run. Row 1 = agent a1, row 2 = the run.
async function start($: Dollar, on: On) {
  const clock = mock.clock(on)
  on('command.register', () => ({ value: { command: 'agents-manager' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('agent.list', () => ({
    value: [{ id: 'a1', name: 'scout', type: 'Explore', description: 'scout', status: 'running' }] as any,
  }))
  on('fs.list', () => ({ value: [{ name: RUN, kind: 'dir' }] as any }))
  on('fs.read', () => ({ value: '{"event":{"type":"run.end","outcome":"green","rc":0}}\n' as any }))
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  await clock.advance(2100)
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
    await ui.input({ key: 'msg', text: '2 keep going' })
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
    await ui.input({ key: 'msg', text: '1 stop after this file' })
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
