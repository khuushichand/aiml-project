import { test, expect, seedAuth } from './smoke.setup'

const LOAD_TIMEOUT = 30_000

test.use({
  viewport: { width: 375, height: 812 }
})

test.describe('Stage 4 mobile sidebar behavior', () => {
  test('chat sidebar is hidden by default on mobile and opens via header toggle', async ({
    page
  }) => {
    await seedAuth(page)

    await page.goto('/chat', {
      waitUntil: 'domcontentloaded',
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState('networkidle', { timeout: LOAD_TIMEOUT }).catch(() => {})

    const headerToggle = page.getByTestId('chat-header-sidebar-toggle')
    await expect(headerToggle).toBeVisible({ timeout: LOAD_TIMEOUT })
    await expect(headerToggle).toHaveAccessibleName(/expand sidebar/i)
    await expect(page.getByTestId('chat-sidebar-toggle')).toHaveCount(0)

    const sidebar = page.getByTestId('chat-sidebar')
    await expect(sidebar).toHaveCount(0)

    await headerToggle.click()

    await expect(sidebar).toBeVisible({ timeout: LOAD_TIMEOUT })
    await expect(headerToggle).toHaveAccessibleName(/collapse sidebar/i)

    const drawer = page.locator('.ant-drawer').filter({ has: sidebar })
    await drawer.getByRole('button', { name: /close/i }).first().click()

    await expect(headerToggle).toHaveAccessibleName(/expand sidebar/i)
  })
})
