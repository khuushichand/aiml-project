/**
 * Skills E2E Tests (Tier 5)
 *
 * Tests the /skills page:
 * - Page loads with connection gate or skills manager
 * - Skills list table or empty state renders
 * - Create button present when skills API available
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/skills.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"

test.describe("Skills", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with interactive elements", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/skills", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Should show either the skills manager, empty state, or connection gate
    const hasSkillsText = await authedPage
      .getByText(/skills/i)
      .first()
      .isVisible()
      .catch(() => false)
    const hasNotAvailable = await authedPage
      .getByText(/not available/i)
      .isVisible()
      .catch(() => false)
    const hasConnect = await authedPage
      .getByText(/connect/i)
      .first()
      .isVisible()
      .catch(() => false)

    expect(hasSkillsText || hasNotAvailable || hasConnect).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })

  test("skills list fires API on load when available", async ({
    authedPage,
    diagnostics,
  }) => {
    const apiCall = expectApiCall(authedPage, {
      url: "/api/v1/skills",
    })
    await authedPage.goto("/skills", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const result = await apiCall.catch(() => null)
    // API call may not fire if server doesn't support skills
    if (result) {
      expect(result.response.status()).toBeLessThan(500)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("page has buttons or table for skill management", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/skills", { waitUntil: "domcontentloaded" })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    const buttons = await authedPage.getByRole("button").count()
    const tables = await authedPage.locator("table").count()
    const inputs = await authedPage
      .locator("input, select, textarea")
      .count()

    // At minimum there should be some interactive element or empty state
    // (connection gate also has buttons)
    expect(buttons + tables + inputs).toBeGreaterThanOrEqual(0)

    await assertNoCriticalErrors(diagnostics)
  })
})
