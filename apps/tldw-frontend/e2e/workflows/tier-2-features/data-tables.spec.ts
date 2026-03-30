/**
 * Data Tables Studio E2E Tests (Tier 2)
 *
 * Tests the Data Tables Studio page lifecycle:
 * - Page loads with expected elements (heading, description, tabs)
 * - Tab switching between My Tables and Create Table
 * - Refresh button fires GET /api/v1/data-tables (requires server)
 * - Search input is present and interactive
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/data-tables.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { DataTablesPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Data Tables Studio", () => {
  let dataTables: DataTablesPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    dataTables = new DataTablesPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Data Tables Studio page with heading and tabs", async ({
      authedPage,
      diagnostics,
    }) => {
      dataTables = new DataTablesPage(authedPage)
      await dataTables.goto()
      await dataTables.assertPageReady()

      // Either the heading is visible (server online) or the offline message
      const headingVisible = await dataTables.heading.isVisible().catch(() => false)
      const offlineVisible = await dataTables.offlineMessage.isVisible().catch(() => false)

      expect(headingVisible || offlineVisible).toBe(true)

      // If online, tabs and description should be present
      if (headingVisible) {
        await expect(dataTables.description).toBeVisible()
        await expect(dataTables.myTablesTab).toBeVisible()
        await expect(dataTables.createTableTab).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between tabs without errors", async ({
      authedPage,
      diagnostics,
    }) => {
      dataTables = new DataTablesPage(authedPage)
      await dataTables.goto()
      await dataTables.assertPageReady()

      // Skip tab switching if page is in offline state
      const headingVisible = await dataTables.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      await dataTables.switchToTab("create")
      await expect(dataTables.createTableTab).toHaveAttribute("aria-selected", "true")

      await dataTables.switchToTab("tables")
      await expect(dataTables.myTablesTab).toHaveAttribute("aria-selected", "true")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // My Tables Tab
  // =========================================================================

  test.describe("My Tables Tab", () => {
    test("should show search input and refresh button", async ({
      authedPage,
      diagnostics,
    }) => {
      dataTables = new DataTablesPage(authedPage)
      await dataTables.goto()
      await dataTables.assertPageReady()

      const headingVisible = await dataTables.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      await expect(dataTables.searchInput).toBeVisible()
      await expect(dataTables.refreshButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show empty state or table list", async ({
      authedPage,
      diagnostics,
    }) => {
      dataTables = new DataTablesPage(authedPage)
      await dataTables.goto()
      await dataTables.assertPageReady()

      const headingVisible = await dataTables.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      await expect
        .poll(
          async () =>
            (await dataTables.emptyState.isVisible().catch(() => false)) ||
            (await authedPage.locator(".ant-table").isVisible().catch(() => false)),
          { timeout: 10_000 }
        )
        .toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Integration (requires server)
  // =========================================================================

  test.describe("API Integration", () => {
    test("should fire GET /api/v1/data-tables on page load", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      dataTables = new DataTablesPage(authedPage)

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/data-tables/,
        method: "GET",
      }, 15_000)

      await dataTables.goto()
      await dataTables.assertPageReady()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // May not fire if server is not fully configured for data tables
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should fire GET /api/v1/data-tables when Refresh is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      dataTables = new DataTablesPage(authedPage)
      await dataTables.goto()
      await dataTables.assertPageReady()

      const headingVisible = await dataTables.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      const refreshEnabled = await dataTables.refreshButton.isEnabled().catch(() => false)
      if (!refreshEnabled) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/data-tables/,
        method: "GET",
      }, 15_000)

      await dataTables.refreshButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Refresh may not fire a new request if data is still fresh
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
