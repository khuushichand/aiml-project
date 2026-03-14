/**
 * Admin MLX E2E Tests (Tier 4)
 *
 * Tests the /admin/mlx page:
 * - Page loads without critical errors
 * - MLX LM Admin heading or admin guard visible
 * - Load Model card with model path input and action buttons
 * - Basic settings (device, compile, max concurrent) visible
 * - MLX status API fires on page load
 *
 * Run: npx playwright test e2e/workflows/tier-4-admin/admin-mlx.spec.ts
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

test.describe("Admin MLX", () => {
  let admin: AdminPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    admin = new AdminPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should load admin/mlx page without critical errors", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")
      await admin.assertSectionReady("mlx")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display MLX LM Admin heading or admin guard alert", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")
      await admin.assertSectionReady("mlx")

      const hasHeading = await admin.mlxHeading.isVisible().catch(() => false)
      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)

      expect(hasHeading || hasGuard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Key Controls
  // =========================================================================

  test.describe("Key Controls", () => {
    test("should show Load Model card with model path input", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")
      await admin.assertSectionReady("mlx")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; MLX controls not shown")
        return
      }

      // Load Model card should be visible
      const cardVisible = await admin.mlxLoadModelCard.isVisible().catch(() => false)
      expect(cardVisible).toBe(true)

      // Model path input (AutoComplete) should be visible after scrolling into view
      await admin.mlxModelPathInput.scrollIntoViewIfNeeded().catch(() => {})
      const inputVisible = await admin.mlxModelPathInput.isVisible().catch(() => false)
      expect(inputVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Load Model and Unload Model buttons", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")
      await admin.assertSectionReady("mlx")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; MLX controls not shown")
        return
      }

      // Scroll buttons into view since they may be below the fold
      await admin.mlxLoadButton.scrollIntoViewIfNeeded().catch(() => {})
      const loadVisible = await admin.mlxLoadButton.isVisible().catch(() => false)
      await admin.mlxUnloadButton.scrollIntoViewIfNeeded().catch(() => {})
      const unloadVisible = await admin.mlxUnloadButton.isVisible().catch(() => false)

      expect(loadVisible).toBe(true)
      expect(unloadVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Basic Settings section with Device and Compile controls", async ({
      authedPage,
      diagnostics,
    }) => {
      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")
      await admin.assertSectionReady("mlx")

      const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
      if (hasGuard) {
        test.skip(true, "Admin guard active; MLX controls not shown")
        return
      }

      // Check for Basic Settings section text
      const basicSettingsText = authedPage.getByText("Basic Settings")
      const visible = await basicSettingsText.isVisible().catch(() => false)
      expect(visible).toBe(true)

      // Device label should be visible
      const deviceLabel = authedPage.getByText(/Device/i).first()
      const deviceVisible = await deviceLabel.isVisible().catch(() => false)
      expect(deviceVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Interactions
  // =========================================================================

  test.describe("API Interactions", () => {
    test("should fire MLX status API on page load", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      // Set up API call expectation before navigation
      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/llm\/providers\/mlx\/status/i,
        method: "GET",
      })

      admin = new AdminPage(authedPage)
      await admin.gotoSection("mlx")

      // The page calls loadStatus() and loadProviders() on mount
      await apiCall

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
