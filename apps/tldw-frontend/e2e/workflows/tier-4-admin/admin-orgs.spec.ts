/**
 * Admin Orgs E2E Tests (Tier 4)
 *
 * Tests the /admin/orgs page:
 * - Page loads without critical errors
 * - Organizations page heading renders
 * - Search and create controls are present
 * - Create Org opens the modal
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

    test("should display Organizations & Teams heading or admin guard alert", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertSectionReady("orgs")

      const hasHeading = await admin.orgsHeading.isVisible().catch(() => false)
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      expect(hasHeading || hasGuard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show org search and create controls when admin API is available", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertSectionReady("orgs")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      await expect(authedPage.getByRole("searchbox", { name: /search orgs/i })).toBeVisible()
      await expect(authedPage.getByRole("button", { name: /refresh/i })).toBeVisible()
      await expect(authedPage.getByRole("button", { name: /create org/i })).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should open the Create Organization modal", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertSectionReady("orgs")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      await authedPage.getByRole("button", { name: /create org/i }).click()
      await expect(
        authedPage.getByRole("dialog").getByText(/create organization/i)
      ).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should render the organizations table or empty state", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("orgs")
      await admin.assertSectionReady("orgs")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip()
        return
      }

      await expect(
        authedPage.getByRole("columnheader", { name: /name/i }).or(
          authedPage.getByText("No data", { exact: true })
        ).first()
      ).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
