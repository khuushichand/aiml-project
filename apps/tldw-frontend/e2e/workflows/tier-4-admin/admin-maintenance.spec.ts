import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { AdminPage } from "../../utils/page-objects"
import { waitForConnection } from "../../utils/helpers"

test.describe("Admin Maintenance", () => {
  let admin: AdminPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    admin = new AdminPage(authedPage)
  })

  async function gotoMaintenance(page: import("@playwright/test").Page): Promise<void> {
    await page.goto("/admin/maintenance", { waitUntil: "domcontentloaded" })
    await waitForConnection(page)
  }

  test("maintenance page loads and shows console heading or admin guard", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)

    await expect(
      admin.maintenanceHeading.or(admin.adminGuardAlert).first()
    ).toBeVisible({ timeout: 15_000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("maintenance page shows maintenance mode controls", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)
    await expect(
      admin.maintenanceHeading.or(admin.adminGuardAlert).first()
    ).toBeVisible({ timeout: 15_000 })

    const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
    if (hasGuard) {
      test.skip()
      return
    }

    await expect(
      authedPage.getByText("Maintenance Mode", { exact: true }).first()
    ).toBeVisible()
    await expect(authedPage.getByRole("switch")).toBeVisible()
    await expect(
      authedPage.getByPlaceholder(/maintenance message displayed to users/i)
    ).toBeVisible()
    await expect(authedPage.getByRole("button", { name: /save changes/i })).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("maintenance page shows incident management controls", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)
    await expect(
      admin.maintenanceHeading.or(admin.adminGuardAlert).first()
    ).toBeVisible({ timeout: 15_000 })

    const hasGuard = await admin.adminGuardAlert.isVisible().catch(() => false)
    if (hasGuard) {
      test.skip()
      return
    }

    await expect(authedPage.getByText("Incidents")).toBeVisible()
    await expect(authedPage.getByPlaceholder(/incident title/i)).toBeVisible()
    await expect(authedPage.getByRole("button", { name: /create incident/i })).toBeVisible()
    await expect(authedPage.getByRole("button", { name: /^refresh$/i })).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})
