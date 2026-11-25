import { spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { ensureRuntime, inspectRuntime, MODULE } from './runtime.js'

export const name = 'nebula-dsh'
export const inject = ['credentials', 'mcpManager', 'connection']
export const SERVER = 'nebula_graph'
export const ROUTE = '/api/nebula-dsh/settings'
export const TEST_ROUTE = '/api/nebula-dsh/test'
const KEY = 'nebula-dsh/connection'
const PROBE = fileURLToPath(new URL('./probe.py', import.meta.url))
const TEST_TIMEOUT_MS = 20_000
const REF = /^DSH_NEBULA_PASSWORD_[0-9A-F]{32}$/
const CONNECTION_ID = /^(?:legacy|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$/
const MAX_CONNECTIONS = 20
const NO_CONNECTIONS = { revision: '', connections: [], activeId: null }
const DETACH_TIMEOUT_MS = 30_000
const forbidden = /[\u0000-\u001f\u007f]/u
const knownStates = new Set(['connecting', 'connected', 'reconnecting', 'failed', 'closed', 'waiting-credentials'])
const cleanupReasons = new Set(['cleanup', 'unclosed-generation'])
const nameKey = name => name.normalize('NFC').toLowerCase()
const sameTarget = (a, b) => a.addresses === b.addresses && a.username === b.username && a.tls === b.tls
const isCleanupFailure = status => (status?.state === 'failed' && cleanupReasons.has(status.reason)) ||
  (status?.state === 'closed' && (status.result?.closeConfirmed === false || status.result?.cleanupError !== undefined))

class SettingsError extends Error {
  constructor(code, status = 400) {
    super(code)
    this.code = code
    this.status = status
  }
}

function runProbe(python, connection, password) {
  return new Promise(resolve => {
    const environment = {
      PATH: process.env.PATH ?? '/usr/bin:/bin',
      HOME: process.env.HOME ?? '',
      LANG: process.env.LANG ?? 'C.UTF-8',
      TMPDIR: process.env.TMPDIR ?? '/tmp',
      NEBULA_ADDRESSES: connection.addresses,
      NEBULA_USERNAME: connection.username,
      NEBULA_PASSWORD: password,
      NEBULA_TLS_ENABLED: String(connection.tls),
    }
    const child = spawn(python, ['-I', PROBE], { env: environment, stdio: ['ignore', 'pipe', 'pipe'] })
    let output = ''
    let settled = false
    const finish = result => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      if (child.exitCode === null) child.kill('SIGKILL')
      resolve(result)
    }
    const timer = setTimeout(() => finish({ ok: false, code: 'timeout', message: '连接测试超时。' }), TEST_TIMEOUT_MS)
    child.on('error', () => finish({ ok: false, code: 'runtime', message: '无法启动连接测试。' }))
    child.stdout.setEncoding('utf8')
    child.stdout.on('data', chunk => { if (output.length < 16_384) output += chunk })
    // The probe never prints credentials; stderr is still discarded rather than surfaced.
    child.stderr.on('data', () => {})
    child.on('close', () => {
      const line = output.trim().split(/\r?\n/u).reverse().find(item => item.startsWith('{'))
      if (line === undefined) {
        finish({ ok: false, code: 'probe', message: '连接测试没有返回结果。' })
        return
      }
      let value
      try {
        value = JSON.parse(line)
      } catch {
        finish({ ok: false, code: 'probe', message: '连接测试返回了无效结果。' })
        return
      }
      if (value?.ok === true) {
        finish({ ok: true, version: typeof value.version === 'string' ? value.version : '' })
        return
      }
      finish({
        ok: false,
        code: typeof value?.code === 'string' ? value.code : 'connection',
        message: typeof value?.message === 'string' ? value.message.slice(0, 300) : '连接失败。',
      })
    })
  })
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
  if (typeof input.tls !== 'boolean') throw new SettingsError('invalid')
  return { addresses, username: input.username.trim(), tls: input.tls }
}

function normalizeName(value) {
  if (typeof value !== 'string' || value.length > 64 || forbidden.test(value) || !value.trim()) {
    throw new SettingsError('name')
  }
  return value.trim()
}

function decode(record) {
  if (!record) return NO_CONNECTIONS
  try {
    const doc = record.payload
    if (record.kind !== 'grant' || typeof doc?.revision !== 'string') throw new Error()
    const { revision } = doc
    if (!Object.hasOwn(doc, 'connections')) {
      if (doc.connection === null) return { revision, connections: [], activeId: null }
      const { enabled, passwordRef } = doc.connection ?? {}
      if (typeof enabled !== 'boolean' || typeof passwordRef !== 'string' || !REF.test(passwordRef)) throw new Error()
      const connection = { id: 'legacy', name: 'Default', ...normalizeConnection(doc.connection), passwordRef }
      return { revision, connections: [connection], activeId: enabled ? connection.id : null }
    }
    if (!Array.isArray(doc.connections) || doc.connections.length > MAX_CONNECTIONS) throw new Error()
    const ids = new Set(), names = new Set(), refs = new Set()
    const connections = doc.connections.map(input => {
      const { id, passwordRef } = input
      const name = normalizeName(input.name)
      const key = nameKey(name)
      if (typeof id !== 'string' || !CONNECTION_ID.test(id) || ids.has(id) || names.has(key) ||
          typeof passwordRef !== 'string' || !REF.test(passwordRef) || refs.has(passwordRef)) throw new Error()
      ids.add(id)
      names.add(key)
      refs.add(passwordRef)
      return { id, name, ...normalizeConnection(input), passwordRef }
    })
    if (doc.activeId !== null && !ids.has(doc.activeId)) throw new Error()
    return { revision, connections, activeId: doc.activeId }
  } catch {
    throw new SettingsError('store', 500)
  }
}

export function createController(credentials, manager, findRuntime = inspectRuntime) {
  let runtime = { state: 'checking' }
  let status = 'disabled'
  let registered
  let cleanupBlocked = false
  let queue = Promise.resolve()
  let disposed = false
  const serialize = task => {
    const next = queue.then(task)
    queue = next.catch(() => {})
    return next
  }
  const read = async () => decode(await credentials.readRecord(KEY))

  function observe(rows = manager.list()) {
    const row = rows.find(item => item.name === SERVER)
    if (isCleanupFailure(row?.status)) cleanupBlocked = true
    return row
  }

  async function detach() {
    const prior = registered
    if (!prior) return
    registered = undefined
    try {
      const settled = rows => {
        const row = observe(rows)
        return !row || (!row.configured && isCleanupFailure(row.status))
      }
      await prior.dispose()
      if (settled()) return
      // Some DSH builds return a void disposer while unmount runs on the manager's
      // queue. A retained row means cleanup is not confirmed, even if configured=false.
      for await (const rows of manager.watch(AbortSignal.timeout(DETACH_TIMEOUT_MS))) {
        if (settled(rows)) return
      }
      cleanupBlocked = true
    } catch {
      cleanupBlocked = true
    }
  }

  async function reconcile(doc, restart = false) {
    const config = doc.connections.find(connection => connection.id === doc.activeId)
    // The display name has no effect on the server; the profile id binds this registration
    // to the active profile even when another saved profile targets the same host.
    const identity = !disposed && config && runtime.state === 'ready' ? JSON.stringify([
      runtime.python, config.id, config.addresses, config.username, config.tls, config.passwordRef,
    ]) : null
    observe()
    if (cleanupBlocked || registered?.identity !== identity) await detach()
    if (cleanupBlocked) return
    if (!identity || disposed) {
      status = 'disabled'
      return
    }
    try {
      if (registered) {
        if (restart) {
          await manager.restart(SERVER)
          status = 'connecting'
        }
        return
      }
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
    // Explicit projection: no reference names, secrets, paths or provider diagnostics.
    const connections = await Promise.all(doc.connections.map(async ({ id, name, addresses, username, tls, passwordRef }) => ({
      id, name, addresses, username, tls,
      passwordSaved: (await credentials.describe(passwordRef)).configured,
    })))
    const slot = observe()?.status
    const live = registered && status !== 'registration-error' ? slot : undefined
    return {
      revision: doc.revision,
      connections,
      activeId: doc.activeId,
      runtime: { state: runtime.state, version: runtime.version },
      mcp: {
        state: cleanupBlocked ? 'host-restart-required' :
          knownStates.has(live?.state) ? live.state : status,
        ...(!cleanupBlocked && live?.state === 'connected' && { toolCount: live.toolCount }),
      },
    }
  }

  async function commit(previous, connections, activeId) {
    const next = { revision: randomUUID(), connections, activeId }
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
      // Never restart a target that changed after the settings card was displayed.
      if (body.revision !== undefined && body.revision !== previous.revision) throw new SettingsError('conflict', 409)
      runtime = await findRuntime()
      await reconcile(previous, true)
      return snapshot(previous)
    }
    if (typeof body?.revision !== 'string' || body.revision !== previous.revision) {
      throw new SettingsError('conflict', 409)
    }
    let { connections, activeId } = previous
    const action = body.action
    const needsId = action === 'clear' || action === 'activate' || (action === 'save' && body.id !== undefined)
    const old = connections.find(candidate => candidate.id === body.id)
    if (needsId && !old) throw new SettingsError('not-found', 404)
    let newRef
    let retiredRef
    let password
    if (action === 'save') {
      const name = normalizeName(body.name)
      if (!old && connections.length >= MAX_CONNECTIONS) throw new SettingsError('limit')
      if (connections.some(candidate => candidate !== old && nameKey(candidate.name) === nameKey(name))) {
        throw new SettingsError('duplicate-name')
      }
      const config = normalizeConnection(body)
      password = body.password
      if (typeof password !== 'string' || password.length > 2048 || forbidden.test(password) ||
          (password !== '' && (!password.trim() || password.trim() !== password))) {
        throw new SettingsError('password')
      }
      const targetChanged = old && !sameTarget(config, old)
      if (!password && (!old || targetChanged || !(await credentials.describe(old.passwordRef)).configured)) {
        throw new SettingsError(targetChanged ? 'new-password' : 'password')
      }
      if (password) {
        newRef = 'DSH_NEBULA_PASSWORD_' + randomUUID().replaceAll('-', '').toUpperCase()
        retiredRef = old?.passwordRef
      }
      const connection = { id: old?.id ?? randomUUID(), name, ...config, passwordRef: newRef ?? old.passwordRef }
      connections = old ? connections.map(candidate => candidate === old ? connection : candidate) : [...connections, connection]
    } else if (action === 'activate') {
      activeId = old.id
    } else if (action === 'deactivate') {
      activeId = null
    } else if (action === 'clear') {
      connections = connections.filter(candidate => candidate !== old)
      if (activeId === old.id) activeId = null
      retiredRef = old.passwordRef
    } else {
      throw new SettingsError('invalid')
    }
    let next
    try {
      if (newRef) await credentials.set(newRef, password)
      next = await commit(previous, connections, activeId)
    } catch (error) {
      if (newRef) await credentials.unset(newRef).catch(() => {})
      throw error
    }
    if (activeId !== previous.activeId || (newRef && old?.id === activeId)) await reconcile(next)
    if (retiredRef) {
      try {
        await credentials.unset(retiredRef)
      } catch {
        throw new SettingsError('cleanup', 500)
      }
    }
    return snapshot(next)
  }

  return {
    start: async () => {
      // Bootstrapping may download a portable Python and install the runtime.
      // Keep the settings API responsive while that happens; reconcile after.
      const current = await findRuntime()
      await serialize(async () => {
        runtime = current
        await reconcile(await read())
      })
    },
    read: () => serialize(async () => snapshot(await read())),
    change: body => serialize(() => change(body)),
    async test(connectionId) {
      if (disposed) throw new SettingsError('unavailable', 503)
      const doc = await read()
      const connection = doc.connections.find(row => row.id === connectionId)
      if (!connection) throw new SettingsError('not-found', 404)
      let current = runtime
      if (current.state !== 'ready') current = await findRuntime()
      if (current.state !== 'ready') {
        return { ok: false, code: 'runtime', message: 'Python 运行时未就绪。' }
      }
      const secret = await credentials.resolve(connection.passwordRef)
      if (secret === undefined) return { ok: false, code: 'password', message: '这条连接没有保存密码。' }
      const started = Date.now()
      const result = await runProbe(current.python, connection, secret.value)
      return result.ok ? { ok: true, version: result.version, latencyMs: Date.now() - started } : result
    },
    async testDraft(input) {
      if (disposed) throw new SettingsError('unavailable', 503)
      let config
      try {
        config = normalizeConnection(input)
      } catch (error) {
        if (error instanceof SettingsError) return { ok: false, code: error.code, message: '连接参数无效。' }
        throw error
      }
      const password = input?.password
      if (typeof password !== 'string' || password.length === 0 || password.length > 2048 ||
          forbidden.test(password) || password.trim() !== password) {
        return { ok: false, code: 'password', message: '请先填写有效密码。' }
      }
      let current = runtime
      if (current.state !== 'ready') current = await findRuntime()
      if (current.state !== 'ready') {
        return { ok: false, code: 'runtime', message: 'Python 运行时未就绪。' }
      }
      const started = Date.now()
      const result = await runProbe(current.python, config, password)
      return result.ok ? { ok: true, version: result.version, latencyMs: Date.now() - started } : result
    },
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

export function registerTestRoute(connection, controller) {
  return connection.fetch.register({
    path: TEST_ROUTE,
    methods: ['POST'],
    requestBody: 'buffered',
    async fetch(request) {
      const { peer } = connection.admit(request)
      if (peer?.id !== connection.browserPeer.id || peer?.principal.kind !== 'owner') {
        return reply(403, { error: 'forbidden' })
      }
      try {
        if (request.headers.get('x-dsh-nebula-settings') !== '1' ||
            request.headers.get('content-type')?.split(';')[0] !== 'application/json') {
          return reply(415, { error: 'invalid' })
        }
        const body = await readBody(request)
        if (typeof body?.id === 'string' && body.id.length > 0 && body.id.length <= 64) {
          return reply(200, await controller.test(body.id))
        }
        if (body?.draft !== null && body?.draft !== undefined && typeof body.draft === 'object' &&
            !Array.isArray(body.draft)) {
          return reply(200, await controller.testDraft(body.draft))
        }
        throw new SettingsError('invalid')
      } catch (error) {
        return error instanceof SettingsError ? reply(error.status, { error: error.code }) : reply(500, { error: 'test' })
      }
    },
  })
}

export function registerRoute(connection, controller) {
  return connection.fetch.register({
    path: ROUTE,
    methods: ['GET', 'POST'],
    requestBody: 'buffered',
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
  const controller = createController(ctx.credentials, ctx.mcpManager, () => ensureRuntime({
    log: message => ctx.logger?.info?.(`[nebula-dsh] ${message}`),
  }))
  ctx.effect(() => {
    const unrouteTest = registerTestRoute(ctx.connection, controller)
    const unroute = registerRoute(ctx.connection, controller)
    void controller.start().catch(() => ctx.logger?.warn('[nebula-dsh] Could not initialize settings'))
    return async () => {
      await unrouteTest()
      await unroute()
      await controller.dispose()
    }
  }, 'nebula-dsh: settings and MCP')
}
