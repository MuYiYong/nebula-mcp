import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createController } from '../index.js'

const serverName = 'nebula_graph'
const version = '0.6.0+build.202611251234'
const python = '/private/test/venv/bin/python'
const firstPassword = 'test-only-initial-password'
const nextPassword = 'test-only-rotated-password'
const base = { addresses: 'graph.example.invalid:9669', username: 'reader', tls: true, enabled: true }
const save = (revision, patch = {}) => ({ action: 'save', revision, ...base, password: '', ...patch })

async function setup(t) {
  const events = []
  const secrets = new Map()
  let record
  let live
  let beforeModify
  const registrations = new Map()
  const credentials = {
    async readRecord() { return structuredClone(record) },
    async modifyRecord(_key, modify) {
      beforeModify?.()
      record = await modify(structuredClone(record))
      events.push(['commit', record.payload.connection?.passwordRef])
    },
    async set(ref, secret) {
      secrets.set(ref, secret)
      events.push(['set', ref])
    },
    async unset(ref) {
      secrets.delete(ref)
      events.push(['unset', ref])
    },
    async describe(ref) {
      return { configured: secrets.has(ref), diagnostic: secrets.get(ref) }
    },
  }
  const manager = {
    register(name, config) {
      assert.equal(registrations.has(name), false)
      registrations.set(name, config)
      events.push(['register', name])
      return async () => {
        registrations.delete(name)
        events.push(['dispose', name])
      }
    },
    list() {
      return [...registrations.keys()].map(name => ({ name, status: live }))
    },
    async restart(name) { events.push(['restart', name]) },
  }
  const controller = createController(credentials, manager, async () => ({
    state: 'ready', version, python, diagnostic: 'private runtime diagnostic',
  }))
  t.after(() => controller.dispose())
  await controller.start()
  return {
    controller, events, secrets, registrations,
    get record() { return record },
    setLive(status) { live = status },
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

test('replaces credentials only after saving a new reference and replaces the MCP registration', async t => {
  const { controller, events, secrets, registrations } = await setup(t)
  const initial = await controller.read()
  assert.equal(initial.connection, null)
  assert.equal(initial.passwordSaved, false)
  assert.equal(initial.mcp.state, 'disabled')

  const first = await controller.change(save(initial.revision, { password: firstPassword }))
  const [oldRef] = secrets.keys()
  assert.match(oldRef, /^DSH_NEBULA_PASSWORD_[0-9A-F]{32}$/)
  assert.equal(secrets.get(oldRef), firstPassword)
  assertRegistration(registrations, oldRef)
  assert.deepEqual(events.splice(0), [['set', oldRef], ['commit', oldRef], ['register', serverName]])

  const addresses = 'replacement.example.invalid:9670'
  await assert.rejects(controller.change(save(first.revision, { addresses })), { code: 'new-password' })
  assert.deepEqual(events, [])
  assertRegistration(registrations, oldRef)

  const next = await controller.change(save(first.revision, { addresses, password: nextPassword }))
  const [newRef] = secrets.keys()
  assert.notEqual(newRef, oldRef)
  assert.notEqual(next.revision, first.revision)
  assert.deepEqual([...secrets], [[newRef, nextPassword]])
  assertRegistration(registrations, newRef, addresses)
  assert.deepEqual(events.splice(0), [
    ['set', newRef], ['commit', newRef], ['dispose', serverName], ['register', serverName], ['unset', oldRef],
  ])

  assert.deepEqual(await controller.change({ action: 'restart' }), next)
  assert.deepEqual(events, [['restart', serverName]])
})

test('disable detaches MCP without losing the secret, and clear removes it after re-enable', async t => {
  const { controller, events, secrets, registrations } = await setup(t)
  const first = await controller.change(save('', { password: firstPassword }))
  const [ref] = secrets.keys()
  events.length = 0

  const disabled = await controller.change(save(first.revision, { enabled: false }))
  assert.deepEqual(disabled.connection, { ...base, enabled: false })
  assert.equal(disabled.passwordSaved, true)
  assert.deepEqual(disabled.mcp, { state: 'disabled' })
  assert.deepEqual([...secrets], [[ref, firstPassword]])
  assert.equal(registrations.size, 0)
  assert.deepEqual(events.splice(0), [['commit', ref], ['dispose', serverName]])

  const enabled = await controller.change(save(disabled.revision))
  assert.equal(enabled.connection.enabled, true)
  assertRegistration(registrations, ref)
  assert.deepEqual(events.splice(0), [['commit', ref], ['register', serverName]])

  const cleared = await controller.change({ action: 'clear', revision: enabled.revision })
  assert.equal(cleared.connection, null)
  assert.equal(cleared.passwordSaved, false)
  assert.deepEqual(cleared.mcp, { state: 'disabled' })
  assert.equal(registrations.size, 0)
  assert.equal(secrets.size, 0)
  assert.deepEqual(events, [['commit', undefined], ['dispose', serverName], ['unset', ref]])
})

test('stale settings do not mutate anything and a commit conflict deletes only the candidate secret', async t => {
  const fixture = await setup(t)
  const { controller, events, secrets, registrations } = fixture
  const first = await controller.change(save('', { password: firstPassword }))
  const [ref] = secrets.keys()
  events.length = 0

  await assert.rejects(controller.change(save('', { password: nextPassword })), { code: 'conflict', status: 409 })
  assert.deepEqual(events, [])
  assert.deepEqual(await controller.read(), first)

  fixture.conflictAtCommit('other-writer')
  await assert.rejects(controller.change(save(first.revision, { password: nextPassword })), {
    code: 'conflict', status: 409,
  })
  const [, candidate] = events[0]
  assert.notEqual(candidate, ref)
  assert.deepEqual(events, [['set', candidate], ['unset', candidate]])
  assert.deepEqual([...secrets], [[ref, firstPassword]])
  assert.equal(fixture.record.payload.revision, 'other-writer')
  assert.equal(fixture.record.payload.connection.passwordRef, ref)
  assertRegistration(registrations, ref)
})

test('controller snapshots never expose credential, runtime, or manager diagnostics', async t => {
  const { controller, secrets, setLive } = await setup(t)
  const saved = await controller.change(save('', { password: firstPassword }))
  const [ref] = secrets.keys()
  setLive({ state: 'failed', toolCount: 3, error: `${firstPassword} ${ref} ${python}` })
  const expected = {
    revision: saved.revision,
    connection: base,
    passwordSaved: true,
    runtime: { state: 'ready', version },
    mcp: { state: 'failed' },
  }
  assert.deepEqual(await controller.read(), expected)
  setLive({ state: 'connected', toolCount: 8, error: firstPassword, command: python })
  assert.deepEqual(await controller.read(), { ...expected, mcp: { state: 'connected', toolCount: 8 } })
})
