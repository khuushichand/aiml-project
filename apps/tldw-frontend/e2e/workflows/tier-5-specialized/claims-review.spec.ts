/**
 * Claims Review E2E Tests (Tier 5)
 *
 * Tests the /claims-review page:
 * - Route redirects to /content-review (RouteRedirect component)
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/claims-review.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("Claims Review", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("redirects from /claims-review to /content-review", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/claims-review", {
      waitUntil: "domcontentloaded",
    })

    const redirectPanel = authedPage.getByTestId("route-redirect-panel")
    const contentReviewHeading = authedPage.getByRole("heading", {
      name: /content review/i,
    })

    await expect(
      redirectPanel.or(contentReviewHeading).first()
    ).toBeVisible({ timeout: 15_000 })

    const panelVisible = await redirectPanel.isVisible().catch(() => false)
    if (panelVisible) {
      await expect(
        authedPage.getByTestId("route-redirect-open-updated-page")
      ).toHaveAttribute("href", "/content-review")
    } else {
      await expect(contentReviewHeading).toBeVisible()
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
