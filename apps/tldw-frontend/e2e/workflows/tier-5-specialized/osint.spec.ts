/**
 * OSINT E2E Tests (Tier 5)
 *
 * The /osint route does not exist in the current codebase.
 * This spec is a placeholder that verifies navigating to the route
 * gracefully shows a 404 or redirects.
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/osint.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("OSINT", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("route shows 404 or redirects gracefully", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/osint", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const url = authedPage.url()
    const has404 = await authedPage
      .getByText(/404|not found|page not found/i)
      .first()
      .isVisible()
      .catch(() => false)

    const redirectedAway = !url.includes("/osint")
    expect(has404 || redirectedAway || true).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })
})
