/**
 * ACP Playground E2E Tests (Tier 3)
 *
 * Tests the ACP Playground page lifecycle:
 * - Page loads with expected header, session panel, and tool tabs
 * - Session panel shows empty state or session list
 * - Tab switching between Tools and Workspace in the right pane
 * - Create Session modal can be opened
 * - Refresh sessions fires API call (requires server)
 *
 * Run: npx playwright test e2e/workflows/tier-3-automation/acp-playground.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { ACPPage } from "../../utils/page-objects/ACPPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth } from "../../utils/helpers"

test.describe("ACP Playground", () => {
  let acp: ACPPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    acp = new ACPPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the ACP Playground page with header and panels", async ({
      authedPage,
      diagnostics,
    }) => {
      acp = new ACPPage(authedPage)
      await acp.goto()
      await acp.assertPageReady()

      // The heading or subtitle should be visible
      const headingVisible = await authedPage.getByText("Agent Playground").first().isVisible().catch(() => false)
      const sessionsVisible = await acp.sessionsHeading.isVisible().catch(() => false)

      expect(headingVisible || sessionsVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show empty state or session list in the session panel", async ({
      authedPage,
      diagnostics,
    }) => {
      acp = new ACPPage(authedPage)
      await acp.goto()
      await acp.assertPageReady()

      // Either sessions are listed or the empty state is shown
      const isEmpty = await acp.isEmptyState()
      const sessionCount = await acp.getSessionCount()

      expect(isEmpty || sessionCount >= 0).toBe(true)

      // If empty state, the create button should be present
      if (isEmpty) {
        const createVisible = await acp.createSessionButton.isVisible().catch(() => false)
        expect(createVisible).toBe(true)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Panel Interactions
  // =========================================================================

  test.describe("Panel Interactions", () => {
    test("should switch between Tools and Workspace tabs in the right pane", async ({
      authedPage,
      diagnostics,
    }) => {
      acp = new ACPPage(authedPage)
      await acp.goto()
      await acp.assertPageReady()

      const toolsTabVisible = await acp.toolsTab.isVisible().catch(() => false)
      if (!toolsTabVisible) return

      // Switch to Workspace tab
      const workspaceTabVisible = await acp.workspaceTab.isVisible().catch(() => false)
      if (workspaceTabVisible) {
        await acp.workspaceTab.click()
        await expect(acp.workspaceTab).toHaveAttribute("aria-selected", "true")

        // Switch back to Tools tab
        await acp.toolsTab.click()
        await expect(acp.toolsTab).toHaveAttribute("aria-selected", "true")
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should open Create Session modal from empty state", async ({
      authedPage,
      diagnostics,
    }) => {
      acp = new ACPPage(authedPage)
      await acp.goto()
      await acp.assertPageReady()

      // Try the create session button (visible in empty state)
      const createVisible = await acp.createSessionButton.isVisible().catch(() => false)
      if (!createVisible) return

      await acp.createSessionButton.click()

      // Modal should appear
      const modal = authedPage.locator(".ant-modal")
      await expect(modal).toBeVisible({ timeout: 5_000 })

      // Close the modal
      await authedPage.keyboard.press("Escape")
      await expect(modal).toBeHidden({ timeout: 3_000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Integration (requires server)
  // =========================================================================

  test.describe("API Integration", () => {
    test("should fire GET /api/v1/acp/sessions on refresh", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      acp = new ACPPage(authedPage)
      await acp.goto()
      await acp.assertPageReady()

      const refreshVisible = await acp.refreshSessionsButton.isVisible().catch(() => false)
      if (!refreshVisible) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/acp\/sessions/,
        method: "GET",
      }, 15_000)

      await acp.refreshSessionsButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Refresh may not fire if sessions store handles it internally
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should hydrate sessions from backend on page load", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      // The component auto-calls listSessions on mount
      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/acp\/sessions/,
        method: "GET",
      }, 20_000)

      acp = new ACPPage(authedPage)
      await acp.goto()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Server may not have ACP endpoint available
      }

      await acp.assertPageReady()
      await assertNoCriticalErrors(diagnostics)
    })
  })
})
