import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createController, registerRoute } from '../index.js'

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
  assert.equal(route.requestBody, 'streaming')
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

test('route maps stale revisions and redacts errors from its services', async t => {
  const controller = createController({ async readRecord() { return null } }, {})
  t.after(() => controller.dispose())
  const { fetch } = setup(controller)
  await assertResponse(await fetch(post('{"action":"clear","revision":"stale"}')),
    409, { error: 'conflict' })

  const broken = setup({ async read() { throw new Error('private store path and password') } })
  await assertResponse(await broken.fetch(new Request(url)), 500, { error: 'store' })
})
