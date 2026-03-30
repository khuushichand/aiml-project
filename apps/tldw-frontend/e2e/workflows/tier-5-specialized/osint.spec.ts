/**
 * OSINT E2E Tests (Tier 5)
 *
 * Tests the public /for/osint landing page:
 * - Page loads with the self-hosted hero
 * - Primary CTA remains on the self-host path
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

  test("public landing page loads with self-hosted CTA", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/for/osint", { waitUntil: "domcontentloaded" })

    await expect(
      authedPage.getByRole("heading", {
        name: /media intelligence without the exposure/i,
      })
    ).toBeVisible({ timeout: 15_000 })

    const primaryCta = authedPage.getByRole("link", {
      name: /deploy self-hosted/i,
    })
    await expect(primaryCta).toBeVisible()
    await expect(primaryCta).toHaveAttribute("href", "/docs/self-hosting")

    await assertNoCriticalErrors(diagnostics)
  })
})
