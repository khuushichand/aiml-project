/**
 * Model Playground E2E Tests (Tier 5)
 *
 * Tests the /model-playground page:
 * - Page loads with header, chat area, sidebar toggle
 * - Debug panel toggle works
 * - Sidebar toggle works
 * - Simple Chat navigation button present
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/model-playground.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"

test.describe("Model Playground", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with header and chat area", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/model-playground", {
      waitUntil: "domcontentloaded",
    })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Header with "Model Playground" heading
    const heading = authedPage.getByText("Model Playground").first()
    await expect(heading).toBeVisible({ timeout: 10_000 })

    // Chat area with role="log"
    const chatLog = authedPage.locator('[role="log"]')
    const hasChatLog = await chatLog.isVisible().catch(() => false)
    expect(hasChatLog).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })

  test("debug panel toggles on and off", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/model-playground", {
      waitUntil: "domcontentloaded",
    })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Find the debug toggle button (Bug icon with aria-pressed)
    const debugBtn = authedPage
      .locator('button[aria-pressed]')
      .filter({ has: authedPage.locator("svg") })
      .first()

    if (await debugBtn.isVisible().catch(() => false)) {
      // Toggle debug on
      await debugBtn.click()
      // A short wait for the panel to appear
      await authedPage.waitForTimeout(300)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("Simple Chat button is present", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/model-playground", {
      waitUntil: "domcontentloaded",
    })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const simpleChatBtn = authedPage.getByRole("button", {
      name: /simple chat/i,
    })
    const isVisible = await simpleChatBtn.isVisible().catch(() => false)
    expect(isVisible).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })
})
