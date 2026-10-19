import { defineConfig, devices } from '@playwright/test'

const testEmail = 'e2e-owner@example.com'
const testPassword = 'E2E-Only-Password-123!'
const testShareToken = 'e2e-local-share-token'
const testApiUrl = 'http://127.0.0.1:18765'
const testFrontendUrl = 'http://127.0.0.1:18766'
process.env.E2E_USER_EMAIL = testEmail
process.env.E2E_USER_PASSWORD = testPassword
process.env.E2E_OTHER_USER_EMAIL = 'e2e-other@example.com'
process.env.E2E_ANALYSIS_ID = '1'
process.env.E2E_SHARE_TOKEN = testShareToken
process.env.E2E_API_URL = testApiUrl
process.env.E2E_PORT = '18765'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: testFrontendUrl,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'node e2e/start-backend.mjs',
      url: `${testApiUrl}/docs`,
      reuseExistingServer: false,
      env: {
        E2E_USER_EMAIL: process.env.E2E_USER_EMAIL,
        E2E_USER_PASSWORD: process.env.E2E_USER_PASSWORD,
        E2E_OTHER_USER_EMAIL: process.env.E2E_OTHER_USER_EMAIL,
        E2E_ANALYSIS_ID: process.env.E2E_ANALYSIS_ID,
        E2E_SHARE_TOKEN: process.env.E2E_SHARE_TOKEN,
        E2E_API_URL: process.env.E2E_API_URL,
        E2E_PORT: process.env.E2E_PORT,
        FRONTEND_ORIGIN: testFrontendUrl,
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 18766 --strictPort',
      url: testFrontendUrl,
      reuseExistingServer: false,
      env: { VITE_API_URL: testApiUrl },
    },
  ],
})
