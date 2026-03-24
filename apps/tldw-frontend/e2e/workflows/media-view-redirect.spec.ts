import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"

test.describe("Media View Redirect", () => {
  test.beforeEach(async ({ serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("media view redirect shows a redirect panel or lands on the media workspace", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/media/123/view", { waitUntil: "domcontentloaded" })

    const redirectPanel = authedPage.getByTestId("route-redirect-panel")
    const openUpdatedPage = authedPage.getByTestId("route-redirect-open-updated-page")
    const mediaResultsList = authedPage.getByTestId("media-review-results-list")
    const mediaResultsHeading = authedPage.getByRole("heading", { name: /^results/i }).first()

    await expect(
      redirectPanel.or(mediaResultsList).or(mediaResultsHeading).first()
    ).toBeVisible({ timeout: 20_000 })

    const panelVisible = await redirectPanel.isVisible().catch(() => false)
    if (panelVisible) {
      await expect(openUpdatedPage).toHaveAttribute("href", "/media")
    } else {
      await expect(mediaResultsList.or(mediaResultsHeading).first()).toBeVisible()
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
