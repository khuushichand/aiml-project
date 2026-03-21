/**
 * Journalists E2E Tests (Tier 5)
 *
 * Tests the public /for/journalists landing page:
 * - Page loads with the self-hosted hero
 * - Primary CTA remains on the self-host path
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/journalists.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("Journalists", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("public landing page loads with self-hosted CTA", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/for/journalists", {
      waitUntil: "domcontentloaded",
    })

    await expect(
      authedPage.getByRole("heading", {
        name: /your sources trust you with their safety/i,
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
