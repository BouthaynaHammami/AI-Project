import { expect, test } from '@playwright/test'

const email = process.env.E2E_USER_EMAIL
const password = process.env.E2E_USER_PASSWORD

test('user can log in', async ({ page }) => {
  test.skip(!email || !password, 'Set E2E_USER_EMAIL and E2E_USER_PASSWORD.')

  await page.goto('/')
  await page.getByRole('button', { name: 'Log In' }).click()
  await page.getByLabel('Email professionnel').fill(email!)
  await page.locator('input[type="password"]').fill(password!)
  await page.getByRole('button', { name: 'Se connecter' }).click()

  await expect(page.getByText(/^Bonjour,/)).toBeVisible()
})
