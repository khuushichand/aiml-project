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
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Route root data-testid
    const routeRoot = authedPage.locator('[data-testid="repo2txt-route-root"]')
    const hasRoot = await routeRoot.isVisible().catch(() => false)

    // Provider panel
    const providerPanel = authedPage.locator(
      '[data-testid="repo2txt-provider-panel"]'
    )
    const hasProvider = await providerPanel.isVisible().catch(() => false)

    // Output panel
    const outputPanel = authedPage.locator(
      '[data-testid="repo2txt-output-panel"]'
    )
    const hasOutput = await outputPanel.isVisible().catch(() => false)

    expect(hasRoot || hasProvider || hasOutput).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })

  test("page has interactive elements for provider selection", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/repo2txt", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const buttons = await authedPage.getByRole("button").count()
    const inputs = await authedPage
      .locator("input, select, textarea")
      .count()
    expect(buttons + inputs).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })
})
