/**
 * Researchers E2E Tests (Tier 5)
 *
 * Tests the public /for/researchers landing page:
 * - Page loads with the self-hosted hero
 * - Primary CTA remains on the self-host path
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

  test("public landing page loads with self-hosted CTA", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/for/researchers", {
      waitUntil: "domcontentloaded",
    })

    await expect(
      authedPage.getByRole("heading", {
        name: /your research data deserves better than/i,
      })
    ).toBeVisible({ timeout: 15_000 })

    const primaryCta = authedPage.getByRole("link", {
      name: /start self-hosting free/i,
    })
    await expect(primaryCta).toBeVisible()
    await expect(primaryCta).toHaveAttribute("href", "/docs/self-hosting")

    await assertNoCriticalErrors(diagnostics)
  })
})
