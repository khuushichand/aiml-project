import { test, expect } from '@playwright/test'
import { launchWithBuiltExtension } from './utils/extension-build'
import {
  waitForConnectionStore,
  forceConnected
} from './utils/connection'

async function dismissWelcomeOverlay(page: import('@playwright/test').Page) {
  const welcomeHeading = page.getByText(/Welcome to tldw Assistant/i).first()
  const appeared = await welcomeHeading
    .waitFor({ state: 'visible', timeout: 3_000 })
    .then(() => true)
    .catch(() => false)
  if (!appeared) return

  const dialog = page.locator('[role="dialog"]').filter({ has: welcomeHeading }).first()
  const closeButton = dialog.getByRole('button', { name: /close/i }).first()
  if (await closeButton.isVisible().catch(() => false)) {
    await closeButton.click()
  } else {
    await page.keyboard.press('Escape').catch(() => undefined)
  }
  await welcomeHeading.waitFor({ state: 'hidden', timeout: 8_000 }).catch(() => undefined)
}

test.describe('Knowledge RAG workspace UX', () => {
  test('workflow hub "Do Research" opens Knowledge QA route', async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await waitForConnectionStore(page, 'knowledge-rag-workflow-entry')
    await forceConnected(
      page,
      { serverUrl: 'http://dummy-tldw' },
      'knowledge-rag-workflow-entry'
    )

    await page.goto(optionsUrl + '#/settings/manageKnowledge')
    await page.waitForLoadState('networkidle')

    const workflowDialog = page
      .locator('[role="dialog"]')
      .filter({ has: page.getByText(/What would you like to do/i).first() })
      .first()
    const dialogAlreadyOpen = await workflowDialog.isVisible().catch(() => false)
    if (!dialogAlreadyOpen) {
      const workflowButton = page.getByTestId('workflow-button').first()
      await expect(workflowButton).toBeVisible()
      await workflowButton.click()
    }

    await expect(workflowDialog).toBeVisible()
    await workflowDialog.getByRole('button', { name: /Do Research/i }).click()

    await expect
      .poll(() => page.url(), { timeout: 15_000 })
      .toContain('#/knowledge')
    await expect(page.getByText(/Knowledge QA|Knowledge search & chat/i)).toBeVisible()

    await context.close()
  })

  test('shows RAG workspace and (when available) allows toggling per-reply RAG', async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    // Pretend the server is connected so the Knowledge workspace renders
    await waitForConnectionStore(page, 'knowledge-rag-connected')
    await forceConnected(
      page,
      { serverUrl: 'http://dummy-tldw' },
      'knowledge-rag-connected'
    )

    await page.goto(optionsUrl + '#/settings/knowledge')
    await page.waitForLoadState('networkidle')
    await dismissWelcomeOverlay(page)

    // Knowledge workspace header should be present with de-jargoned title
    await expect(
      page.getByText(/Knowledge search & chat/i)
    ).toBeVisible()
    await expect(
      page.getByText(/Retrieval-augmented generation \(RAG\) lets the assistant ground answers/i)
    ).toBeVisible()

    // If the bundled OpenAPI spec does not advertise RAG endpoints,
    // the workspace shows a capability callout instead of full controls.
    const ragUnsupportedCallout = page.getByText(
      /RAG search is not available on this server/i
    )
    const calloutVisible = await ragUnsupportedCallout
      .isVisible()
      .catch(() => false)

    if (!calloutVisible) {
      // Auto-RAG toggle should be visible and wired to chatMode
      const autoRagSwitch = page.getByRole('switch', {
        name: /Use RAG for every reply/i
      })
      await expect(autoRagSwitch).toBeVisible()

      const initialMode = await page.evaluate(() => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const store = (window as any).__tldw_useStoreMessageOption
        return store ? store.getState().chatMode : null
      })
      expect(initialMode).toBe('normal')

      await autoRagSwitch.click()

      const ragMode = await page.evaluate(() => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const store = (window as any).__tldw_useStoreMessageOption
        return store ? store.getState().chatMode : null
      })
      expect(ragMode).toBe('rag')

      await autoRagSwitch.click()

      const backMode = await page.evaluate(() => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const store = (window as any).__tldw_useStoreMessageOption
        return store ? store.getState().chatMode : null
      })
      expect(backMode).toBe('normal')
    } else {
      // When RAG is unsupported, we at least show a Diagnostics CTA
      await expect(
        page.getByRole('button', { name: /Health & diagnostics/i })
      ).toBeVisible()
    }

    await context.close()
  })
})
