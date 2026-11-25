import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createController, registerRoute, registerTestRoute, TEST_ROUTE } from '../index.js'

const path = '/api/nebula-dsh/settings'
const url = `http://localhost${path}`
const jsonHeaders = { 'content-type': 'application/json; charset=utf-8', 'x-dsh-nebula-settings': '1' }
const browserOwner = { id: 'browser', principal: { kind: 'owner' } }

function setup(controller) {
  let route
  const admissions = []
  const peers = new WeakMap()
  const dispose = () => {}
  const connection = {
    browserPeer: { id: 'browser' },
    admit(request) {
      admissions.push(request)
      return { peer: peers.get(request) }
    },
    fetch: {
      register(definition) {
        route = definition
        return dispose
      },
    },
  }
  assert.equal(registerRoute(connection, controller), dispose)
  assert.equal(route.path, path)
  assert.deepEqual(route.methods, ['GET', 'POST'])
  // Buffered: the bridge attaches a stream body only in streaming mode, and a
  // GET Request cannot carry a body, which made every settings read fail with
  // an empty 400. Settings bodies are tiny, so buffering is the correct mode.
  assert.equal(route.requestBody, 'buffered')
  return {
    admissions,
    fetch(request, peer = browserOwner) {
      peers.set(request, peer)
      return route.fetch(request)
    },
  }
}

function post(body, headers = jsonHeaders) {
  return new Request(url, { method: 'POST', headers, body, duplex: 'half' })
}

async function assertResponse(response, status, body) {
  assert.equal(response.status, status)
  assert.equal(response.headers.get('content-type'), 'application/json; charset=utf-8')
  assert.equal(response.headers.get('cache-control'), 'no-store')
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff')
  assert.deepEqual(await response.json(), body)
}

test('route admits only the owner browser peer through connection.admit', async () => {
  const calls = []
  const { fetch, admissions } = setup({
    async read() { calls.push('read'); return { revision: '' } },
    async change(body) { calls.push(body); return { accepted: true } },
  })
  for (const peer of [null, { ...browserOwner, id: 'another-peer' },
    { ...browserOwner, principal: { kind: 'member' } }]) {
    const request = post('{"action":"restart"}', { ...jsonHeaders, origin: 'http://localhost' })
    await assertResponse(await fetch(request, peer), 403, { error: 'forbidden' })
    assert.equal(admissions.at(-1), request)
    assert.equal(request.bodyUsed, false)
  }
  assert.deepEqual(calls, [])

  const get = new Request(url)
  await assertResponse(await fetch(get), 200, { revision: '' })
  assert.equal(admissions.at(-1), get)
  const change = { action: 'restart' }
  await assertResponse(await fetch(post(JSON.stringify(change))), 200, { accepted: true })
  assert.deepEqual(calls, ['read', change])
})

test('route rejects missing guard, wrong media type, malformed JSON and invalid UTF-8', async () => {
  const changes = []
  const { fetch } = setup({ async change(body) { changes.push(body) } })
  for (const headers of [{ 'content-type': 'application/json' },
    { ...jsonHeaders, 'content-type': 'text/plain' }]) {
    const request = post('{}', headers)
    await assertResponse(await fetch(request), 415, { error: 'invalid' })
    assert.equal(request.bodyUsed, false)
  }
  await assertResponse(await fetch(post('{')), 400, { error: 'invalid' })
  await assertResponse(await fetch(post(new Uint8Array([0xff]))), 400, { error: 'invalid' })
  assert.deepEqual(changes, [])
})

test('route counts body bytes and cancels an oversized stream without reading the rest', async () => {
  const changes = []
  const { fetch } = setup({ async change(body) { changes.push(body) } })
  const encoder = new TextEncoder()
  const chunks = ['{"value":"' + '界'.repeat(3000), '界'.repeat(3000) + '"}', 'unread'].map(
    chunk => encoder.encode(chunk),
  )
  let reads = 0
  let cancelled = false
  const body = new ReadableStream({
    pull(controller) {
      controller.enqueue(chunks[reads++])
      if (reads === chunks.length) controller.close()
    },
    cancel() { cancelled = true },
  }, { highWaterMark: 0 })
  await assertResponse(await fetch(post(body)), 413, { error: 'invalid' })
  assert.equal(reads, 2)
  assert.equal(cancelled, true)
  assert.deepEqual(changes, [])
})

test('route preserves UTF-8 code points split across streamed chunks', async () => {
  const { fetch } = setup({ async change(body) { return body } })
  const bytes = new TextEncoder().encode('{"value":"界"}')
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(bytes.slice(0, 11))
      controller.enqueue(bytes.slice(11))
      controller.close()
    },
  })
  await assertResponse(await fetch(post(body)), 200, { value: '界' })
})

test('route returns the same redacted multi-connection contract for GET and successful mutations', async t => {
  const secrets = new Map()
  let record
  const credentials = {
    async readRecord() { return record },
    async modifyRecord(_key, modify) { record = await modify(record) },
    async set(ref, value) { secrets.set(ref, value) },
    async unset(ref) { secrets.delete(ref) },
    async describe(ref) { return { configured: secrets.has(ref), masked: secrets.get(ref) } },
  }
  const controller = createController(credentials, { list: () => [] }, async () => ({ state: 'missing' }))
  t.after(() => controller.dispose())
  await controller.start()
  const { fetch } = setup(controller)
  const get = () => fetch(new Request(url))
  const change = body => fetch(post(JSON.stringify(body)))
  const initial = { revision: '', connections: [], activeId: null, runtime: { state: 'missing' }, mcp: { state: 'disabled' } }
  await assertResponse(await get(), 200, initial)
  const fields = { name: 'Graph', addresses: 'graph.example.invalid:9669', username: 'reader', tls: true }
  const response = await change({ action: 'save', revision: '', ...fields, password: 'test-secret' })
  assert.equal(response.status, 200)
  const { revision, connections } = await response.clone().json()
  const [row] = connections
  const id = row.id
  assert.equal(typeof id, 'string')
  assert.equal(typeof revision, 'string')
  const saved = { ...initial, revision, connections: [{ ...fields, id, passwordSaved: true }] }
  await assertResponse(response, 200, saved)
  await assertResponse(await get(), 200, saved)
  await assertResponse(await change({ action: 'save', revision, ...fields, name: ' GrApH ', password: 'test-secret' }),
    400, { error: 'duplicate-name' })
  await assertResponse(await change({ action: 'activate', revision, id: 'missing' }), 404, { error: 'not-found' })
  const activating = await change({ action: 'activate', revision, id })
  const active = { ...saved, revision: (await activating.clone().json()).revision, activeId: id }
  await assertResponse(activating, 200, active)
  await assertResponse(await get(), 200, active)
  const clearing = await change({ action: 'clear', revision: active.revision, id })
  const cleared = { ...initial, revision: (await clearing.clone().json()).revision }
  await assertResponse(clearing, 200, cleared)
  await assertResponse(await get(), 200, cleared)
  assert.equal(secrets.size, 0)
})

test('route maps stale revisions and redacts errors from its services', async t => {
  const controller = createController({ async readRecord() { return null } }, {})
  t.after(() => controller.dispose())
  const { fetch } = setup(controller)
  await assertResponse(await fetch(post('{"action":"clear","revision":"stale"}')),
    409, { error: 'conflict' })

  const broken = setup({ async read() { throw new Error('private store path and password') } })
  await assertResponse(await broken.fetch(new Request(url)), 500, { error: 'store' })
})

test('test route returns probe results to the owner browser only', async () => {
  let route
  const owner = { id: 'browser', principal: { kind: 'owner' } }
  const connection = {
    browserPeer: { id: 'browser' },
    admit: () => ({ peer: owner }),
    fetch: { register(definition) { route = definition; return () => {} } },
  }
  const controller = {
    async test(id) { return { ok: true, version: '5.3.2', latencyMs: 12, id } },
    async testDraft(draft) { return { ok: true, version: '5.3.4', latencyMs: 9, draft } },
  }
  registerTestRoute(connection, controller)
  assert.equal(route.path, TEST_ROUTE)
  assert.deepEqual(route.methods, ['POST'])
  assert.equal(route.requestBody, 'buffered')
  const post = (body, headers = jsonHeaders) => new Request('http://localhost' + TEST_ROUTE, {
    method: 'POST', headers, body, duplex: 'half',
  })
  const response = await route.fetch(post(JSON.stringify({ id: 'legacy' })))
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { ok: true, version: '5.3.2', latencyMs: 12, id: 'legacy' })

  const draft = { addresses: 'db.example.net:9669', username: 'root', password: 'secret', tls: false }
  const draftResponse = await route.fetch(post(JSON.stringify({ draft })))
  assert.equal(draftResponse.status, 200)
  assert.deepEqual(await draftResponse.json(), { ok: true, version: '5.3.4', latencyMs: 9, draft })

  assert.equal((await route.fetch(post(JSON.stringify({ id: 'legacy' }), { 'content-type': 'application/json' }))).status, 415)
  assert.equal((await route.fetch(post(JSON.stringify({ id: '' })))).status, 400)
  connection.admit = () => ({ peer: { id: 'other', principal: { kind: 'owner' } } })
  assert.equal((await route.fetch(post(JSON.stringify({ id: 'legacy' })))).status, 403)
})
