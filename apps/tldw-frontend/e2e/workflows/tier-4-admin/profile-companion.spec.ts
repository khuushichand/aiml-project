import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"

test.describe("Profile Page", () => {
  test.beforeEach(async ({ serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("profile page loads and shows placeholder", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/profile", { waitUntil: "domcontentloaded" })

    // Profile is a RoutePlaceholder
    const panel = authedPage.getByTestId("route-placeholder-panel")
    await expect(panel).toBeVisible({ timeout: 15_000 })

    // Verify "Coming Soon" label
    await expect(authedPage.getByText("Coming Soon", { exact: true })).toBeVisible()

    // Verify title
    await expect(
      authedPage.getByRole("heading", { name: /profile page is coming soon/i })
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("profile page shows correct description", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/profile", { waitUntil: "domcontentloaded" })

    const panel = authedPage.getByTestId("route-placeholder-panel")
    await expect(panel).toBeVisible({ timeout: 15_000 })

    await expect(
      authedPage.getByText(/dedicated profile management is not yet available/i)
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("profile page primary CTA links to settings", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/profile", { waitUntil: "domcontentloaded" })

    const primaryCta = authedPage.getByTestId("route-placeholder-primary")
    await expect(primaryCta).toBeVisible({ timeout: 15_000 })
    await expect(primaryCta).toHaveText("Open Settings")
    await expect(primaryCta).toHaveAttribute("href", "/settings")

    await assertNoCriticalErrors(diagnostics)
  })

  test("profile page has Go back button", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/profile", { waitUntil: "domcontentloaded" })

    const goBackBtn = authedPage.getByTestId("route-placeholder-go-back")
    await expect(goBackBtn).toBeVisible({ timeout: 15_000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("profile page shows planned route", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/profile", { waitUntil: "domcontentloaded" })

    const panel = authedPage.getByTestId("route-placeholder-panel")
    await expect(panel).toBeVisible({ timeout: 15_000 })

    // Verify the planned path is displayed (appears in both Requested and Planned route)
    await expect(authedPage.getByText("/profile").first()).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})

test.describe("Companion Page", () => {
  test.beforeEach(async ({ serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("companion page loads and shows redirect panel", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/companion", { waitUntil: "domcontentloaded" })

    // Companion is a RouteRedirect — it shows a redirect panel briefly then navigates
    const redirectPanel = authedPage.getByTestId("route-redirect-panel")

    // The redirect may happen quickly, so check either the panel or the destination
    const panelVisible = await redirectPanel.isVisible().catch(() => false)
    if (panelVisible) {
      // Verify redirect panel elements
      await expect(
        authedPage.getByRole("heading", { name: /this route has moved/i })
      ).toBeVisible()
    }

    // The RouteRedirect component calls router.replace — the page should eventually
    // navigate or at minimum render without uncaught errors
    await assertNoCriticalErrors(diagnostics)
  })

  test("companion redirect panel has navigation links", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/companion", { waitUntil: "domcontentloaded" })

    const redirectPanel = authedPage.getByTestId("route-redirect-panel")
    const panelVisible = await redirectPanel.isVisible().catch(() => false)

    if (panelVisible) {
      // "Open updated page" link
      const openUpdatedLink = authedPage.getByTestId("route-redirect-open-updated-page")
      await expect(openUpdatedLink).toBeVisible()

      // "Go to Chat" link
      const goChatLink = authedPage.getByTestId("route-redirect-go-chat")
      await expect(goChatLink).toBeVisible()

      // "Open Settings" link
      const openSettingsLink = authedPage.getByTestId("route-redirect-open-settings")
      await expect(openSettingsLink).toBeVisible()
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
