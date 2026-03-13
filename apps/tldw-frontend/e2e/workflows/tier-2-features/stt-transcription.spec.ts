/**
 * STT (Speech-to-Text) Playground E2E Tests (Tier 2)
 *
 * Tests the STT Playground page lifecycle:
 * - Page loads with expected elements (heading, recording controls, panels)
 * - Settings toggle shows/hides inline settings panel
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/stt-transcription.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { STTPage } from "../../utils/page-objects/STTPage"
import { seedAuth } from "../../utils/helpers"

test.describe("STT Playground", () => {
  let sttPage: STTPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    sttPage = new STTPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the STT Playground page with heading and recording controls", async ({
      authedPage,
      diagnostics,
    }) => {
      sttPage = new STTPage(authedPage)
      await sttPage.goto()
      await sttPage.assertPageReady()

      // Heading and subtitle visible
      await expect(sttPage.heading).toBeVisible()
      await expect(sttPage.subtitle).toBeVisible()

      // Recording strip controls visible
      await expect(sttPage.recordButton).toBeVisible()
      await expect(sttPage.uploadButton).toBeVisible()
      await expect(sttPage.settingsToggleButton).toBeVisible()

      // Duration display visible (shows 00:00 initially)
      await expect(sttPage.durationDisplay).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should toggle settings panel when clicking settings button", async ({
      authedPage,
      diagnostics,
    }) => {
      sttPage = new STTPage(authedPage)
      await sttPage.goto()
      await sttPage.assertPageReady()

      // Settings panel should be hidden initially
      const languageLabel = authedPage.getByText(/language/i)
      const settingsInitiallyVisible = await languageLabel.first().isVisible().catch(() => false)

      // Toggle settings open
      await sttPage.settingsToggleButton.click()
      await authedPage.waitForTimeout(500)

      const settingsAfterClick = await languageLabel.first().isVisible().catch(() => false)

      // State should have changed
      expect(settingsInitiallyVisible).not.toEqual(settingsAfterClick)

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
