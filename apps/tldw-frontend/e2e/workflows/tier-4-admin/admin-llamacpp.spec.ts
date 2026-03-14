/**
 * Admin Llama.cpp E2E Tests (Tier 4)
 *
 * Tests the /admin/llamacpp page:
 * - Page loads without critical errors
 * - Llama.cpp Admin heading or admin guard visible
 * - Load Model card with model select and start buttons
 * - Export/Import preset buttons visible
 * - Start Server button fires llamacpp start API call
 *
 * Run: npx playwright test e2e/workflows/tier-4-admin/admin-llamacpp.spec.ts
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

test.describe("Admin Llama.cpp", () => {
  let admin: AdminPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    admin = new AdminPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should load admin/llamacpp page without critical errors", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("llamacpp")
      await admin.assertSectionReady("llamacpp")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display Llama.cpp Admin heading or admin guard alert", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("llamacpp")
      await admin.assertSectionReady("llamacpp")

      const hasHeading = await admin.llamacppHeading.isVisible().catch(() => false)
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)

      expect(hasHeading || hasGuard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should show Load Model card with model select and action buttons", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("llamacpp")
      await admin.assertSectionReady("llamacpp")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; llamacpp controls not shown")
        return
      }

      // Load Model card should be visible
      const loadCard = admin.llamacppLoadModelCard
      const cardVisible = await loadCard.isVisible().catch(() => false)
      expect(cardVisible).toBe(true)

      // Start Server and Start with Defaults buttons should exist
      const startBtnVisible = await admin.llamacppStartButton.isVisible().catch(() => false)
      const startDefaultsBtnVisible = await admin.llamacppStartDefaultsButton
        .isVisible()
        .catch(() => false)
      expect(startBtnVisible || startDefaultsBtnVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Export and Import preset buttons", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("llamacpp")
      await admin.assertSectionReady("llamacpp")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; llamacpp controls not shown")
        return
      }

      const exportVisible = await admin.llamacppExportPresetButton
        .isVisible()
        .catch(() => false)
      const importVisible = await admin.llamacppImportPresetButton
        .isVisible()
        .catch(() => false)

      expect(exportVisible).toBe(true)
      expect(importVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Interactions
  // =========================================================================

  test.describe("API Interactions", () => {
    test("should fire llamacpp status API on page load", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      // Set up the API call expectation before navigation
      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/(admin\/)?llamacpp\/(status|models)/i,
        method: "GET",
      })

      admin = new AdminPage(authedPage)
      await admin.gotoSection("llamacpp")

      // The page calls loadStatus() and loadModels() on mount
      await apiCall

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
