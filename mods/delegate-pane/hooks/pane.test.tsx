import { expect, mock, test } from 'claude-code/testing'

import { isNative, mergeAgents, offeredTypes, PANE } from './register'

type On = Parameters<Parameters<typeof test>[1]>[1]
type Dollar = Parameters<Parameters<typeof test>[1]>[0]

const STATUS = JSON.stringify({
  models: [
    { nickname: 'luna', offered: true, slug: 'gpt-6-luna' },
    { nickname: 'gemini-flash', offered: false, slug: 'gemini-3.8-flash' },
  ],
  legacy_routes: false,
})
const MOUNT = {
  plugin: 'delegate-pane',
  component: 'Pane',
  requestId: PANE,
  props: { title: 'agents-inc native agents', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

async function start($: Dollar, on: On, world: { agents: any[]; dirs: string[] }) {
  const clock = mock.clock(on)
  on('command.register', () => ({ value: { command: 'delegate-pane' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('agent.list', () => ({ value: world.agents as any }))
  // A dispatch run dir on disk: FR-020 says the pane must not list it.
  on('fs.list', () => ({ value: world.dirs.map(name => ({ name, kind: 'dir' })) as any }))
  on('process.spawn', async function* () {
    yield { stream: 'stdout' as const, text: STATUS }
    return { value: { code: 0, signal: null } }
  })
  await $.session.start({ cwd: '/work', surface: 'desktop', isInteractive: true })
  await clock.advance(1100)
  return clock
}

test('the pane lists registered native types and native agents, never a dispatch run dir (FR-020)', async ($, on) => {
  const world = {
    agents: [
      { id: 'a1', type: 'agents-inc:luna', description: 'read the repo', status: 'running' },
      { id: 'a2', type: 'Explore', description: 'scout', status: 'running' },
      { id: 'a3', type: 'agents-inc:relay', description: 'old route', status: 'running' },
    ],
    dirs: ['20991107T000000Z-sonnet-aaaaaa'],
  }
  await start($, on, world)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /agents-inc:luna · read the repo/ }))?.text).toContain('running')
  expect(await ui.find({ type: 'Text', text: /^ {2}agents-inc:luna$/ })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /gemini-flash/ })).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /scout/ })).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /old route/ })).toBeFalsy()
  expect(await ui.find({ type: 'Text', text: /aaaaaa/ })).toBeFalsy()
  await ui.unmount()
})

test('a finished native agent stays listed after the engine stops listing it', async ($, on) => {
  const world = { agents: [{ id: 'a1', type: 'agents-inc:terra', description: 'fix it', status: 'running' }] as any[], dirs: [] }
  const clock = await start($, on, world)
  world.agents = []
  await clock.advance(1100)
  const ui = await $.ui.mount({ ...MOUNT, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /agents-inc:terra · fix it/ }))?.text).toContain('finished')
  await ui.unmount()
})

test('pure helpers: native filter, merge, offered types', () => {
  expect(isNative('agents-inc:luna')).toBe(true)
  expect(isNative('agents-inc:relay')).toBe(false)
  expect(isNative('general-purpose')).toBe(false)
  const one = mergeAgents([], [{ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'running' }])
  expect(mergeAgents(one, [])).toEqual([{ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'finished' }])
  expect(mergeAgents([{ id: 'x', type: 'agents-inc:sol', description: 'd', status: 'completed' }], [])[0].status).toBe('completed')
  expect(offeredTypes(STATUS)).toEqual(['agents-inc:luna'])
  expect(offeredTypes('not json')).toEqual([])
})
