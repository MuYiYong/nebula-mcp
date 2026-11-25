import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { dataRoot, inspectRuntime } from '../runtime.js'

const version = '0.6.0+build.202611251234'
const moduleName = 'nebula_mcp.dsh_stdio'

async function tempRoot(t) {
  const root = await mkdtemp(join(tmpdir(), 'nebula-dsh-runtime-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  return root
}

function interpreterPath(root) {
  return join(root, 'versions', version, 'venv', ...(
    process.platform === 'win32' ? ['Scripts', 'python.exe'] : ['bin', 'python']
  ))
}

async function installFixture(root) {
  const python = interpreterPath(root)
  await mkdir(dirname(python), { recursive: true })
  await writeFile(python, '', { mode: 0o700 })
  const manifest = { schema_version: 1, version, python }
  const state = join(root, 'state.json')
  await writeFile(state, JSON.stringify(manifest))
  return { manifest, python, state }
}

function noProbe() {
  // inspectRuntime catches probe failures, so assert the call count outside the probe.
  let calls = 0
  return {
    run: () => { calls += 1 },
    assertUnused: () => assert.equal(calls, 0),
  }
}

test('data root uses the installer convention for each platform', () => {
  const home = join(tmpdir(), 'runtime-home')
  const custom = join(home, 'custom')
  assert.equal(dataRoot({ XDG_DATA_HOME: custom }, 'darwin', home),
    join(home, 'Library', 'Application Support', 'nebula-mcp'))
  assert.equal(dataRoot({}, 'linux', home), join(home, '.local', 'share', 'nebula-mcp'))
  assert.equal(dataRoot({ XDG_DATA_HOME: custom }, 'linux', home), join(custom, 'nebula-mcp'))
  assert.equal(dataRoot({ XDG_DATA_HOME: '~/custom' }, 'linux', home), join(custom, 'nebula-mcp'))
  assert.equal(dataRoot({ LOCALAPPDATA: custom }, 'win32', home), join(custom, 'nebula-mcp'))
  assert.equal(dataRoot({ LOCALAPPDATA: 'relative' }, 'win32', home), undefined)
})

test('finds an installed calendar-version runtime and only probes the restricted module', async t => {
  const root = await tempRoot(t)
  const { python } = await installFixture(root)
  const probes = []
  const runtime = await inspectRuntime(root, async (...args) => {
    probes.push(args)
    return { stdout: `nebula-mcp-dsh ${version}\n` }
  })

  assert.deepEqual(runtime, { state: 'ready', python, version })
  assert.deepEqual(probes, [[python, ['-I', '-m', moduleName, '--version'], {
    cwd: root, timeout: 6000, maxBuffer: 4096, windowsHide: true,
  }]])
})

test('rejects missing or invalid installer state before probing Python', async t => {
  const root = await tempRoot(t)
  const probe = noProbe()
  assert.deepEqual(await inspectRuntime(join(root, 'missing'), probe.run), { state: 'missing' })
  assert.deepEqual(await inspectRuntime(root, probe.run), { state: 'missing' })

  const { manifest, state, python } = await installFixture(root)
  const external = join(root, 'other-python')
  await writeFile(external, '', { mode: 0o700 })
  for (const contents of [
    '{',
    ' '.repeat(4097),
    JSON.stringify({ ...manifest, schema_version: 2 }),
    JSON.stringify({ ...manifest, version: '../outside' }),
    JSON.stringify({ ...manifest, python: external }),
  ]) {
    await writeFile(state, contents)
    assert.deepEqual(await inspectRuntime(root, probe.run), { state: 'invalid' })
  }
  await writeFile(state, JSON.stringify(manifest))
  await rm(python)
  assert.deepEqual(await inspectRuntime(root, probe.run), { state: 'invalid' })
  probe.assertUnused()
})

test('rejects a symlinked runtime bin directory', { skip: process.platform === 'win32' }, async t => {
  const root = await tempRoot(t)
  const outside = await tempRoot(t)
  const python = interpreterPath(root)
  const bin = dirname(python)
  await mkdir(dirname(bin), { recursive: true })
  await writeFile(join(outside, 'python'), '', { mode: 0o700 })
  await symlink(outside, bin, 'dir')
  await writeFile(join(root, 'state.json'), JSON.stringify({ schema_version: 1, version, python }))

  const probe = noProbe()
  assert.deepEqual(await inspectRuntime(root, probe.run), { state: 'invalid' })
  probe.assertUnused()
})

test('suppresses details when the restricted module probe fails or has a mismatched version', async t => {
  const root = await tempRoot(t)
  await installFixture(root)
  const unsupported = { state: 'unsupported', version }
  assert.deepEqual(await inspectRuntime(root, async () => ({ stdout: 'nebula-mcp-dsh 0.1.0\n' })), unsupported)
  assert.deepEqual(await inspectRuntime(root, async () => {
    throw new Error('private interpreter path and stderr')
  }), unsupported)
})