/**
 * KnowledgeQA (RAG Search) Workflow E2E Tests
 *
 * Tests the complete knowledge QA lifecycle:
 * - Basic RAG search (query, results, citations)
 * - Settings & Presets (fast, balanced, thorough, expert mode)
 * - Follow-up questions (thread context)
 * - Search history
 * - No results / error states
 *
 * Run: npx playwright test e2e/workflows/knowledge-qa.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import { KnowledgeQAPage } from "../utils/page-objects/KnowledgeQAPage"
import { seedAuth, generateTestId, waitForConnection } from "../utils/helpers"

test.describe("KnowledgeQA Workflow", () => {
  let qaPage: KnowledgeQAPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    qaPage = new KnowledgeQAPage(page)
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.1  Basic RAG Search
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Basic RAG Search", () => {
    test("should navigate to KnowledgeQA page and display search bar", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Search bar should be visible
      const input = await qaPage.getSearchInput()
      await expect(input).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should focus search bar with / key", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Click somewhere else first, then press /
      await authedPage.locator("body").click()
      await qaPage.pressSlashToFocus()

      const input = await qaPage.getSearchInput()
      await expect(input).toBeFocused({ timeout: 5_000 })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should perform a RAG search and display results", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Perform search
      const query = "What is machine learning?"

      const [ragResult] = await Promise.all([
        qaPage.waitForRagSearch(),
        qaPage.search(query)
      ])

      expect(ragResult.status).toBe(200)
      expect(ragResult.requestBody?.query).toBe(query)

      // Wait for results to render
      await qaPage.waitForResults()

      // Either we get an answer or a no-results state
      const answer = await qaPage.getAnswerText()
      const noResults = await qaPage.hasNoResults()

      // One of these should be true
      expect(answer.length > 0 || noResults).toBeTruthy()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should surface the evidence panel after a live search", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.search("content analysis")
      await qaPage.waitForResults()

      await expect(qaPage.getEvidencePanel()).toBeVisible({ timeout: 10_000 })
      const answer = await qaPage.getAnswerText()
      if (answer.length > 0) {
        const citationButtons = qaPage.getCitationButtons()
        const citationCount = await citationButtons.count()
        if (citationCount > 0) {
          await qaPage.clickCitation(0)
          await expect(qaPage.getEvidencePanel()).toBeVisible({ timeout: 10_000 })
        } else {
          await expect(
            qaPage.getEvidencePanel().getByText(/No sources yet|0 sources/i).first()
          ).toBeVisible({ timeout: 10_000 })
        }
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show loading state during search", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Start search
      const input = await qaPage.getSearchInput()
      await input.fill("test loading state")
      await input.press("Enter")

      // Check for loading indicator (may be brief)
      const wasLoading = await qaPage.isLoading()
      // Loading state is transient, we just verify no crash

      await qaPage.waitForResults()

      await assertNoCriticalErrors(diagnostics)
    })

    test("shows progressive loading stages for delayed long-running searches", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)

      await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: "",
        })
      })

      await authedPage.route("**/api/v1/rag/search", async (route) => {
        await authedPage.waitForTimeout(6500)
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            results: [
              {
                id: "delayed-source-1",
                content: "Delayed source excerpt",
                metadata: {
                  title: "Delayed Source",
                  source_type: "media_db",
                  url: "https://example.com/delayed-source",
                },
                score: 0.92,
              },
            ],
            answer: "Delayed answer [1]",
            expanded_queries: ["delayed response query"],
          }),
        })
      })

      await qaPage.goto()
      await qaPage.waitForReady()

      const input = await qaPage.getSearchInput()
      await input.fill("delayed response query")
      await input.press("Enter")

      await expect(
        authedPage.getByText(/Searching documents\.\.\./i)
      ).toBeVisible({ timeout: 4_000 })
      await expect(
        authedPage.getByText(/Reranking results\.\.\./i)
      ).toBeVisible({ timeout: 10_000 })

      await qaPage.waitForResults()
      await expect(authedPage.getByText("AI Answer")).toBeVisible({
        timeout: 10_000
      })
      await expect(
        authedPage.getByTestId("knowledge-answer-content")
      ).toContainText(/Delayed answer/i, { timeout: 10_000 })
      await expect(qaPage.getCitationButtons().first()).toBeVisible({
        timeout: 10_000
      })

      await assertNoCriticalErrors(diagnostics)
    })

    test("treats whitespace-only answers as no generated answer", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)

      await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: "",
        })
      })

      await authedPage.route("**/api/v1/rag/search", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            results: [
              {
                id: "blank-answer-source-1",
                content: "Relevant source excerpt",
                metadata: {
                  title: "Blank Answer Source",
                  source_type: "notes",
                },
                score: 0.91,
              },
            ],
            answer: "   ",
          }),
        })
      })

      await qaPage.goto()
      await qaPage.waitForReady()
      await qaPage.search("blank answer regression")
      await qaPage.waitForResults()

      await expect(
        authedPage.getByText(/Found 1 relevant source\./i)
      ).toBeVisible({ timeout: 10_000 })
      await expect(authedPage.getByText("AI Answer")).toHaveCount(0)
      await expect(authedPage.getByTestId("knowledge-answer-content")).toHaveCount(0)
      await expect(await qaPage.getAnswerText()).toBe("")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.2  Settings & Presets
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Settings & Presets", () => {
    test("should open settings panel", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      await expect(qaPage.getSettingsDialog()).toBeVisible({ timeout: 10_000 })
      await expect(
        qaPage.getSettingsDialog().getByText(/RAG Settings/i)
      ).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between presets", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      await expect(qaPage.getSettingsDialog()).toBeVisible({ timeout: 10_000 })

      for (const preset of ["fast", "balanced", "thorough"] as const) {
        await qaPage.selectPreset(preset)
        await expect(
          qaPage
            .getSettingsDialog()
            .getByRole("radio", { name: new RegExp(`^${preset}\\b`, "i") })
        ).toHaveAttribute("aria-checked", "true")
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should toggle expert mode", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      const settingsDialog = qaPage.getSettingsDialog()
      const expertToggle = qaPage.getExpertModeToggle()

      const initialChecked = await expertToggle.getAttribute("aria-checked")
      await qaPage.toggleExpertMode()

      await expect(expertToggle).not.toHaveAttribute("aria-checked", initialChecked)
      await expect(settingsDialog.getByText("Agentic RAG")).toBeVisible({
        timeout: 10_000
      })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should apply settings to search request", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      await qaPage.selectPreset("thorough")
      await expect(
        qaPage
          .getSettingsDialog()
          .getByRole("radio", { name: /^thorough\b/i })
      ).toHaveAttribute("aria-checked", "true")
      await qaPage.getSettingsDialog().getByRole("button", { name: /^Done$/i }).click()

      const [ragResult] = await Promise.all([
        qaPage.waitForRagSearch(),
        qaPage.search("test with settings")
      ])

      await qaPage.waitForResults()
      expect(ragResult.status).toBe(200)
      expect(ragResult.requestBody?.top_k).toBe(20)
      expect(ragResult.requestBody?.enable_citations).toBe(true)
      expect(ragResult.requestBody?.enable_post_verification).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.3  Follow-up Questions
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Follow-up Questions", () => {
    test("should show follow-up input after initial search", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.search("What is neural network?")
      await qaPage.waitForResults()

      const answer = await qaPage.getAnswerText()
      if (answer.length > 0) {
        const followUpInput = await qaPage.getFollowUpInput()
        await expect(followUpInput).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should submit follow-up question with thread context", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.search("What is deep learning?")
      await qaPage.waitForResults()

      const hasFollowUp = await qaPage.isFollowUpVisible()
      expect(hasFollowUp).toBeTruthy()
      if (hasFollowUp) {
        const [ragResult] = await Promise.all([
          qaPage.waitForRagSearch(),
          qaPage.askFollowUp("Can you elaborate on convolutional networks?")
        ])

        await qaPage.waitForResults()
        expect(ragResult.status).toBe(200)
        expect(ragResult.requestBody?.query).toBe(
          "Can you elaborate on convolutional networks?"
        )
        await expect(
          authedPage.getByText(/Conversation • 2 turns/i)
        ).toBeVisible({ timeout: 10_000 })
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.4  Search History
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Search History", () => {
    test("should open history sidebar", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      const firstQuery = `history-${generateTestId("first")}`
      const secondQuery = `history-${generateTestId("second")}`

      await qaPage.search(firstQuery)
      await qaPage.waitForResults()

      const input = await qaPage.getSearchInput()
      await input.fill(secondQuery)
      await input.press("Enter")
      await qaPage.waitForResults()

      await qaPage.toggleHistorySidebar()
      await expect(qaPage.getHistorySidebar()).toBeVisible({ timeout: 10_000 })

      const firstHistoryEntry = authedPage.getByRole("button", {
        name: new RegExp(secondQuery, "i")
      })
      await expect(firstHistoryEntry).toBeVisible({ timeout: 10_000 })
      await firstHistoryEntry.click()

      await expect(input).toHaveValue(secondQuery)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should start new search with Cmd+K", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.pressNewSearch()
      await authedPage.waitForTimeout(500)

      // Search input should be focused/cleared
      const input = await qaPage.getSearchInput()
      await expect(input).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.5  No Results / Error States
  // ═════════════════════════════════════════════════════════════════════

  test.describe("No Results / Error States", () => {
    test("should handle no results gracefully", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Search for something that won't match
      const nonsenseQuery = `xyzzy-${generateTestId()}-qqq`
      await qaPage.search(nonsenseQuery)
      await qaPage.waitForResults()

      // Should get empty results or web fallback
      const answer = await qaPage.getAnswerText()
      const noResults = await qaPage.hasNoResults()
      const sourceOnlyState = await qaPage.hasSourceOnlyState()

      expect(answer.length > 0 || noResults || sourceOnlyState).toBeTruthy()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display error state when API fails", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      // Mock a failing API by intercepting the route
      await authedPage.route("**/api/v1/rag/search", (route) => {
        route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" })
        })
      })

      await qaPage.search("trigger error")
      await authedPage.waitForTimeout(3000)

      // Should show some kind of error state
      const errorMsg = await qaPage.getErrorMessage()

      expect(errorMsg).not.toBeNull()

      // Unroute to not affect other tests
      await authedPage.unroute("**/api/v1/rag/search")

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
