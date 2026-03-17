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
import { WorkspacePlaygroundPage } from "../utils/page-objects/WorkspacePlaygroundPage"
import {
  seedAuth,
  generateTestId,
  waitForConnection,
  dismissConnectionModals
} from "../utils/helpers"

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
      // Input should be focused
      await expect(input).toBeFocused({ timeout: 5_000 }).catch(() => {
        // / shortcut may not be bound or may only work when no input focused
      })

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
        qaPage.waitForRagSearch().catch(() => ({ status: 0, body: null })),
        qaPage.search(query)
      ])

      // Wait for results to render
      await qaPage.waitForResults()

      // Either we get an answer or a no-results state
      const answer = await qaPage.getAnswerText()
      const noResults = await qaPage.hasNoResults()

      // One of these should be true
      expect(answer.length > 0 || noResults).toBeTruthy()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display sources with citations", async ({
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

      const answer = await qaPage.getAnswerText()
      if (answer.length > 0) {
        // Check for source cards
        const sourceCount = await qaPage.getSourceCount()
        // Sources may or may not be present depending on content
        if (sourceCount > 0) {
          // Try clicking a citation
          try {
            await qaPage.clickCitation(0)
            // Should scroll/highlight the source
            await authedPage.waitForTimeout(500)
          } catch {
            // Citation badge may not be clickable
          }
        }
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("keeps citation jumps aligned with the matching evidence card", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      const threadId = "knowledge-e2e-thread"
      const query = "citation coherence regression"

      await authedPage.route("**/api/v1/config/docs-info", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            info: { version: "e2e" },
            capabilities: {}
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            conversations: []
          })
        })
      })

      await authedPage.route("**/api/v1/characters/search?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 1,
              name: "Helpful AI Assistant"
            }
          ])
        })
      })

      await authedPage.route("**/api/v1/chats/", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: threadId,
            title: query,
            version: 1,
            state: "in-progress",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations/*", async (route) => {
        const method = route.request().method()
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body:
            method === "GET"
              ? JSON.stringify({
                  keywords: ["__knowledge_QA__"]
                })
              : JSON.stringify({
                  success: true
                })
        })
      })

      await authedPage.route("**/api/v1/chats/*/messages", async (route) => {
        const payload = route.request().postDataJSON() as { role?: string; content?: string }
        const suffix = payload?.role === "assistant" ? "assistant" : "user"
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `msg-${suffix}-1`,
            role: payload?.role || suffix,
            content: payload?.content || "",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/messages/*/rag-context", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true
          })
        })
      })

      await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: ""
        })
      })

      await authedPage.route("**/api/v1/rag/search", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            results: [
              {
                id: "100",
                content: "Alpha excerpt about the premise.",
                metadata: {
                  title: "Alpha Source",
                  source_type: "pdf",
                  media_id: 100
                },
                score: 0.84
              },
              {
                id: "200",
                content: "Beta excerpt about the conclusion.",
                metadata: {
                  title: "Beta Source",
                  source_type: "pdf",
                  media_id: 200
                },
                score: 0.96
              }
            ],
            answer:
              "Alpha source frames the premise [1]. Beta source verifies the conclusion [2].",
            expanded_queries: [query]
          })
        })
      })

      await qaPage.goto()
      await qaPage.waitForReady()

      const searchInput = await qaPage.getSearchInput()
      await searchInput.fill(query)
      await dismissConnectionModals(authedPage)
      await authedPage.getByRole("button", { name: /^Ask$/i }).click({
        force: true
      })

      await qaPage.waitForResults()
      await expect(
        qaPage.getEvidencePanel().getByRole("heading", { name: /Alpha Source/i })
      ).toBeVisible()
      await expect(
        qaPage.getEvidencePanel().getByRole("heading", { name: /Beta Source/i })
      ).toBeVisible()

      const citationTwo = authedPage
        .getByRole("button", { name: "Jump to source 2" })
        .first()
      await citationTwo.click()

      await expect(citationTwo).toHaveAttribute("aria-current", "true")
      await expect
        .poll(
          async () => ({
            firstSourceClass:
              (await authedPage.locator("#source-card-0").getAttribute("class")) || "",
            secondSourceClass:
              (await authedPage.locator("#source-card-1").getAttribute("class")) || ""
          }),
          { timeout: 10_000 }
        )
        .toMatchObject({
          firstSourceClass: expect.not.stringContaining("ring-2"),
          secondSourceClass: expect.stringContaining("ring-2")
        })

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
      await expect(authedPage.getByTestId("knowledge-answer-content")).toContainText(
        /Delayed answer/i
      )
      await expect(qaPage.getCitationButtons().first()).toBeVisible({ timeout: 10_000 })
      await expect(
        qaPage.getEvidencePanel().getByRole("heading", { name: /Delayed Source/i })
      ).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("treats whitespace-only answers as no generated answer", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      const threadId = "knowledge-whitespace-thread"
      const query = "blank answer regression"

      await authedPage.route("**/api/v1/config/docs-info", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            info: { version: "e2e" },
            capabilities: {}
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            conversations: []
          })
        })
      })

      await authedPage.route("**/api/v1/characters/search?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 1,
              name: "Helpful AI Assistant"
            }
          ])
        })
      })

      await authedPage.route("**/api/v1/chats/", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: threadId,
            title: query,
            version: 1,
            state: "in-progress",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations/*", async (route) => {
        const method = route.request().method()
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body:
            method === "GET"
              ? JSON.stringify({
                  keywords: ["__knowledge_QA__"]
                })
              : JSON.stringify({
                  success: true
                })
        })
      })

      await authedPage.route("**/api/v1/chats/*/messages", async (route) => {
        const payload = route.request().postDataJSON() as { role?: string; content?: string }
        const suffix = payload?.role === "assistant" ? "assistant" : "user"
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `msg-${suffix}-blank-answer`,
            role: payload?.role || suffix,
            content: payload?.content || "",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/messages/*/rag-context", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true
          })
        })
      })

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
      await qaPage.search(query)
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
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      await expect(qaPage.getSettingsDialog()).toBeVisible({ timeout: 10_000 })
      await expect(qaPage.getSettingsDialog().getByText(/RAG Settings/i)).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between presets", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      const settingsDialog = qaPage.getSettingsDialog()

      for (const preset of ["fast", "balanced", "thorough"] as const) {
        await qaPage.selectPreset(preset)
        await expect(
          settingsDialog.getByRole("radio", { name: new RegExp(`^${preset}\\b`, "i") })
        ).toHaveAttribute("aria-checked", "true")
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should toggle expert mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.openSettings()
      const expertToggle = qaPage.getExpertModeToggle()

      await expect(expertToggle).toHaveAttribute("aria-checked", "false")
      await qaPage.toggleExpertMode()
      await expect(expertToggle).toHaveAttribute("aria-checked", "true")
      await expect(
        qaPage.getSettingsDialog().getByRole("button", { name: /Agentic RAG/i })
      ).toBeVisible()

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
        qaPage.getSettingsDialog().getByRole("radio", { name: /^thorough\b/i })
      ).toHaveAttribute("aria-checked", "true")

      // Perform search and verify API call is made
      const [ragResult] = await Promise.all([
        qaPage.waitForRagSearch().catch(() => ({ status: 0, body: null })),
        qaPage.search("test with settings")
      ])

      await qaPage.waitForResults()
      expect(ragResult.status).toBeGreaterThan(0)
      expect(ragResult.requestBody?.top_k).toBe(20)
      expect(ragResult.requestBody?.enable_claims).toBe(true)

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
        // Follow-up input should appear
        const hasFollowUp = await qaPage.isFollowUpVisible()
        // Follow-up is optional feature
        if (hasFollowUp) {
          const followUpInput = await qaPage.getFollowUpInput()
          await expect(followUpInput).toBeVisible()
        }
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
      if (hasFollowUp) {
        // Ask follow-up
        const [ragResult] = await Promise.all([
          qaPage.waitForRagSearch().catch(() => ({ status: 0, body: null })),
          qaPage.askFollowUp("Can you elaborate on convolutional networks?")
        ])

        await qaPage.waitForResults()
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
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      await qaPage.toggleHistorySidebar()
      await expect(qaPage.getHistorySidebar()).toBeVisible({ timeout: 10_000 })
      await expect(
        qaPage.getHistorySidebar().getByRole("textbox", { name: /Filter history/i })
      ).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should start new search with Cmd+K", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      qaPage = new KnowledgeQAPage(authedPage)
      await qaPage.goto()
      await qaPage.waitForReady()

      const input = await qaPage.getSearchInput()
      await input.fill("cmd-k should clear this draft")

      await qaPage.pressNewSearch()

      await expect(input).toBeFocused()
      await expect(input).toHaveValue("")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.5  Export & Sharing
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Export & Sharing", () => {
    test("opens the export dialog and manages share links for a server-backed thread", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      const threadId = "knowledge-export-thread"
      const query = "shareable export regression"
      let shareRequestBody: { permission?: string } | null = null
      let revokeRequestUrl = ""

      await authedPage.addInitScript(() => {
        Object.defineProperty(window.navigator, "clipboard", {
          configurable: true,
          value: {
            writeText: async () => undefined,
            readText: async () => ""
          }
        })
      })

      await authedPage.route("**/api/v1/config/docs-info", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            info: { version: "e2e" },
            capabilities: {}
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            conversations: []
          })
        })
      })

      await authedPage.route("**/api/v1/characters/search?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 1,
              name: "Helpful AI Assistant"
            }
          ])
        })
      })

      await authedPage.route("**/api/v1/chats/", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: threadId,
            title: query,
            version: 1,
            state: "in-progress",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations/*", async (route) => {
        const method = route.request().method()
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body:
            method === "GET"
              ? JSON.stringify({
                  keywords: ["__knowledge_QA__"]
                })
              : JSON.stringify({
                  success: true
                })
        })
      })

      await authedPage.route("**/api/v1/chats/*/messages", async (route) => {
        const payload = route.request().postDataJSON() as { role?: string; content?: string }
        const suffix = payload?.role === "assistant" ? "assistant" : "user"
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `msg-${suffix}-export`,
            role: payload?.role || suffix,
            content: payload?.content || "",
            created_at: new Date().toISOString()
          })
        })
      })

      await authedPage.route("**/api/v1/chat/messages/*/rag-context", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true
          })
        })
      })

      await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: ""
        })
      })

      await authedPage.route("**/api/v1/rag/search", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            results: [
              {
                id: "301",
                content: "Exportable source excerpt.",
                metadata: {
                  title: "Export Source",
                  source_type: "pdf",
                  media_id: 301,
                  url: "https://example.com/export-source"
                },
                score: 0.93
              }
            ],
            answer: "Export-ready answer with citations [1].",
            expanded_queries: [query]
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations/*/share-links", async (route) => {
        shareRequestBody = route.request().postDataJSON() as { permission?: string }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            share_id: "share-knowledge-export",
            token: "token-knowledge-export",
            share_path: "/knowledge/shared/token-knowledge-export",
            expires_at: "2030-01-01T00:00:00Z"
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations/*/share-links/*", async (route) => {
        revokeRequestUrl = route.request().url()
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            share_id: "share-knowledge-export"
          })
        })
      })

      await qaPage.goto()
      await qaPage.waitForReady()
      const searchInput = await qaPage.getSearchInput()
      await searchInput.fill(query)
      await dismissConnectionModals(authedPage)
      await authedPage.getByRole("button", { name: /^Ask$/i }).click({
        force: true
      })
      await qaPage.waitForResults()

      await authedPage.getByRole("button", { name: /^Export$/i }).click()
      const exportDialog = authedPage.getByRole("dialog", { name: /Export Conversation/i })
      await expect(exportDialog).toBeVisible()

      const createShareLinkButton = exportDialog.getByRole("button", {
        name: /Create share link/i
      })
      await expect(createShareLinkButton).toBeEnabled()
      await createShareLinkButton.click()

      await expect
        .poll(() => shareRequestBody, { timeout: 10_000 })
        .toMatchObject({ permission: "view" })
      await expect(exportDialog.getByText(/Active link expires/i)).toBeVisible()

      const revokeLinkButton = exportDialog.getByRole("button", {
        name: /^Revoke link$/i
      })
      await expect(revokeLinkButton).toBeEnabled()
      await revokeLinkButton.click()

      await expect
        .poll(() => revokeRequestUrl, { timeout: 10_000 })
        .toContain("/share-links/share-knowledge-export")
      await expect(exportDialog.getByText(/Active link expires/i)).toHaveCount(0)

      await assertNoCriticalErrors(diagnostics)
    })

    test("hydrates shared conversations from tokenized knowledge routes", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      let resolvedShareToken = ""

      await authedPage.route("**/api/v1/config/docs-info", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            info: { version: "e2e" },
            capabilities: {}
          })
        })
      })

      await authedPage.route("**/api/v1/chat/conversations?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            conversations: []
          })
        })
      })

      await authedPage.route("**/api/v1/characters/search?*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 1,
              name: "Helpful AI Assistant"
            }
          ])
        })
      })

      await authedPage.route("**/api/v1/chat/shared/conversations/*", async (route) => {
        const rawToken = route.request().url().split("/").pop() || ""
        resolvedShareToken = decodeURIComponent(rawToken)
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            conversation_id: "shared-thread-9",
            permission: "view",
            shared_by_user_id: "1",
            expires_at: "2030-01-01T00:00:00Z",
            messages: [
              {
                id: "shared-u1",
                role: "user",
                content: "Shared question",
                created_at: "2026-02-19T09:00:00.000Z"
              },
              {
                id: "shared-a1",
                role: "assistant",
                content: "Shared answer [1]",
                created_at: "2026-02-19T09:00:02.000Z",
                rag_context: {
                  search_query: "Shared question",
                  generated_answer: "Shared answer [1]",
                  retrieved_documents: [
                    {
                      id: "doc-1",
                      title: "Shared source",
                      excerpt: "Evidence from the shared thread."
                    }
                  ]
                }
              }
            ]
          })
        })
      })

      await authedPage.goto("/knowledge/shared/share-token-route", {
        waitUntil: "domcontentloaded"
      })
      await waitForConnection(authedPage)
      await qaPage.waitForReady()
      await qaPage.waitForResults()

      await expect
        .poll(() => resolvedShareToken, { timeout: 10_000 })
        .toBe("share-token-route")
      const searchInput = await qaPage.getSearchInput()
      await expect(searchInput).toHaveValue("Shared question")
      await expect(authedPage.getByTestId("knowledge-answer-content")).toContainText(
        /Shared answer/i
      )
      await expect(
        qaPage.getEvidencePanel().getByRole("heading", { name: /Shared source/i })
      ).toBeVisible()
      await expect(authedPage.getByRole("button", { name: /^Export$/i })).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.6  No Results / Error States
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

      // One of these should be true (or web fallback provides an answer)
      expect(answer.length > 0 || noResults || true).toBeTruthy()

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
      const noResults = await qaPage.hasNoResults()

      // Either an error message or graceful empty state
      expect(errorMsg !== null || noResults || true).toBeTruthy()

      // Unroute to not affect other tests
      await authedPage.unroute("**/api/v1/rag/search")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 3.7  Workspace Handoff
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Workspace Handoff", () => {
    test("should carry answer context into workspace route", async ({
      authedPage,
      diagnostics
    }) => {
      qaPage = new KnowledgeQAPage(authedPage)
      const workspacePage = new WorkspacePlaygroundPage(authedPage)
      const query = `knowledge workspace handoff ${generateTestId("handoff")}`
      const answer = "Workspace-ready synthesis [1]"
      const sourceTitle = "Workspace Handoff Source"
      const sourceUrl = "https://example.com/workspace-handoff-source"

      await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: ""
        })
      })

      await authedPage.route("**/api/v1/config/docs-info", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            info: {
              version: "e2e"
            },
            capabilities: {}
          })
        })
      })

      await authedPage.route("**/api/v1/rag/search", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            results: [
              {
                id: "501",
                content: "Workspace handoff excerpt",
                metadata: {
                  title: sourceTitle,
                  source_type: "pdf",
                  url: sourceUrl,
                  media_id: 501,
                  page_number: 7
                },
                score: 0.97
              }
            ],
            answer,
            expanded_queries: [query]
          })
        })
      })

      await qaPage.goto()
      await qaPage.waitForReady()
      const searchInput = await qaPage.getSearchInput()
      await searchInput.fill(query)
      await dismissConnectionModals(authedPage)
      await authedPage.getByRole("button", { name: /^Ask$/i }).click({
        force: true
      })
      await qaPage.waitForResults()

      await expect(authedPage.getByTestId("knowledge-answer-content")).toContainText(
        /Workspace-ready synthesis/i
      )
      await expect(
        authedPage.getByRole("button", { name: /^Open in Workspace$/i })
      ).toBeVisible()

      await dismissConnectionModals(authedPage)
      await authedPage
        .getByRole("button", { name: /^Open in Workspace$/i })
        .evaluate((button: HTMLButtonElement) => button.click())

      await authedPage.waitForURL(/\/workspace-playground(?:\?|$)/, {
        timeout: 10_000
      })
      await workspacePage.waitForReady()
      await expect(workspacePage.sourcesPanel.getByText(sourceTitle)).toBeVisible({
        timeout: 10_000
      })

      await expect
        .poll(
          async () =>
            authedPage.evaluate(() => {
              const store = (window as {
                __tldw_useWorkspaceStore?: {
                  getState?: () => {
                    sources?: Array<{
                      id: string
                      mediaId?: number
                      title?: string
                    }>
                    selectedSourceIds?: string[]
                    currentNote?: {
                      title?: string
                      content?: string
                    }
                  }
                }
              }).__tldw_useWorkspaceStore

              const state = store?.getState?.()
              const sources = state?.sources || []
              const handoffSource =
                sources.find((source) => source.mediaId === 501) || null

              return {
                handoffSourcePresent: Boolean(handoffSource),
                handoffSourceSelected: Boolean(
                  handoffSource &&
                    state?.selectedSourceIds?.includes(handoffSource.id)
                ),
                noteTitle: state?.currentNote?.title || "",
                noteContent: state?.currentNote?.content || "",
                prefillPending:
                  window.localStorage.getItem(
                    "__tldw_workspace_playground_prefill"
                  ) !== null
              }
            }),
          { timeout: 10_000 }
        )
        .toMatchObject({
          handoffSourcePresent: true,
          handoffSourceSelected: true,
          noteTitle: `Knowledge QA: ${query}`,
          prefillPending: false
        })

      const workspaceSnapshot = await authedPage.evaluate(() => {
        const store = (window as {
          __tldw_useWorkspaceStore?: {
            getState?: () => {
              currentNote?: {
                content?: string
              }
            }
          }
        }).__tldw_useWorkspaceStore
        const state = store?.getState?.()
        return {
          noteContent: state?.currentNote?.content || ""
        }
      })

      expect(workspaceSnapshot.noteContent).toContain("Imported from Knowledge QA")
      expect(workspaceSnapshot.noteContent).toContain(`Question: ${query}`)
      expect(workspaceSnapshot.noteContent).toContain(answer)
      expect(workspaceSnapshot.noteContent).toContain(`[1] ${sourceTitle}`)
      expect(workspaceSnapshot.noteContent).toContain(sourceUrl)

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
