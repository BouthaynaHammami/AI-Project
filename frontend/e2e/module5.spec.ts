import { expect, test, type APIRequestContext } from '@playwright/test'

<<<<<<< HEAD
const apiURL = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000'
const email = process.env.E2E_USER_EMAIL
const password = process.env.E2E_USER_PASSWORD
const analysisId = Number(process.env.E2E_ANALYSIS_ID)
let cachedHeaders: { Authorization: string } | undefined

test.beforeEach(async ({}, testInfo) => {
  test.skip(
    !email || !password || !Number.isInteger(analysisId),
    'Set E2E_USER_EMAIL, E2E_USER_PASSWORD, and E2E_ANALYSIS_ID for the isolated seeded fixture.',
  )
=======
const apiURL = 'http://127.0.0.1:18765'
const email = 'e2e-owner@example.com'
const password = 'E2E-Only-Password-123!'
const otherEmail = 'e2e-other@example.com'
const analysisId = 1
const shareToken = 'e2e-local-share-token'

test.beforeEach(async ({}, testInfo) => {
>>>>>>> 353023a (Fix profile updates and configure isolated E2E tests)
  testInfo.annotations.push({ type: 'fixture', description: 'Real FastAPI API and deterministic seeded analysis' })
})

async function authenticatedRequest(request: APIRequestContext) {
<<<<<<< HEAD
  if (cachedHeaders) return { headers: cachedHeaders }
  const login = await request.post(`${apiURL}/auth/login`, {
    data: { email, password },
  })
  expect(login.ok()).toBeTruthy()
=======
  const login = await request.post(`${apiURL}/auth/login`, { data: { email, password } })
  expect(login.ok(), `Login failed (${login.status()}): ${await login.text()}`).toBeTruthy()
>>>>>>> 353023a (Fix profile updates and configure isolated E2E tests)
  const token = (await login.json()).access_token as string
  cachedHeaders = { Authorization: `Bearer ${token}` }
  return { headers: { Authorization: `Bearer ${token}` } }
}

test.describe('Module 5 analysis lifecycle and exports', () => {
  test('history search, favorite, rename, open, delete and restore stay user-scoped', async ({ request }) => {
    const auth = await authenticatedRequest(request)
    const history = await request.get(`${apiURL}/analysis/history?q=total`, { headers: auth.headers })
    expect(history.ok()).toBeTruthy()
    expect((await history.json()).items).toEqual(expect.any(Array))

    const renamed = await request.patch(`${apiURL}/analysis/${analysisId}`, {
      headers: auth.headers,
      data: { title: 'Rapport E2E', is_favorite: true },
    })
    expect(renamed.ok()).toBeTruthy()
    expect((await renamed.json()).title).toBe('Rapport E2E')

    const favoriteHistory = await request.get(`${apiURL}/analysis/history?favorite=true`, { headers: auth.headers })
    expect((await favoriteHistory.json()).items.some((item: { id: number }) => item.id === analysisId)).toBe(true)

    const deleted = await request.delete(`${apiURL}/analysis/${analysisId}`, { headers: auth.headers })
    expect(deleted.status()).toBe(204)
    const restored = await request.post(`${apiURL}/analysis/${analysisId}/restore`, { headers: auth.headers })
    expect(restored.ok()).toBeTruthy()
  })

  test('exports XLSX and PDF with safe attachment names and rejects invalid formats', async ({ request }) => {
    const auth = await authenticatedRequest(request)
    for (const format of ['xlsx', 'pdf']) {
      const response = await request.get(`${apiURL}/analysis/${analysisId}/export?format=${format}`, { headers: auth.headers })
      expect(response.ok()).toBeTruthy()
      expect(response.headers()['content-disposition']).toMatch(/^attachment; filename="analyse-[a-z0-9-]+\.(xlsx|pdf)"$/)
    }
    const invalid = await request.get(`${apiURL}/analysis/${analysisId}/export?format=csv`, { headers: auth.headers })
    expect(invalid.status()).toBe(422)
  })

  test('feedback can be created, updated and deleted', async ({ request }) => {
    const auth = await authenticatedRequest(request)
    const positive = await request.put(`${apiURL}/analysis/${analysisId}/feedback`, {
      headers: auth.headers,
      data: { rating: 1, comment: 'Useful' },
    })
    expect(positive.ok()).toBeTruthy()
    const negative = await request.put(`${apiURL}/analysis/${analysisId}/feedback`, {
      headers: auth.headers,
      data: { rating: -1, comment: 'Needs detail' },
    })
    expect((await negative.json()).rating).toBe(-1)
    expect((await request.delete(`${apiURL}/analysis/${analysisId}/feedback`, { headers: auth.headers })).status()).toBe(204)
  })

  test('another authenticated user cannot read or mutate the analysis', async ({ request }) => {
<<<<<<< HEAD
    const otherEmail = `e2e-other-${Date.now()}@example.test`
    const signup = await request.post(`${apiURL}/auth/signup`, {
      data: { name: 'E2E Other', email: otherEmail, password: 'SecurePass123!' },
    })
    test.skip(signup.status() === 429, 'Signup rate limit reached; use a pre-seeded second user for this test.')
    test.skip(![200, 201, 202].includes(signup.status()), `Secondary-user setup returned HTTP ${signup.status()}.`)
    const login = await request.post(`${apiURL}/auth/login`, {
      data: { email: otherEmail, password },
      headers: { 'X-Auth-Email': `${otherEmail}-${Date.now()}` },
    })
    test.skip(!login.ok(), 'The isolated fixture must provide an auto-verified or verification-bypassed E2E environment.')
=======
    const login = await request.post(`${apiURL}/auth/login`, { data: { email: otherEmail, password } })
    expect(login.ok(), `Login failed (${login.status()}): ${await login.text()}`).toBeTruthy()
>>>>>>> 353023a (Fix profile updates and configure isolated E2E tests)
    const otherToken = (await login.json()).access_token as string
    const otherHeaders = { Authorization: `Bearer ${otherToken}` }
    expect((await request.get(`${apiURL}/analysis/${analysisId}/export?format=pdf`, { headers: otherHeaders })).status()).toBe(404)
    expect((await request.patch(`${apiURL}/analysis/${analysisId}`, { headers: otherHeaders, data: { title: 'Nope' } })).status()).toBe(404)
  })
})

test.describe('Module 5 public sharing', () => {
  test('supports every expiration period and single-link revocation', async ({ request }) => {
    const auth = await authenticatedRequest(request)
    const createdLinks: Array<{ id: number; token: string }> = []
    for (const expiresInDays of [1, 7, 30]) {
      const created = await request.post(`${apiURL}/analysis/${analysisId}/share`, {
        headers: auth.headers,
        data: { expires_in_days: expiresInDays },
      })
      expect(created.status()).toBe(201)
      createdLinks.push(await created.json())
    }
    for (const link of createdLinks) {
      expect((await request.get(`${apiURL}/public/analysis/${link.token}`)).ok()).toBeTruthy()
      expect((await request.delete(`${apiURL}/analysis/${analysisId}/share/${link.id}`, { headers: auth.headers })).status()).toBe(204)
      expect((await request.get(`${apiURL}/public/analysis/${link.token}`)).status()).toBe(404)
    }
    const remaining = await Promise.all([1, 7].map((expiresInDays) => request.post(`${apiURL}/analysis/${analysisId}/share`, {
      headers: auth.headers,
      data: { expires_in_days: expiresInDays },
    })))
    const remainingTokens = await Promise.all(remaining.map(async (response) => (await response.json()).token as string))
    expect((await request.delete(`${apiURL}/analysis/${analysisId}/share`, { headers: auth.headers })).status()).toBe(204)
    for (const token of remainingTokens) {
      expect((await request.get(`${apiURL}/public/analysis/${token}`)).status()).toBe(404)
    }
  })

  test('public URL works without authentication, survives refresh, and returns privacy headers', async ({ page, request }) => {
    const auth = await authenticatedRequest(request)
    const created = await request.post(`${apiURL}/analysis/${analysisId}/share`, {
      headers: auth.headers,
      data: { expires_in_days: 1 },
    })
    expect(created.status()).toBe(201)
    const shareToken = (await created.json()).token as string
    const response = await request.get(`${apiURL}/public/analysis/${encodeURIComponent(shareToken)}`)
    expect(response.ok()).toBeTruthy()
    expect(response.headers()['x-robots-tag']).toContain('noindex')
    expect(response.headers()['cache-control']).toContain('no-store')

    await page.goto(`/share/${encodeURIComponent(shareToken!)}`)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Réponse' })).toBeVisible()
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Réponse' })).toBeVisible()
  })

  test('expired, invalid, or revoked public links show the unavailable state', async ({ page }) => {
    await page.goto('/share/not-a-real-token')
    await expect(page.getByRole('heading', { name: 'Ce lien n’est plus disponible' })).toBeVisible()
  })
})
