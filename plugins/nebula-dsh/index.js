import { randomUUID } from 'node:crypto'
import { inspectRuntime, MODULE } from './runtime.js'

export const name = 'nebula-dsh'
export const inject = ['credentials', 'mcpManager', 'connection']
export const SERVER = 'nebula_graph'
export const ROUTE = '/api/nebula-dsh/settings'
const KEY = 'nebula-dsh/connection'
const REF = /^DSH_NEBULA_PASSWORD_[0-9A-F]{32}$/
const initial = { revision: '', connection: null }
const forbidden = /[\u0000-\u001f\u007f]/u
const knownStates = new Set(['connecting', 'connected', 'reconnecting', 'failed', 'closed', 'waiting-credentials'])

class SettingsError extends Error {
  constructor(code, status = 400) {
    super(code)
    this.code = code
    this.status = status
  }
}

function normalizeConnection(input) {
  if (typeof input?.addresses !== 'string' || input.addresses.length > 2000) throw new SettingsError('addresses')
  const addresses = input.addresses.split(',').map(part => {
    const match = /^(\[[0-9a-f:.]+\]|[^\s,:/\\?#@${}\[\]]+):(\d{1,5})$/iu.exec(part.trim())
    if (!match || Number(match[2]) < 1 || Number(match[2]) > 65535 || forbidden.test(match[1])) {
      throw new SettingsError('addresses')
    }
    return `${match[1]}:${Number(match[2])}`
  }).join(', ')
  if (typeof input.username !== 'string' || !input.username.trim() || input.username.length > 256 ||
      forbidden.test(input.username) || input.username.includes('${')) throw new SettingsError('username')
  if (typeof input.tls !== 'boolean' || typeof input.enabled !== 'boolean') throw new SettingsError('invalid')
  return { addresses, username: input.username.trim(), tls: input.tls, enabled: input.enabled }
}

function decode(record) {
  if (!record) return initial
  const doc = record.payload
  if (record.kind !== 'grant' || typeof doc?.revision !== 'string') throw new SettingsError('store', 500)
  if (doc.connection === null) return { revision: doc.revision, connection: null }
  const { passwordRef } = doc.connection ?? {}
  if (typeof passwordRef !== 'string' || !REF.test(passwordRef)) throw new SettingsError('store', 500)
  return { revision: doc.revision, connection: { ...normalizeConnection(doc.connection), passwordRef } }
}

export function createController(credentials, manager, findRuntime = inspectRuntime) {
  let runtime = { state: 'checking' }
  let status = 'disabled'
  let registered
  let queue = Promise.resolve()
  let disposed = false
  const serialize = task => {
    const next = queue.then(task)
    queue = next.catch(() => {})
    return next
  }
  const read = async () => decode(await credentials.readRecord(KEY))

  async function detach() {
    const prior = registered
    registered = undefined
    await prior?.dispose()
  }

  async function reconcile(doc, restart = false) {
    const config = doc.connection
    if (disposed || !config?.enabled || runtime.state !== 'ready') {
      await detach()
      status = 'disabled'
      return
    }
    const identity = JSON.stringify([runtime.python, config])
    try {
      if (registered?.identity === identity) {
        if (restart) await manager.restart(SERVER)
        return
      }
      await detach()
      const dispose = manager.register(SERVER, {
        transport: 'stdio',
        command: runtime.python,
        args: ['-I', '-m', MODULE],
        env: {
          NEBULA_ADDRESSES: config.addresses,
          NEBULA_USERNAME: config.username,
          NEBULA_PASSWORD: '${credential:' + config.passwordRef + '}',
          NEBULA_TLS_ENABLED: String(config.tls),
        },
      })
      registered = { identity, dispose }
      status = 'connecting'
    } catch {
      status = 'registration-error'
    }
  }

  async function snapshot(doc) {
    const saved = doc.connection
    // Both registered and declaratively configured entries have `configured: true`.
    const slot = manager.list().find(row => row.name === SERVER)?.status
    const needsHostRestart = slot?.state === 'failed' && ['cleanup', 'unclosed-generation'].includes(slot.reason)
    const live = registered ? slot : undefined
    const passwordSaved = saved ? (await credentials.describe(saved.passwordRef)).configured : false
    // Explicit projection: no reference names, secrets, paths or provider diagnostics.
    return {
      revision: doc.revision,
      connection: saved ? {
        addresses: saved.addresses, username: saved.username, tls: saved.tls, enabled: saved.enabled,
      } : null,
      passwordSaved,
      runtime: { state: runtime.state, version: runtime.version },
      mcp: {
        state: needsHostRestart ? 'host-restart-required' :
          knownStates.has(live?.state) && status !== 'registration-error' ? live.state : status,
        ...(live?.state === 'connected' && status !== 'registration-error' && { toolCount: live.toolCount }),
      },
    }
  }

  async function commit(previous, connection) {
    const next = { revision: randomUUID(), connection }
    await credentials.modifyRecord(KEY, async current => {
      if (decode(current).revision !== previous.revision) throw new SettingsError('conflict', 409)
      return { kind: 'grant', payload: next }
    })
    return next
  }

  async function change(body) {
    if (disposed) throw new SettingsError('unavailable', 503)
    const previous = await read()
    if (body?.action === 'restart') {
      runtime = await findRuntime()
      await reconcile(previous, true)
      return snapshot(previous)
    }
    if (typeof body?.revision !== 'string' || body.revision !== previous.revision) {
      throw new SettingsError('conflict', 409)
    }
    const old = previous.connection
    let connection = null
    let newRef
    if (body.action === 'save') {
      const config = normalizeConnection(body)
      const password = body.password
      if (typeof password !== 'string' || password.length > 2048 || forbidden.test(password) ||
          (password !== '' && (!password.trim() || password.trim() !== password))) {
        throw new SettingsError('password')
      }
      const targetChanged = !old || config.addresses !== old.addresses ||
        config.username !== old.username || config.tls !== old.tls
      if (!password && (targetChanged || !(await credentials.describe(old.passwordRef)).configured)) {
        throw new SettingsError(targetChanged && old ? 'new-password' : 'password')
      }
      if (password) {
        newRef = 'DSH_NEBULA_PASSWORD_' + randomUUID().replaceAll('-', '').toUpperCase()
        await credentials.set(newRef, password)
      }
      connection = { ...config, passwordRef: newRef ?? old.passwordRef }
    } else if (body.action !== 'clear') {
      throw new SettingsError('invalid')
    }
    let next
    try {
      next = await commit(previous, connection)
    } catch (error) {
      if (newRef) await credentials.unset(newRef)
      throw error
    }
    await reconcile(next)
    if (old && old.passwordRef !== connection?.passwordRef) {
      try {
        await credentials.unset(old.passwordRef)
      } catch {
        throw new SettingsError('cleanup', 500)
      }
    }
    return snapshot(next)
  }

  return {
    start: () => serialize(async () => {
      runtime = await findRuntime()
      await reconcile(await read())
    }),
    read: async () => snapshot(await read()),
    change: body => serialize(() => change(body)),
    dispose: () => {
      disposed = true
      return serialize(detach)
    },
  }
}

function reply(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    },
  })
}

async function readBody(request) {
  const stream = request.body?.getReader()
  if (!stream) throw new SettingsError('invalid')
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let size = 0
  let text = ''
  try {
    for (;;) {
      const { done, value } = await stream.read()
      if (done) break
      size += value.byteLength
      if (size > 16384) throw new SettingsError('invalid', 413)
      text += decoder.decode(value, { stream: true })
    }
    return JSON.parse(text + decoder.decode())
  } catch (error) {
    void stream.cancel().catch(() => {})
    throw error instanceof SettingsError ? error : new SettingsError('invalid')
  } finally {
    stream.releaseLock()
  }
}

export function registerRoute(connection, controller) {
  return connection.fetch.register({
    path: ROUTE,
    methods: ['GET', 'POST'],
    requestBody: 'streaming',
    async fetch(request) {
      // Exact Fetch routes run after owner admission but are only passed the Request.
      // Re-admit to distinguish the browser owner from a separate API peer.
      const { peer } = connection.admit(request)
      if (peer?.id !== connection.browserPeer.id || peer?.principal.kind !== 'owner') {
        return reply(403, { error: 'forbidden' })
      }
      try {
        if (request.method === 'GET') return reply(200, await controller.read())
        if (request.headers.get('x-dsh-nebula-settings') !== '1' ||
            request.headers.get('content-type')?.split(';')[0] !== 'application/json') {
          return reply(415, { error: 'invalid' })
        }
        const body = await readBody(request)
        if (request.signal.aborted) return reply(400, { error: 'invalid' })
        return reply(200, await controller.change(body))
      } catch (error) {
        return error instanceof SettingsError
          ? reply(error.status, { error: error.code })
          : reply(500, { error: 'store' })
      }
    },
  })
}

export function apply(ctx) {
  const controller = createController(ctx.credentials, ctx.mcpManager)
  ctx.effect(() => {
    const unroute = registerRoute(ctx.connection, controller)
    void controller.start().catch(() => ctx.logger?.warn('[nebula-dsh] Could not initialize settings'))
    return async () => {
      await unroute()
      await controller.dispose()
    }
  }, 'nebula-dsh: settings and MCP')
}
