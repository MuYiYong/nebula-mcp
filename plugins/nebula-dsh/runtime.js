import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { access, lstat, readFile, realpath, stat } from 'node:fs/promises'
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
    if (relative(expected, manifest.python) !== '' ||
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
