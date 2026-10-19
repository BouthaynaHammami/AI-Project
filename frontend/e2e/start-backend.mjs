import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendDirectory = path.resolve(frontendDirectory, '..', 'backend')
const pythonCandidates = process.platform === 'win32'
  ? ['.venv-test/Scripts/python.exe', 'venv/Scripts/python.exe', '.venv/Scripts/python.exe']
  : ['.venv-test/bin/python', 'venv/bin/python', '.venv/bin/python']
const pythonPath = process.env.E2E_PYTHON
  ? path.resolve(backendDirectory, process.env.E2E_PYTHON)
  : pythonCandidates
      .map((candidate) => path.join(backendDirectory, candidate))
      .find((candidate) => spawnSync(candidate, ['--version'], { stdio: 'ignore' }).status === 0)

if (!pythonPath) {
  throw new Error('Python virtual environment not found. Set E2E_PYTHON or create backend\\.venv-test.')
}

const databaseDirectory = mkdtempSync(path.join(tmpdir(), 'ai-project-playwright-'))
const databasePath = path.join(databaseDirectory, 'e2e.sqlite3')
const databaseUrl = `sqlite:///${databasePath.replaceAll('\\', '/')}`
const environment = {
  ...process.env,
  DATABASE_URL: databaseUrl,
  ENV: 'dev',
  JWT_SECRET_KEY: 'playwright-local-test-secret-key-not-for-production',
  E2E_TEST_DATABASE: '1',
}

function runPython(args) {
  const result = spawnSync(pythonPath, args, {
    cwd: backendDirectory,
    env: environment,
    stdio: 'inherit',
  })
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`Python command failed with exit code ${result.status}`)
  }
}

let server
let shuttingDown = false

function cleanup(exitCode = 0) {
  if (shuttingDown) return
  shuttingDown = true
  if (server && server.exitCode === null) server.kill()
  rmSync(databaseDirectory, { recursive: true, force: true })
  process.exit(exitCode)
}

try {
  runPython(['scripts/seed_e2e.py'])
  server = spawn(pythonPath, [
    '-m',
    'uvicorn',
    'app.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    process.env.E2E_PORT ?? '18765',
  ], {
    cwd: backendDirectory,
    env: environment,
    stdio: 'inherit',
  })
  server.on('error', (error) => {
    console.error(error)
    cleanup(1)
  })
  server.on('exit', (code) => cleanup(code ?? 1))
  process.on('SIGINT', () => cleanup())
  process.on('SIGTERM', () => cleanup())
} catch (error) {
  rmSync(databaseDirectory, { recursive: true, force: true })
  throw error
}
