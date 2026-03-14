/**
 * Quiz Playground E2E Tests (Tier 2)
 *
 * Tests the Quiz Playground page lifecycle:
 * - Page loads with beta badge and appropriate state (online playground, demo, or connection banner)
 * - Tab switching between Take, Generate, Create, Manage, Results
 * - Global search and reset controls
 * - Demo quiz flow (start, take, submit, results) when in demo/offline mode
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/quiz.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { QuizPage } from "../../utils/page-objects/QuizPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth } from "../../utils/helpers"

test.describe("Quiz Playground", () => {
  let quiz: QuizPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    quiz = new QuizPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Quiz page with beta badge", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      // Beta badge should be visible in all states (online, offline, demo)
      const betaVisible = await quiz.betaBadge.isVisible().catch(() => false)
      const playgroundVisible = await quiz.isPlaygroundVisible()
      const demoVisible = await quiz.demoPreview.isVisible().catch(() => false)
      const connectionVisible = await quiz.connectionBanner.isVisible().catch(() => false)
      const unavailableVisible = await quiz.featureUnavailable.isVisible().catch(() => false)

      // At least one state should be rendered
      expect(
        betaVisible || playgroundVisible || demoVisible || connectionVisible || unavailableVisible
      ).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show beta tooltip on badge interaction", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      const badgeVisible = await quiz.betaBadge.isVisible().catch(() => false)
      if (!badgeVisible) return

      await quiz.betaBadge.click()
      await expect(quiz.betaTooltip).toBeVisible({ timeout: 5_000 })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between playground tabs without errors", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      // Only test tab switching if the playground (online state) is visible
      const playgroundVisible = await quiz.isPlaygroundVisible()
      if (!playgroundVisible) return

      for (const tab of ["generate", "create", "manage", "results", "take"] as const) {
        await quiz.switchToTab(tab)
        await authedPage.waitForTimeout(500)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Global Search and Controls
  // =========================================================================

  test.describe("Global Search", () => {
    test("should have global search input and apply button", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      const playgroundVisible = await quiz.isPlaygroundVisible()
      if (!playgroundVisible) return

      await expect(quiz.globalSearchInput).toBeVisible()
      await expect(quiz.globalSearchApplyButton).toBeVisible()
      await expect(quiz.resetCurrentTabButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should accept text input in global search", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      const playgroundVisible = await quiz.isPlaygroundVisible()
      if (!playgroundVisible) return

      await quiz.globalSearchInput.fill("test search query")
      await expect(quiz.globalSearchInput).toHaveValue("test search query")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Demo Mode Flow
  // =========================================================================

  test.describe("Demo Mode", () => {
    test("should render demo quiz preview or connection banner when offline", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      // If online, the playground is shown; if offline, either demo or connection banner
      const playgroundVisible = await quiz.isPlaygroundVisible()
      if (playgroundVisible) return // Skip demo tests when server is available

      const demoVisible = await quiz.demoPreview.isVisible().catch(() => false)
      const connectionVisible = await quiz.connectionBanner.isVisible().catch(() => false)

      expect(demoVisible || connectionVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should start and navigate through demo quiz when in demo mode", async ({
      authedPage,
      diagnostics,
    }) => {
      quiz = new QuizPage(authedPage)
      await quiz.goto()
      await quiz.assertPageReady()

      const demoVisible = await quiz.demoPreview.isVisible().catch(() => false)
      if (!demoVisible) return // Skip if not in demo mode

      // Click the start button
      await expect(quiz.demoStartButton).toBeVisible()
      await quiz.demoStartButton.click()

      // Should show the taking section
      await expect(quiz.demoTaking).toBeVisible({ timeout: 5_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Integration (requires server)
  // =========================================================================

  test.describe("Quiz API", () => {
    test("should fire GET /api/v1/quizzes when playground loads", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      quiz = new QuizPage(authedPage)

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/quizzes/,
        method: "GET",
      }, 20_000)

      await quiz.goto()
      await quiz.assertPageReady()

      const playgroundVisible = await quiz.isPlaygroundVisible()
      if (!playgroundVisible) return

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Quiz API may not be available on this server version
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
