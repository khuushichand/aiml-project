import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
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

  test("maintenance page loads and shows placeholder", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)

    // The maintenance page is a RoutePlaceholder — verify its panel renders
    await admin.assertPlaceholderVisible()

    // Verify "Coming Soon" label is present
    await expect(authedPage.getByText("Coming Soon", { exact: true })).toBeVisible()

    // Verify the title text
    await expect(
      authedPage.getByRole("heading", { name: /maintenance console is coming soon/i })
    ).toBeVisible()

    // Verify the description
    await expect(
      authedPage.getByText(/advanced maintenance tooling/i)
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("maintenance page shows planned route", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)
    await admin.assertPlaceholderVisible()

    // Verify the planned path is displayed (appears in both Requested and Planned route)
    await expect(authedPage.getByText("/admin/maintenance").first()).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("primary CTA links to Server Admin", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)
    await admin.assertPlaceholderVisible()

    const primaryCta = authedPage.getByTestId("route-placeholder-primary")
    await expect(primaryCta).toBeVisible()
    await expect(primaryCta).toHaveText("Open Server Admin")

    // Verify the href points to /admin/server
    await expect(primaryCta).toHaveAttribute("href", "/admin/server")

    await assertNoCriticalErrors(diagnostics)
  })

  test("Open Settings link is present", async ({ authedPage, diagnostics }) => {
    await gotoMaintenance(authedPage)
    await admin.assertPlaceholderVisible()

    const settingsLink = authedPage.getByTestId("route-placeholder-open-settings")
    await expect(settingsLink).toBeVisible()
    await expect(settingsLink).toHaveAttribute("href", "/settings")

    await assertNoCriticalErrors(diagnostics)
  })

  test("Go back button is present and clickable", async ({ authedPage, diagnostics }) => {
    // Navigate to a known page first so "back" has somewhere to go
    await authedPage.goto("/settings", { waitUntil: "domcontentloaded" })
    await gotoMaintenance(authedPage)
    await admin.assertPlaceholderVisible()

    const goBackBtn = authedPage.getByTestId("route-placeholder-go-back")
    await expect(goBackBtn).toBeVisible()
    await expect(goBackBtn).toHaveText("Go back")

    await assertNoCriticalErrors(diagnostics)
  })
})
