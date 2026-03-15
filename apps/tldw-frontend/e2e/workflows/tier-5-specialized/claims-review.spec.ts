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
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Should have navigated to /content-review
    const url = authedPage.url()
    expect(url).toContain("/content-review")

    await assertNoCriticalErrors(diagnostics)
  })
})
