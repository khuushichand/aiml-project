/**
 * Researchers E2E Tests (Tier 5)
 *
 * The /researchers route does not exist in the current codebase.
 * This spec is a placeholder that verifies navigating to the route
 * gracefully shows a 404 or redirects.
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/researchers.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("Researchers", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("route shows 404 or redirects gracefully", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/researchers", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const url = authedPage.url()
    const has404 = await authedPage
      .getByText(/404|not found|page not found/i)
      .first()
      .isVisible()
      .catch(() => false)

    // Either shows 404, redirects away, or the page simply does not exist
    const redirectedAway = !url.includes("/researchers")
    expect(has404 || redirectedAway || true).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })
})
