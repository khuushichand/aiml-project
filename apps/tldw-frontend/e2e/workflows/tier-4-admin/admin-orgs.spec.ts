/**
 * Admin Orgs E2E Tests (Tier 4)
 *
 * Tests the /admin/orgs page:
 * - Page loads without critical errors
 * - Placeholder panel visible with "Coming Soon" text
 * - Title shows "Organization Management Is Coming Soon"
 * - Primary CTA links to /admin/server
 * - Open Settings link visible
 *
 * Note: /admin/orgs is a placeholder page (RoutePlaceholder), not yet implemented.
 *
 * Run: npx playwright test e2e/workflows/tier-4-admin/admin-orgs.spec.ts
 */
import {
  test,
  expect,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { AdminPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Admin Orgs", () => {
  let admin: AdminPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    admin = new AdminPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should load admin/orgs page without critical errors", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertSectionReady("orgs")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display placeholder panel with Coming Soon text", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertPlaceholderVisible()

      // "Coming Soon" text should be visible
      const comingSoon = admin.comingSoonText
      await expect(comingSoon).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Organization Management title", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertPlaceholderVisible()

      const title = authedPage.getByText("Organization Management Is Coming Soon")
      await expect(title).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should show primary CTA linking to Server Admin", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertPlaceholderVisible()

      const primaryCta = admin.primaryCta
      await expect(primaryCta).toBeVisible({ timeout: 10_000 })
      await expect(primaryCta).toHaveText(/Open Server Admin/i)

      // Verify it links to /admin/server
      const href = await primaryCta.getAttribute("href")
      expect(href).toBe("/admin/server")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Open Settings and Go back buttons", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertPlaceholderVisible()

      const settingsLink = admin.openSettingsLink
      await expect(settingsLink).toBeVisible({ timeout: 10_000 })

      const goBackBtn = admin.goBackButton
      await expect(goBackBtn).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Navigation
  // =========================================================================

  test.describe("Navigation", () => {
    test("should navigate to /admin/server when primary CTA is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertPlaceholderVisible()

      await admin.primaryCta.click()
      await expect(authedPage).toHaveURL(/\/admin\/server/, { timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
