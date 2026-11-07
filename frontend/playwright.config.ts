/**
 * Browser tests that run the real API and site together.
 *
 * They use their own ports, so they never clash with anything already running
 * on 8000 or 5173. Prediction logging is off, so tests don't fill the real log.
 */
import { defineConfig, devices } from '@playwright/test'

const API_PORT = process.env.E2E_API_PORT ?? '8011'
const SITE_PORT = process.env.E2E_SITE_PORT ?? '5174'

function withEnv(extra: Record<string, string>) {
  const inherited = Object.entries(process.env).filter(
    (entry): entry is [string, string] => entry[1] !== undefined,
  )
  return { ...Object.fromEntries(inherited), ...extra }
}

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${SITE_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop-dark',
      use: { viewport: { width: 1280, height: 800 }, colorScheme: 'dark' },
    },
    {
      name: 'phone-light',
      use: { ...devices['Pixel 7'], colorScheme: 'light' },
    },
  ],
  webServer: [
    {
      command: `uv run uvicorn api.main:app --port ${API_PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: withEnv({ SHOPSENSE_LOG_PREDICTIONS: 'false' }),
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite --port ${SITE_PORT} --strictPort`,
      url: `http://localhost:${SITE_PORT}`,
      env: withEnv({ SHOPSENSE_API_URL: `http://127.0.0.1:${API_PORT}` }),
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
