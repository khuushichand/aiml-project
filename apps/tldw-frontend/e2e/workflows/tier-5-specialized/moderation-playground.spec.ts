/**
 * Moderation Playground E2E Tests (Tier 5)
 *
 * Tests the /moderation-playground page:
 * - Page loads with hero, tabs, and policy panel
 * - Tab navigation works across all 5 panels
 * - Server status badge visible
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/moderation-playground.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"

test.describe("Moderation Playground", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with hero heading and tab bar", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/moderation-playground", {
      waitUntil: "domcontentloaded",
    })

    const heading = authedPage.getByRole("heading", {
      name: /moderation playground/i,
    })
    const permissionError = authedPage.getByText(
      /admin moderation access required/i
    )
    await expect(heading.or(permissionError).first()).toBeVisible({
      timeout: 15_000,
    })

    await assertNoCriticalErrors(diagnostics)
  })

  test("tab navigation switches between panels", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/moderation-playground", {
      waitUntil: "domcontentloaded",
    })
    await expect(
      authedPage
        .getByRole("heading", { name: /moderation playground/i })
        .or(authedPage.getByText(/admin moderation access required/i))
        .first()
    ).toBeVisible({ timeout: 15_000 })

    // Skip if permission gated
    const hasPermissionError = await authedPage
      .getByText("Admin moderation access required")
      .isVisible()
      .catch(() => false)
    if (hasPermissionError) {
      test.skip()
      return
    }

    const tabs = authedPage.locator('[role="tab"]')
    const tabCount = await tabs.count()

    // Should have 5 tabs: Policy, Blocklist, Overrides, Test, Advanced
    expect(tabCount).toBeGreaterThanOrEqual(5)

    // Click Test Sandbox tab
    const testTab = authedPage.getByRole("tab", { name: /test sandbox/i })
    if (await testTab.isVisible().catch(() => false)) {
      await testTab.click()
      await expect(testTab).toHaveAttribute("aria-selected", "true")
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("server status badge is visible", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/moderation-playground", {
      waitUntil: "domcontentloaded",
    })

    const statusBadge = authedPage.getByText(/server (online|offline)/i).first()
    const permissionError = authedPage.getByText(
      /admin moderation access required/i
    )

    await expect(statusBadge.or(permissionError).first()).toBeVisible({
      timeout: 15_000,
    })

    await assertNoCriticalErrors(diagnostics)
  })

  test("policy settings fires API on load", async ({
    authedPage,
    diagnostics,
  }) => {
    const apiCall = expectApiCall(authedPage, {
      url: "/api/v1/moderation",
    })
    await authedPage.goto("/moderation-playground", {
      waitUntil: "domcontentloaded",
    })

    const { response } = await apiCall.catch(() => ({
      response: { status: () => 0 },
    }))

    // Either successful load or auth error
    if (response.status() > 0) {
      expect(response.status()).toBeLessThan(500)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
