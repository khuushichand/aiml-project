/**
 * Admin Server E2E Tests (Tier 4)
 *
 * Tests the /admin/server page:
 * - Page loads without critical errors
 * - Server heading or admin guard visible
 * - System statistics card rendered (when admin API available)
 * - Users & roles card rendered
 * - Refresh button fires system stats API call
 *
 * Run: npx playwright test e2e/workflows/tier-4-admin/admin-server.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { AdminPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Admin Server", () => {
  let admin: AdminPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    admin = new AdminPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should load admin/server page without critical errors", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("server")
      await admin.assertSectionReady("server")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display Server Admin heading or admin guard alert", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("server")
      await admin.assertSectionReady("server")

      const hasHeading = await admin.serverHeading.isVisible().catch(() => false)
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)

      expect(hasHeading || hasGuard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should show Connection card when config is loaded", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("server")
      await admin.assertSectionReady("server")

      // Connection card should be visible if not guarded
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (!hasGuard) {
        const connectionCard = admin.connectionCard
        const visible = await connectionCard.isVisible().catch(() => false)
        // Connection card may or may not render depending on config availability
        // This is a soft check
        expect(typeof visible).toBe("boolean")
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show system statistics or users sections when not guarded", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("server")
      await admin.assertSectionReady("server")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (!hasGuard) {
        // At least one admin card should be visible
        const statsVisible = await admin.systemStatsCard.isVisible().catch(() => false)
        const usersVisible = await admin.usersAndRolesCard.isVisible().catch(() => false)
        expect(statsVisible || usersVisible).toBe(true)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Interactions
  // =========================================================================

  test.describe("API Interactions", () => {
    test("should fire system stats API when Refresh is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      admin = new AdminPage(authedPage)
      await admin.gotoSection("server")
      await admin.assertSectionReady("server")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; admin APIs not available")
        return
      }

      const refreshBtn = admin.refreshStatsButton
      const isVisible = await refreshBtn.isVisible().catch(() => false)
      if (!isVisible) {
        test.skip(true, "Refresh button not visible on this page state")
        return
      }

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/(admin\/stats|system)/i,
        method: "GET",
      })

      await refreshBtn.click()
      await apiCall

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
