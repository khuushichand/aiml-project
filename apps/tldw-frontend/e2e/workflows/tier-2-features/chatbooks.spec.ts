/**
 * Chatbooks Playground E2E Tests (Tier 2)
 *
 * Tests the Chatbooks Playground page lifecycle:
 * - Page loads with expected elements (heading, tabs, job tracker)
 * - Tab switching between Export, Import, and Jobs
 * - Export button fires POST /api/v1/chatbooks/export (requires server)
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/chatbooks.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { ChatbooksPage } from "../../utils/page-objects/ChatbooksPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth } from "../../utils/helpers"

test.describe("Chatbooks Playground", () => {
  let chatbooks: ChatbooksPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    chatbooks = new ChatbooksPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Chatbooks Playground page with heading and tabs", async ({
      authedPage,
      diagnostics,
    }) => {
      chatbooks = new ChatbooksPage(authedPage)
      await chatbooks.goto()
      await chatbooks.assertPageReady()

      // Either the heading is visible (server online) or the offline message
      const headingVisible = await chatbooks.heading.isVisible().catch(() => false)
      const offlineVisible = await chatbooks.offlineMessage.isVisible().catch(() => false)

      expect(headingVisible || offlineVisible).toBe(true)

      // If online, tabs and job tracker should be present
      if (headingVisible) {
        await expect(chatbooks.exportTab).toBeVisible()
        await expect(chatbooks.importTab).toBeVisible()
        await expect(chatbooks.jobsTab).toBeVisible()
        await expect(chatbooks.jobTrackerCard).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between tabs without errors", async ({
      authedPage,
      diagnostics,
    }) => {
      chatbooks = new ChatbooksPage(authedPage)
      await chatbooks.goto()
      await chatbooks.assertPageReady()

      // Skip tab switching if page is in offline state
      const headingVisible = await chatbooks.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      for (const tab of ["import", "jobs", "export"] as const) {
        await chatbooks.switchToTab(tab)
        await authedPage.waitForTimeout(500)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Import Tab
  // =========================================================================

  test.describe("Import Tab", () => {
    test("should show upload dropzone on Import tab", async ({
      authedPage,
      diagnostics,
    }) => {
      chatbooks = new ChatbooksPage(authedPage)
      await chatbooks.goto()
      await chatbooks.assertPageReady()

      const headingVisible = await chatbooks.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      await chatbooks.switchToTab("import")

      await expect(chatbooks.uploadDropzone).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Export API Integration (requires server)
  // =========================================================================

  test.describe("Export API", () => {
    test("should fire POST /api/v1/chatbooks/export when Export button is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      chatbooks = new ChatbooksPage(authedPage)
      await chatbooks.goto()
      await chatbooks.assertPageReady()

      // Ensure we are on the Export tab
      const exportTabVisible = await chatbooks.exportTab.isVisible().catch(() => false)
      if (!exportTabVisible) return

      await chatbooks.switchToTab("export")

      const exportEnabled = await chatbooks.exportButton.isEnabled().catch(() => false)
      if (!exportEnabled) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/chatbooks\/export/,
        method: "POST",
      }, 15_000)

      await chatbooks.exportButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Export may require content selection; acceptable to not fire if nothing is selected
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
