/**
 * Admin Data Ops E2E Tests (Tier 4)
 *
 * Tests the /admin/data-ops page:
 * - Page loads without critical errors
 * - Data Operations heading renders
 * - Backups controls are present
 * - Tab navigation works across the workspace
 *
 * Run: npx playwright test e2e/workflows/tier-4-admin/admin-data-ops.spec.ts
 */
import {
  test,
  expect,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { AdminPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Admin Data Ops", () => {
  let admin: AdminPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    admin = new AdminPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should load admin/data-ops page without critical errors", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("data-ops")
      await admin.assertSectionReady("data-ops")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display Data Operations heading or admin guard alert", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("data-ops")
      await admin.assertSectionReady("data-ops")

      const hasHeading = await admin.dataOpsHeading.isVisible().catch(() => false)
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      expect(hasHeading || hasGuard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show backup controls when admin API is available", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("data-ops")
      await admin.assertSectionReady("data-ops")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      await expect(authedPage.getByRole("tab", { name: /backups/i })).toBeVisible()
      await expect(authedPage.getByRole("button", { name: /create backup/i })).toBeVisible()
      await expect(authedPage.getByRole("button", { name: /refresh/i }).first()).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should show all data-ops tabs", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("data-ops")
      await admin.assertSectionReady("data-ops")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      await expect(authedPage.getByRole("tab", { name: /backups/i })).toBeVisible()
      await expect(authedPage.getByRole("tab", { name: /data subject requests/i })).toBeVisible()
      await expect(authedPage.getByRole("tab", { name: /retention policies/i })).toBeVisible()
      await expect(authedPage.getByRole("tab", { name: /bundles/i })).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch to the Data Subject Requests tab", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("data-ops")
      await admin.assertSectionReady("data-ops")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      const dsrTab = authedPage.getByRole("tab", { name: /data subject requests/i })
      await dsrTab.click()
      await expect(dsrTab).toHaveAttribute("aria-selected", "true")

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
