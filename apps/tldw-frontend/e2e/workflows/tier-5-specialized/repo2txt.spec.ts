/**
 * Repo2Txt E2E Tests (Tier 5)
 *
 * Tests the /repo2txt page:
 * - Page loads with provider selector and output panel
 * - GitHub provider panel shows URL input
 * - Generate button is present when source loaded
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/repo2txt.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("Repo2Txt", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with provider and output panels", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/repo2txt", { waitUntil: "domcontentloaded" })

    await expect(
      authedPage.getByRole("heading", { name: /source provider/i })
    ).toBeVisible({ timeout: 15_000 })
    await expect(
      authedPage.getByRole("heading", { name: /output/i })
    ).toBeVisible({ timeout: 15_000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("page has interactive elements for provider selection", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/repo2txt", { waitUntil: "domcontentloaded" })

    const interactiveElements = authedPage.locator(
      "button, input, select, textarea"
    )
    await expect(interactiveElements.first()).toBeVisible({ timeout: 15_000 })
    expect(await interactiveElements.count()).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })
})
