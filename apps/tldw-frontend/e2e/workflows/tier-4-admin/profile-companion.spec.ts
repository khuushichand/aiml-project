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

  test("companion page shows a visible loading or home state instead of a blank content area", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/companion", { waitUntil: "domcontentloaded" })

    const loadingPanel = authedPage.getByTestId("companion-route-loading")
    const companionShell = authedPage.getByTestId("companion-home-shell")
    const companionPage = authedPage.getByTestId("companion-home-page")

    await expect
      .poll(async () => {
        if (await loadingPanel.isVisible().catch(() => false)) return "loading"
        if (await companionShell.isVisible().catch(() => false)) return "shell"
        if (await companionPage.isVisible().catch(() => false)) return "page"
        return "blank"
      })
      .not.toBe("blank")

    await assertNoCriticalErrors(diagnostics)
  })

  test("companion page eventually renders the companion home quick actions", async ({ authedPage, diagnostics }) => {
    await authedPage.goto("/companion", { waitUntil: "domcontentloaded" })

    await expect(authedPage.getByTestId("companion-home-shell")).toBeVisible({
      timeout: 20_000,
    })
    await expect(authedPage.getByRole("heading", { name: "Quick actions" })).toBeVisible()
    await expect(authedPage.getByRole("link", { name: "Open Chat" })).toBeVisible()
    await expect(authedPage.getByRole("link", { name: "Open Knowledge" })).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})
