#!/usr/bin/env node
/**
 * Codex plugin launcher for nebula-mcp.
 *
 * Codex installs plugins from a Git marketplace but does not run install
 * scripts. This launcher reuses the same managed runtime as the DeepSeek
 * Harness bundle: if the runtime is missing it prepares a portable Python in
 * the background and then starts the stdio MCP server from that runtime.
 *
 * stdout belongs to the MCP protocol; all diagnostics go to stderr.
 */
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { mkdir, open, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { bootstrapCache, dataRoot, ensureRuntime, inspectRuntime } from './runtime.mjs'

const PREFIX = '[nebula-mcp]'
const FIRST_START_WAIT_MS = 25_000
const PREPARE_TIMEOUT_MS = 15 * 60_000
const LOCK_STALE_MS = 30 * 60_000

function note(message) {
  process.stderr.write(`${PREFIX} ${message}\n`)
}

async function main() {
  const args = process.argv.slice(2)
  if (args.includes('--help') || args.includes('-h')) {
    process.stderr.write(
      'Usage: launch.mjs [--prepare]\n' +
      '  (default)  ensure the runtime, then start the MCP stdio server\n' +
      '  --prepare  ensure the runtime only; used for background preparation\n',
    )
    return 0
  }

  const root = dataRoot()
  if (!root) {
    note('cannot locate a writable data directory for the managed runtime')
    return 1
  }

  if (args.includes('--prepare')) {
    const state = await prepare(root)
    return state.state === 'ready' ? 0 : 1
  }

  let state = await inspectRuntime(root)
  if (state.state !== 'ready') {
    const cache = bootstrapCache()
    await startBackgroundPrepare(cache)
    state = await waitForRuntime(root, FIRST_START_WAIT_MS)
    if (state.state !== 'ready') {
      note(`runtime is still being prepared; retry shortly (log: ${join(cache, 'bootstrap.log')})`)
      return 1
    }
  }
  return runServer(state)
}

async function prepare(root) {
  const cache = bootstrapCache()
  await mkdir(cache, { recursive: true })
  const lock = await acquireLock(cache, root)
  if (!lock) return inspectRuntime(root)
  try {
    return await ensureRuntime({ root, log: note })
  } finally {
    await rm(lock, { recursive: true, force: true })
  }
}

async function startBackgroundPrepare(cache) {
  await mkdir(cache, { recursive: true })
  const logPath = join(cache, 'bootstrap.log')
  const handle = await open(logPath, 'a', 0o600)
  try {
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--prepare'], {
      detached: true,
      stdio: ['ignore', handle.fd, handle.fd],
      windowsHide: true,
      env: process.env,
    })
    child.on('error', error => note(`could not start the runtime preparation: ${error.message}`))
    child.unref()
  } finally {
    await handle.close()
  }
}

async function waitForRuntime(root, timeout) {
  const deadline = Date.now() + timeout
  for (;;) {
    const state = await inspectRuntime(root)
    if (state.state === 'ready' || Date.now() >= deadline) return state
    await new Promise(resolve => setTimeout(resolve, 1_000))
  }
}

async function acquireLock(cache, root) {
  const lock = join(cache, 'bootstrap.lock')
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await mkdir(lock)
      await writeFile(join(lock, 'owner.json'), JSON.stringify({
        pid: process.pid,
        startedAt: Date.now(),
      }))
      return lock
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error
      if (await isStaleLock(lock)) {
        await rm(lock, { recursive: true, force: true })
        continue
      }
      const state = await waitForRuntime(root, PREPARE_TIMEOUT_MS)
      if (state.state === 'ready') return undefined
      if (await isStaleLock(lock)) {
        await rm(lock, { recursive: true, force: true })
        continue
      }
      note('another process is still preparing the runtime; giving up for now')
      return undefined
    }
  }
  return undefined
}

async function isStaleLock(lock) {
  try {
    const info = await stat(lock)
    if (Date.now() - info.mtimeMs > LOCK_STALE_MS) return true
    const owner = JSON.parse(await readFile(join(lock, 'owner.json'), 'utf8'))
    return typeof owner?.pid === 'number' && !isAlive(owner.pid)
  } catch {
    return true
  }
}

function isAlive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return error?.code === 'EPERM'
  }
}

function runServer(state) {
  const child = spawn(state.python, ['-I', '-m', 'nebula_mcp'], {
    stdio: 'inherit',
    env: process.env,
    cwd: process.cwd(),
    windowsHide: true,
  })
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(signal, () => {
      try {
        child.kill(signal)
      } catch {
        // The child may already be gone.
      }
    })
  }
  child.on('error', error => {
    note(`could not start the MCP server: ${error.message}`)
    process.exitCode = 1
  })
  child.on('exit', (code, signal) => {
    if (signal) {
      process.removeAllListeners(signal)
      try {
        process.kill(process.pid, signal)
      } catch {
        process.exit(1)
      }
      return
    }
    process.exit(code ?? 0)
  })
  return undefined
}

main().then(code => {
  if (code !== undefined) process.exit(code)
}).catch(error => {
  note(`launcher failed: ${error?.message ?? String(error)}`)
  process.exit(1)
})
