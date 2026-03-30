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

    // Header with "Model Playground" heading
    const heading = authedPage.getByRole("heading", {
      name: /model playground/i,
    })
    await expect(heading).toBeVisible({ timeout: 10_000 })

    // Chat area with role="log"
    const chatLog = authedPage.getByRole("log", { name: /chat messages/i })
    await expect(chatLog).toBeVisible({ timeout: 10_000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("debug panel toggles on and off", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/model-playground", {
      waitUntil: "domcontentloaded",
    })
    await expect(
      authedPage.getByRole("heading", { name: /model playground/i })
    ).toBeVisible({ timeout: 10_000 })

    const debugBtn = authedPage
      .locator("main")
      .last()
      .locator('button[aria-pressed]')
      .first()
    await expect(debugBtn).toBeVisible({ timeout: 10_000 })
    await debugBtn.click()
    await expect(
      authedPage.getByText(/no assistant messages yet/i)
    ).toBeVisible({ timeout: 10_000 })
    await debugBtn.click()
    await expect(
      authedPage.getByText(/no assistant messages yet/i)
    ).toHaveCount(0)

    await assertNoCriticalErrors(diagnostics)
  })

  test("Simple Chat button is present", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/model-playground", {
      waitUntil: "domcontentloaded",
    })

    const simpleChatBtn = authedPage.getByRole("button", {
      name: /simple chat/i,
    })
    await expect(simpleChatBtn).toBeVisible({ timeout: 10_000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
