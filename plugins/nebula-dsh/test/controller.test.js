import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createController } from '../index.js'

const serverName = 'nebula_graph'
const version = '0.6.0+build.202611251234'
const python = '/private/test/venv/bin/python'
const firstPassword = 'test-only-initial-password'
const nextPassword = 'test-only-rotated-password'
const base = { name: 'Primary', addresses: 'graph.example.invalid:9669', username: 'reader', tls: true }
const save = (revision, patch = {}) => ({ action: 'save', revision, ...base, password: '', ...patch })
const action = (name, doc, id) => ({ action: name, revision: doc.revision, ...(id !== undefined && { id }) })
const defer = () => {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

async function setup(t, options = {}) {
  const events = []
  const secrets = new Map(options.secrets)
  let record = options.record
  let live
  let retiring = false
  let retained
  let beforeModify
  let nextDisposal
  let runtime = { state: 'ready', version, python, diagnostic: 'private runtime diagnostic' }
  const registrations = new Map()
  const subscribers = new Set()
  const changed = () => { for (const notify of subscribers) notify() }
  const credentials = {
    async readRecord() { return structuredClone(record) },
    async modifyRecord(_key, modify) {
      beforeModify?.()
      record = await modify(structuredClone(record))
      events.push(['commit', record.payload.activeId])
    },
    async set(ref, secret) {
      assert.equal(secrets.has(ref), false)
      secrets.set(ref, secret)
      events.push(['set', ref])
    },
    async unset(ref) {
      secrets.delete(ref)
      events.push(['unset', ref])
    },
    async describe(ref) {
      return { configured: secrets.has(ref), masked: secrets.get(ref) }
    },
  }
  const manager = {
    register(name, config) {
      assert.equal(registrations.has(name), false, 'replacement attempted before the previous process settled')
      assert.equal(retained, undefined, 'replacement attempted after incomplete cleanup')
      registrations.set(name, config)
      live = undefined
      events.push(['register', name])
      changed()
      return () => {
        events.push(['dispose:start', name])
        const pending = nextDisposal
        nextDisposal = undefined
        const finish = result => {
          registrations.delete(name)
          retiring = false
          retained = result === 'cleanup' ? { state: 'failed', reason: 'cleanup', result: { closeConfirmed: false } } : undefined
          events.push(['dispose:end', name])
          changed()
          if (result === 'reject') throw new Error('private close diagnostic')
        }
        if (!pending) return finish()
        retiring = true
        changed()
        pending.started.resolve()
        const done = pending.finish.promise.then(finish)
        if (!pending.returnsVoid) return done
      }
    },
    list() {
      return registrations.size ? [{ name: serverName, configured: !retiring, status: live }] :
        retained ? [{ name: serverName, configured: false, status: retained }] : []
    },
    async *watch(signal) {
      let ready = defer()
      const notify = () => ready.resolve()
      subscribers.add(notify)
      signal.addEventListener('abort', notify, { once: true })
      try {
        while (!signal.aborted) {
          yield manager.list()
          await ready.promise
          ready = defer()
        }
      } finally {
        subscribers.delete(notify)
        signal.removeEventListener('abort', notify)
      }
    },
    async restart(name) { events.push(['restart', name]) },
  }
  const controller = createController(credentials, manager, async () => runtime)
  t.after(() => controller.dispose())
  await controller.start()
  return {
    controller, events, secrets, registrations,
    get record() { return record },
    setLive(status) { live = status; changed() },
    setRuntime(value) { runtime = value },
    holdDisposal(returnsVoid) {
      const started = defer(), finish = defer()
      nextDisposal = { started, finish, returnsVoid }
      return { started: started.promise, finish: finish.resolve }
    },
    conflictAtCommit(revision) {
      beforeModify = () => {
        record.payload.revision = revision
        beforeModify = undefined
      }
    },
  }
}

function assertRegistration(registrations, ref, addresses = base.addresses) {
  assert.deepEqual([...registrations], [[serverName, {
    transport: 'stdio', command: python, args: ['-I', '-m', 'nebula_mcp.dsh_stdio'],
    env: {
      NEBULA_ADDRESSES: addresses,
      NEBULA_USERNAME: base.username,
      NEBULA_PASSWORD: '${credential:' + ref + '}',
      NEBULA_TLS_ENABLED: 'true',
    },
  }]])
}

async function twoConnections(controller) {
  const first = await controller.change(save('', { password: firstPassword }))
  const addresses = 'secondary.example.invalid:9670'
  const second = await controller.change(save(first.revision, { name: 'Secondary', addresses, password: nextPassword }))
  return { second, one: second.connections[0].id, two: second.connections[1].id, addresses }
}

test('supports zero or one active saved connection and clears without automatic fallback', async t => {
  const { controller, events, secrets, registrations } = await setup(t)
  assert.deepEqual(await controller.read(), {
    revision: '', connections: [], activeId: null, runtime: { state: 'ready', version }, mcp: { state: 'disabled' },
  })
  const { second, one, two, addresses } = await twoConnections(controller)
  const [firstRef, secondRef] = secrets.keys()
  assert.match(firstRef, /^DSH_NEBULA_PASSWORD_[0-9A-F]{32}$/)
  assert.notEqual(firstRef, secondRef)
  assert.deepEqual(second.connections, [
    { ...base, id: one, passwordSaved: true },
    { ...base, id: two, name: 'Secondary', addresses, passwordSaved: true },
  ])
  assert.equal(second.activeId, null)
  assert.deepEqual(second.mcp, { state: 'disabled' })
  assert.equal(registrations.size, 0)

  const active = await controller.change(action('activate', second, one))
  assert.equal(active.activeId, one)
  assertRegistration(registrations, firstRef)
  const switched = await controller.change(action('activate', active, two))
  assert.equal(switched.activeId, two)
  assertRegistration(registrations, secondRef, addresses)
  const disabled = await controller.change(action('deactivate', switched))
  assert.equal(disabled.activeId, null)
  assert.deepEqual(disabled.connections, second.connections)
  assert.deepEqual(disabled.mcp, { state: 'disabled' })
  assert.deepEqual([...secrets.values()], [firstPassword, nextPassword])
  assert.equal(registrations.size, 0)

  const reactivated = await controller.change(action('activate', disabled, one))
  events.length = 0
  const cleared = await controller.change(action('clear', reactivated, one))
  assert.equal(cleared.activeId, null)
  assert.deepEqual(cleared.connections, [second.connections[1]])
  assert.deepEqual(cleared.mcp, { state: 'disabled' })
  assert.equal(registrations.size, 0)
  assert.deepEqual([...secrets], [[secondRef, nextPassword]])
  assert.deepEqual(events, [['commit', null], ['dispose:start', serverName], ['dispose:end', serverName], ['unset', firstRef]])
})

test('active rename and inactive edits leave the active server untouched; replacement secrets stay isolated', async t => {
  const { controller, events, secrets, registrations } = await setup(t)
  const { second, one, two, addresses } = await twoConnections(controller)
  const active = await controller.change(action('activate', second, one))
  const [firstRef, secondRef] = secrets.keys()
  events.length = 0
  const renamed = await controller.change(save(active.revision, { id: one, name: ' Production ' }))
  assert.equal(renamed.connections[0].name, 'Production')
  assert.deepEqual(events.splice(0), [['commit', one]])
  assertRegistration(registrations, firstRef)

  const newAddr = 'replacement.example.invalid:9671'
  await assert.rejects(controller.change(save(renamed.revision, { id: one, addresses: newAddr })), { code: 'new-password' })
  await assert.rejects(controller.change(save(renamed.revision, { id: two, name: 'Secondary', addresses, tls: false })), { code: 'new-password' })
  assert.deepEqual(events, [])
  const edited = await controller.change(save(renamed.revision, {
    id: two, name: 'Secondary', addresses, password: 'secondary-rotation',
  }))
  const rotatedSecond = [...secrets.keys()].find(ref => ref !== firstRef)
  assert.deepEqual(events.splice(0), [['set', rotatedSecond], ['commit', one], ['unset', secondRef]])
  assertRegistration(registrations, firstRef)
  const updated = await controller.change(save(edited.revision, {
    id: one, name: 'Production', addresses: newAddr, password: 'primary-rotation',
  }))
  const rotatedFirst = [...secrets.keys()].find(ref => ref !== rotatedSecond)
  assert.notEqual(rotatedFirst, firstRef)
  assertRegistration(registrations, rotatedFirst, newAddr)
  assert.deepEqual(events.splice(0), [
    ['set', rotatedFirst], ['commit', one], ['dispose:start', serverName], ['dispose:end', serverName],
    ['register', serverName], ['unset', firstRef],
  ])
  assert.deepEqual(await controller.change({ action: 'restart' }), updated)
  assert.deepEqual(events.splice(0), [['restart', serverName]])

  const remaining = await controller.change(action('clear', updated, two))
  assert.equal(remaining.activeId, one)
  assertRegistration(registrations, rotatedFirst, newAddr)
  assert.deepEqual(events, [['commit', one], ['unset', rotatedSecond]])
})

for (const returnsVoid of [false, true]) {
  test(`switching waits for disposal even with ${returnsVoid ? 'a void' : 'an async'} disposer`, async t => {
    const fixture = await setup(t)
    const { controller, events, registrations, secrets } = fixture
    const { second, one, two, addresses } = await twoConnections(controller)
    const active = await controller.change(action('activate', second, one))
    const [firstRef, secondRef] = secrets.keys()
    const held = fixture.holdDisposal(returnsVoid)
    events.length = 0
    const switching = controller.change(action('activate', active, two))
    await held.started
    let readComplete = false
    const reading = controller.read().then(state => { readComplete = true; return state })
    const stale = assert.rejects(controller.change(action('deactivate', active)), { code: 'conflict', status: 409 })
    await Promise.resolve()
    assert.equal(readComplete, false)
    assertRegistration(registrations, firstRef)
    assert.deepEqual(events, [['commit', two], ['dispose:start', serverName]])
    held.finish()
    const switched = await switching
    await stale
    assert.deepEqual(await reading, switched)
    assertRegistration(registrations, secondRef, addresses)
    assert.deepEqual(events, [['commit', two], ['dispose:start', serverName], ['dispose:end', serverName], ['register', serverName]])
  })
}

for (const [outcome, returnsVoid] of [['cleanup', true], ['reject', false]]) {
  test(`a ${outcome} disposal failure permanently blocks replacement until Host restart`, async t => {
    const fixture = await setup(t)
    const { controller, events, registrations } = fixture
    const { second, one, two } = await twoConnections(controller)
    const active = await controller.change(action('activate', second, one))
    const held = fixture.holdDisposal(returnsVoid)
    events.length = 0
    const switching = controller.change(action('activate', active, two))
    await held.started
    held.finish(outcome)
    const switched = await switching
    assert.equal(switched.activeId, two)
    assert.deepEqual(switched.mcp, { state: 'host-restart-required' })
    assert.deepEqual(await controller.change({ action: 'restart' }), switched)
    const disabled = await controller.change(action('deactivate', switched))
    assert.equal(disabled.activeId, null)
    assert.deepEqual(disabled.mcp, { state: 'host-restart-required' })
    const selected = await controller.change(action('activate', disabled, one))
    assert.deepEqual(selected.mcp, { state: 'host-restart-required' })
    assert.equal(registrations.size, 0)
    assert.deepEqual(events, [['commit', two], ['dispose:start', serverName], ['dispose:end', serverName], ['commit', null], ['commit', one]])
  })
}

test('unclosed-generation blocks restart and switching even if the manager row then disappears', async t => {
  const { controller, events, setLive } = await setup(t)
  const { second, one, two } = await twoConnections(controller)
  const active = await controller.change(action('activate', second, one))
  events.length = 0
  setLive({ state: 'failed', reason: 'unclosed-generation', lastError: 'private close diagnostic' })
  assert.deepEqual((await controller.read()).mcp, { state: 'host-restart-required' })
  const switched = await controller.change(action('activate', active, two))
  assert.equal(switched.activeId, two)
  assert.deepEqual((await controller.change({ action: 'restart' })).mcp, { state: 'host-restart-required' })
  assert.deepEqual(events, [['commit', two], ['dispose:start', serverName], ['dispose:end', serverName]])
})

for (const enabled of [false, true]) {
  test(`legacy connection migration preserves secret and ${enabled ? 'active' : 'inactive'} state`, async t => {
    const ref = 'DSH_NEBULA_PASSWORD_' + 'A'.repeat(32)
    const legacy = { kind: 'grant', payload: { revision: 'old-revision', connection: { ...base, enabled, passwordRef: ref } } }
    const fixture = await setup(t, { record: legacy, secrets: [[ref, firstPassword]] })
    const { controller, secrets, registrations, events } = fixture
    const loaded = await controller.read()
    const migrated = { ...base, id: 'legacy', name: 'Default', passwordSaved: true }
    assert.equal(loaded.revision, 'old-revision')
    assert.deepEqual(loaded.connections, [migrated])
    assert.equal(loaded.activeId, enabled ? 'legacy' : null)
    assert.equal(registrations.size, Number(enabled))
    assert.deepEqual(fixture.record, legacy)
    const rechecked = await controller.change({ action: 'restart' })
    assert.equal(rechecked.revision, loaded.revision)
    events.length = 0
    const saved = await controller.change(save(loaded.revision, { id: 'legacy', name: 'Legacy renamed' }))
    assert.deepEqual(saved.connections, [{ ...migrated, name: 'Legacy renamed' }])
    assert.equal(saved.activeId, loaded.activeId)
    assert.deepEqual(fixture.record, { kind: 'grant', payload: {
      revision: saved.revision,
      connections: [{ ...base, id: 'legacy', name: 'Legacy renamed', passwordRef: ref }],
      activeId: loaded.activeId,
    } })
    assert.notEqual(saved.revision, loaded.revision)
    assert.deepEqual([...secrets], [[ref, firstPassword]])
    assert.equal(registrations.size, Number(enabled))
    assert.deepEqual(events, [['commit', loaded.activeId]])
  })
}

test('reading or rejecting an old empty layout does not persist; successful mutations keep its revision check', async t => {
  const legacy = { kind: 'grant', payload: { revision: 'old-empty', connection: null } }
  const fixture = await setup(t, { record: legacy })
  const { controller } = fixture
  assert.equal((await controller.read()).revision, 'old-empty')
  assert.deepEqual(fixture.record, legacy)
  await assert.rejects(controller.change(save('', { password: firstPassword })), { code: 'conflict', status: 409 })
  assert.deepEqual(fixture.record, legacy)
  const saved = await controller.change(save('old-empty', { password: firstPassword }))
  assert.equal(saved.activeId, null)
  assert.deepEqual(Object.keys(fixture.record.payload), ['revision', 'connections', 'activeId'])
  assert.notEqual(saved.revision, 'old-empty')
})

test('validation handles missing ids, duplicate names, name length and the connection limit', async t => {
  const { controller, events, secrets } = await setup(t)
  await assert.rejects(controller.change(save('', { name: ' '.repeat(4) })), { code: 'name' })
  await assert.rejects(controller.change(save('', { name: 'x'.repeat(65) })), { code: 'name' })
  await assert.rejects(controller.change(save('', { name: 'a\nb' })), { code: 'name' })
  await assert.rejects(controller.change(save('')), { code: 'password' })
  assert.deepEqual(events, [])
  let saved = await controller.change(save('', { name: 'A'.repeat(64), password: firstPassword }))
  await assert.rejects(controller.change(save(saved.revision, { name: 'a'.repeat(64), password: nextPassword })), { code: 'duplicate-name' })
  await assert.rejects(controller.change(save(saved.revision, { id: 'missing', password: nextPassword })), { code: 'not-found', status: 404 })
  for (const mutation of ['activate', 'clear']) {
    await assert.rejects(controller.change(action(mutation, saved, 'missing')), { code: 'not-found', status: 404 })
  }
  for (let i = 1; i < 20; i++) saved = await controller.change(save(saved.revision, { name: `Connection ${i}`, password: nextPassword }))
  await assert.rejects(controller.change(save(saved.revision, { name: 'Twenty-one', password: nextPassword })), { code: 'limit' })
  assert.equal(secrets.size, 20)
  const edited = await controller.change(save(saved.revision, { id: saved.connections[0].id, name: 'still editable' }))
  assert.equal(edited.connections.length, 20)
})

test('stale revisions do not mutate and a commit conflict unsets only the candidate secret', async t => {
  const fixture = await setup(t)
  const { controller, events, secrets, registrations } = fixture
  const { second, one } = await twoConnections(controller)
  const active = await controller.change(action('activate', second, one))
  const [firstRef, secondRef] = secrets.keys()
  events.length = 0
  await assert.rejects(controller.change(save(second.revision, { id: one, password: nextPassword })), { code: 'conflict', status: 409 })
  await assert.rejects(controller.change(action('restart', second)), { code: 'conflict', status: 409 })
  assert.deepEqual(events, [])
  assert.deepEqual(await controller.read(), active)

  fixture.conflictAtCommit('other-writer')
  await assert.rejects(controller.change(save(active.revision, { id: one, password: nextPassword })), { code: 'conflict', status: 409 })
  const [, candidate] = events[0]
  assert.notEqual(candidate, firstRef)
  assert.notEqual(candidate, secondRef)
  assert.deepEqual(events, [['set', candidate], ['unset', candidate]])
  assert.deepEqual([...secrets], [[firstRef, firstPassword], [secondRef, nextPassword]])
  assert.equal(fixture.record.payload.revision, 'other-writer')
  assert.deepEqual(fixture.record.payload.connections.map(row => row.passwordRef), [firstRef, secondRef])
  assertRegistration(registrations, firstRef)
})

test('snapshots project status, runtime, and each secret without exposing private details', async t => {
  const { controller, secrets, setLive, setRuntime, registrations } = await setup(t)
  const { second, one } = await twoConnections(controller)
  const saved = await controller.change(action('activate', second, one))
  const [ref, inactiveRef] = secrets.keys()
  secrets.delete(inactiveRef)
  setLive({ state: 'failed', toolCount: 3, lastError: `${firstPassword} ${ref} ${python}` })
  const expected = {
    revision: saved.revision,
    connections: [saved.connections[0], { ...saved.connections[1], passwordSaved: false }],
    activeId: one,
    runtime: { state: 'ready', version },
    mcp: { state: 'failed' },
  }
  assert.deepEqual(await controller.read(), expected)
  setLive({ state: 'connected', toolCount: 8, error: firstPassword, command: python })
  assert.deepEqual(await controller.read(), { ...expected, mcp: { state: 'connected', toolCount: 8 } })
  setRuntime({ state: 'missing', diagnostic: python })
  assert.deepEqual(await controller.change({ action: 'restart' }), {
    ...expected, runtime: { state: 'missing', version: undefined }, mcp: { state: 'disabled' },
  })
  assert.equal(registrations.size, 0)
})
