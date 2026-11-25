import { execFile, spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { constants } from 'node:fs'
import { access, lstat, mkdir, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { isAbsolute, join, relative, resolve } from 'node:path'
import { promisify } from 'node:util'

export const MODULE = 'nebula_mcp.dsh_stdio'
const versionPattern = /^\d+\.\d+\.\d+(?:[.a-z0-9]+)?(?:\+[a-z0-9]+(?:\.[a-z0-9]+)*)?$/i

export function dataRoot(env = process.env, platform = process.platform, home = homedir()) {
  if (platform === 'darwin') return join(home, 'Library', 'Application Support', 'nebula-mcp')
  if (platform === 'win32') {
    if (!env.LOCALAPPDATA || !isAbsolute(env.LOCALAPPDATA)) return undefined
    return join(env.LOCALAPPDATA, 'nebula-mcp')
  }
  const data = env.XDG_DATA_HOME || join(home, '.local', 'share')
  return join(resolve(data.replace(/^~(?=\/|$)/, home)), 'nebula-mcp')
}

export async function hasModule(python, moduleName, run = promisify(execFile)) {
  try {
    await run(python, ['-I', '-c', `import ${moduleName}`], {
      timeout: 6000,
      maxBuffer: 4096,
      windowsHide: true,
    })
    return true
  } catch {
    return false
  }
}

export async function inspectRuntime(root = dataRoot(), run = promisify(execFile)) {
  if (!root) return { state: 'missing' }
  let manifest
  let expected
  try {
    const rootInfo = await lstat(root)
    if (!rootInfo.isDirectory()) return { state: 'invalid' }
    const path = join(root, 'state.json')
    const stateInfo = await lstat(path)
    if (!stateInfo.isFile() || stateInfo.size > 4096) return { state: 'invalid' }
    manifest = JSON.parse(await readFile(path, 'utf8'))
    if (manifest?.schema_version !== 1 || typeof manifest.version !== 'string' ||
        !versionPattern.test(manifest.version) || typeof manifest.python !== 'string' ||
        !isAbsolute(manifest.python)) return { state: 'invalid' }
    const venv = join(root, 'versions', manifest.version, 'venv')
    const bin = join(venv, process.platform === 'win32' ? 'Scripts' : 'bin')
    expected = join(bin, process.platform === 'win32' ? 'python.exe' : 'python')
    if (await realpath(expected) !== await realpath(manifest.python) ||
        relative(join(await realpath(root), 'versions', manifest.version, 'venv',
          process.platform === 'win32' ? 'Scripts' : 'bin'), await realpath(bin)) !== '' ||
        !(await stat(expected)).isFile()) return { state: 'invalid' }
    await access(expected, constants.X_OK)
  } catch (error) {
    return { state: error?.code === 'ENOENT' && !manifest ? 'missing' : 'invalid' }
  }
  try {
    const { stdout } = await run(expected, ['-I', '-m', MODULE, '--version'], {
      cwd: root,
      timeout: 6000,
      maxBuffer: 4096,
      windowsHide: true,
    })
    if (stdout.trim() === `nebula-mcp-dsh ${manifest.version}`) {
      return { state: 'ready', python: expected, version: manifest.version }
    }
  } catch {
    // Never pass subprocess output (which may be sensitive) to the browser.
  }
  return { state: 'unsupported', version: manifest.version }
}


const INSTALLER = {
  version: '0.7.0+build.202611260045',
  url: 'https://github.com/MuYiYong/nebula-mcp/releases/download/v26.11.26_Build0045/install.py',
  sha256: '1b6f98af53250d7c78da2717494ae6bd0f8a45d434f5c2cc976ace488790b8be',
}

// Relocatable CPython distributions used only when no managed runtime exists yet.
// They are not hardened with a Team ID, so pip-installed native extensions
// (pydantic_core) load normally, unlike the DSH-bundled hardened Python.
const PORTABLE = {
  'darwin-arm64': {
    name: 'cpython-3.12.16+20261124-aarch64-apple-darwin-install_only.tar.gz',
    sha256: '431b99a9c2cdd37ad9b06e425be0e520d2dbce0552abe454257abef592fe3634',
    url: 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-aarch64-apple-darwin-install_only.tar.gz',
  },
  'darwin-x64': {
    name: 'cpython-3.12.16+20261124-x86_64-apple-darwin-install_only.tar.gz',
    sha256: 'ccce24cfd3f56f62561d2c9480fcc567ca3a9bac68450cd73e11aeb631befa1f',
    url: 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-x86_64-apple-darwin-install_only.tar.gz',
  },
  'linux-x64': {
    name: 'cpython-3.12.16+20261124-x86_64-unknown-linux-gnu-install_only.tar.gz',
    sha256: '6774c7f49ee21c1723f7ac91961a5bf9f3ee3ae6e4d82ff58bd358958b546461',
    url: 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-x86_64-unknown-linux-gnu-install_only.tar.gz',
  },
  'linux-arm64': {
    name: 'cpython-3.12.16+20261124-aarch64-unknown-linux-gnu-install_only.tar.gz',
    sha256: '2e6b3576f96d5b8861e4c265ea6db3d19eb24027bbd6c22f044544989444b20b',
    url: 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-aarch64-unknown-linux-gnu-install_only.tar.gz',
  },
  'win32-x64': {
    name: 'cpython-3.12.16+20261124-x86_64-pc-windows-msvc-install_only.tar.gz',
    sha256: '8152ff5b6c6c044ddbbaa3531dda59cb9ce5bd6cb670d4c9ac2e3ab91afa8778',
    url: 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.12.16%2B20261124-x86_64-pc-windows-msvc-install_only.tar.gz',
  },
}

let pending

/** Idempotently provision the managed runtime from a portable CPython + the release installer. */
export async function ensureRuntime(options = {}) {
  const root = options.root ?? dataRoot(options.env, options.platform, options.home)
  if (!root) return { state: 'missing' }
  const current = await inspectRuntime(root)
  if (current.state === 'ready' &&
      (!options.requiredModule || await hasModule(current.python, options.requiredModule))) {
    return current
  }
  if (pending) return pending
  const cache = options.cache ?? bootstrapCache(options.env, options.platform, options.home)
  pending = bootstrap(root, cache, options).then(async state => {
    if (state.state === 'ready' && options.requiredModule &&
        !(await hasModule(state.python, options.requiredModule))) {
      options.log?.(`Runtime ${state.version} is missing ${options.requiredModule}`)
      return { state: 'unsupported', version: state.version }
    }
    return state
  }).finally(() => { pending = undefined })
  return pending
}

export function bootstrapCache(env = process.env, platform = process.platform, home = homedir()) {
  if (platform === 'darwin') return join(home, 'Library', 'Caches', 'nebula-mcp-bootstrap')
  if (platform === 'win32') return join(env.LOCALAPPDATA || join(home, 'AppData', 'Local'), 'nebula-mcp-bootstrap')
  return join(env.XDG_CACHE_HOME || join(home, '.cache'), 'nebula-mcp-bootstrap')
}

async function bootstrap(root, cache, options) {
  const platform = options.platform ?? process.platform
  const arch = options.arch ?? process.arch
  const asset = PORTABLE[`${platform}-${arch}`]
  const log = options.log
  if (!asset) {
    log?.(`No portable Python runtime for ${platform}-${arch}`)
    return inspectRuntime(root)
  }
  const env = { ...process.env, ...(options.env ?? {}) }
  try {
    log?.('Preparing portable Python runtime')
    const python = await preparePython(cache, asset, log, platform)
    log?.('Downloading the runtime installer')
    const installer = await prepareInstaller(cache, log)
    log?.('Installing the NebulaGraph runtime (first use may take a minute)')
    await runInstaller(cache, python, installer, env, log)
    const state = await inspectRuntime(root)
    if (state.state !== 'ready') log?.(`Runtime installation did not become ready: ${state.state}`)
    return state
  } catch (error) {
    log?.(`Runtime bootstrap failed: ${error?.message ?? String(error)}`)
    return inspectRuntime(root)
  }
}

async function preparePython(cache, asset, log, platform) {
  await mkdir(cache, { recursive: true })
  const archive = join(cache, asset.name)
  if (!(await exists(archive))) await download(asset.url, archive, asset.sha256, log)
  const target = join(cache, asset.name.replace(/\.tar\.gz$/, ''))
  const python = platform === 'win32'
    ? join(target, 'python', 'python.exe')
    : join(target, 'python', 'bin', 'python3')
  if (!(await exists(python))) {
    await rm(target, { recursive: true, force: true })
    await mkdir(target, { recursive: true })
    await extract(archive, target)
  }
  await access(python, constants.X_OK)
  return python
}

async function prepareInstaller(cache, log) {
  await mkdir(cache, { recursive: true })
  const installer = join(cache, `install-${INSTALLER.version}.py`)
  try {
    const cached = await readFile(installer)
    if (createHash('sha256').update(cached).digest('hex') === INSTALLER.sha256) return installer
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error
  }
  await download(INSTALLER.url, installer, INSTALLER.sha256, log)
  return installer
}

async function download(url, target, expected, log) {
  log?.(`Downloading ${url}`)
  const response = await fetch(url, { redirect: 'follow', signal: AbortSignal.timeout(10 * 60_000) })
  if (!response.ok) throw new Error(`download failed with HTTP ${response.status}`)
  const bytes = Buffer.from(await response.arrayBuffer())
  const digest = createHash('sha256').update(bytes).digest('hex')
  if (digest !== expected) throw new Error('download checksum mismatch')
  await writeFile(target, bytes, { mode: 0o600 })
}

async function extract(archive, target) {
  await new Promise((resolve, reject) => {
    const child = spawn('tar', ['-xzf', archive, '-C', target], {
      stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true,
    })
    let error = ''
    child.stderr.on('data', chunk => { if (error.length < 4000) error += String(chunk) })
    const timer = setTimeout(() => {
      child.kill('SIGKILL')
      reject(new Error('tar timed out'))
    }, 120_000)
    child.on('error', failure => { clearTimeout(timer); reject(failure) })
    child.on('close', code => {
      clearTimeout(timer)
      if (code === 0) resolve()
      else reject(new Error(error.trim() || `tar exited with ${code}`))
    })
  })
}

async function runInstaller(cwd, python, installer, env, log) {
  await new Promise((resolve, reject) => {
    const child = spawn(python, [installer, '--mode', 'runtime', '--yes'], {
      cwd, env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    })
    let output = ''
    const collect = chunk => {
      const text = String(chunk)
      output = (output + text).slice(-8000)
      for (const line of text.split(/\r?\n/)) if (line.trim()) log?.(line.trim())
    }
    child.stdout.on('data', collect)
    child.stderr.on('data', collect)
    const timer = setTimeout(() => {
      child.kill('SIGKILL')
      reject(new Error('runtime installer timed out'))
    }, 15 * 60_000)
    child.on('error', failure => { clearTimeout(timer); reject(failure) })
    child.on('close', code => {
      clearTimeout(timer)
      if (code === 0) resolve()
      else reject(new Error(output.trim().slice(-2000) || `installer exited with ${code}`))
    })
  })
}

async function exists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}
