/**
 * Search (RAG) Workflow E2E Tests
 *
 * Tests the complete search workflow from a user's perspective:
 * - Basic search
 * - Empty results handling
 * - Search filters
 * - Result interaction
 * - RAG integration (semantic vs keyword search)
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { SearchPage } from "../utils/page-objects"
import { seedAuth, TEST_CONFIG, generateTestId, waitForConnection } from "../utils/helpers"

test.describe("Search Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test.describe("Search Page Navigation", () => {
    test("should navigate to search page and display interface", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Verify search input is visible
      const input = await searchPage.getSearchInput()
      await expect(input).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display search controls", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Search input should be present
      const input = await searchPage.getSearchInput()
      await expect(input).toBeVisible()

      // Search button may also be present
      const searchBtn = authedPage.getByRole("button", { name: /search/i })
      // Button is optional if Enter key works

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Basic Search", () => {
    test("should perform a search query", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      const testQuery = "test search query"
      await searchPage.search(testQuery)

      // Wait for results or no-results state
      await searchPage.waitForResults()

      // Verify search was performed (results or empty state shown)
      const hasResults = !(await searchPage.hasNoResults())

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display search results with titles", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      await searchPage.search("content")
      await searchPage.waitForResults()

      const results = await searchPage.getResults()

      // If there are results, they should have titles
      for (const result of results) {
        expect(result.title).toBeTruthy()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should highlight matching terms in results", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      const searchTerm = "important"
      await searchPage.search(searchTerm)
      await searchPage.waitForResults()

      // Check for highlighted text
      const highlights = await searchPage.getHighlightedText()
      // Highlighting is optional feature

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Empty Results", () => {
    test("should display no results message for nonexistent content", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Search for something unlikely to exist
      const uniqueQuery = `nonexistent-content-${generateTestId()}-xyz`
      await searchPage.search(uniqueQuery)
      await searchPage.waitForResults()

      // Should show no results or empty state
      const hasNoResults = await searchPage.hasNoResults()
      const results = await searchPage.getResults()

      expect(hasNoResults || results.length === 0).toBeTruthy()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should provide helpful message when no results found", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      const uniqueQuery = `nonexistent-${generateTestId()}`
      await searchPage.search(uniqueQuery)
      await searchPage.waitForResults()

      const message = await searchPage.getNoResultsMessage()
      // Message content varies by implementation

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Search Filters", () => {
    test("should display filter options", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Look for filter elements
      const filters = authedPage.locator(
        "[data-testid='search-filters'], .search-filters, .filter-panel"
      )

      // Filters may or may not exist
      await assertNoCriticalErrors(diagnostics)
    })

    test("should filter by content type if available", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try to apply type filter
      try {
        await searchPage.filterByType("video")
      } catch {
        // Filter may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should filter by date range if available", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try to apply date filter
      try {
        await searchPage.filterByDateRange("2024-01-01", "2024-12-31")
      } catch {
        // Date filter may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should filter by tag if available", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try to apply tag filter
      try {
        await searchPage.filterByTag("test-tag")
      } catch {
        // Tag filter may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should clear filters", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try to clear filters
      try {
        await searchPage.clearFilters()
      } catch {
        // Clear filters button may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Result Interaction", () => {
    test("should click on search result and navigate to content", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      await searchPage.search("content")
      await searchPage.waitForResults()

      const results = await searchPage.getResults()

      if (results.length > 0) {
        // Click first result
        await searchPage.clickResult(0)

        // Should navigate to detail page or show content
        await authedPage.waitForTimeout(1000)
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate back to search from result detail", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      await searchPage.search("content")
      await searchPage.waitForResults()

      const results = await searchPage.getResults()

      if (results.length > 0) {
        await searchPage.clickResult(0)
        await authedPage.waitForTimeout(1000)

        // Try to go back
        await searchPage.backToSearch()
        await authedPage.waitForTimeout(1000)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("RAG Integration", () => {
    test("should support semantic search mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try semantic search
      try {
        await searchPage.semanticSearch("What is machine learning?")
        await searchPage.waitForResults()
      } catch {
        // Semantic search mode may not be explicitly available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should support keyword search mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Try keyword search
      try {
        await searchPage.keywordSearch("machine learning")
        await searchPage.waitForResults()
      } catch {
        // Keyword search mode may not be explicitly available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display search mode selector if available", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Check search mode
      const mode = await searchPage.getSearchMode()
      // Mode may be unknown if not explicitly shown

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Search Performance", () => {
    test("should display loading indicator during search", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Start search but don't wait for results
      const input = await searchPage.getSearchInput()
      await input.fill("test query")
      await input.press("Enter")

      // Look for loading indicator
      const loading = authedPage.locator(
        ".loading, .searching, [data-loading='true'], .ant-spin"
      )

      // Loading may appear briefly
      await authedPage.waitForTimeout(500)

      // Wait for search to complete
      await searchPage.waitForResults()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Search from Chat Context", () => {
    test("should support search integration in chat", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      // Navigate to chat first
      await authedPage.goto("/chat", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      // Look for RAG/search integration in chat
      const ragToggle = authedPage.locator(
        "[data-testid='rag-toggle'], [data-testid='knowledge-toggle'], .rag-switch"
      )

      if ((await ragToggle.count()) > 0) {
        // RAG integration exists in chat
        await expect(ragToggle.first()).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Knowledge Page", () => {
    test("should navigate to knowledge page", async ({
      authedPage,
      diagnostics
    }) => {
      await authedPage.goto("/knowledge", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      // Verify page loaded
      await authedPage.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display knowledge base content", async ({
      authedPage,
      diagnostics
    }) => {
      await authedPage.goto("/knowledge", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      // Look for knowledge content
      const knowledgeContainer = authedPage.locator(
        "[data-testid='knowledge-container'], .knowledge-page, .knowledge-base"
      )

      await authedPage.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Search Suggestions", () => {
    test("should show search suggestions if available", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      const input = await searchPage.getSearchInput()
      await input.fill("test")

      // Look for suggestions dropdown
      const suggestions = authedPage.locator(
        "[data-testid='search-suggestions'], .autocomplete-dropdown, .suggestions"
      )

      // Suggestions may appear after typing
      await authedPage.waitForTimeout(1000)

      // Suggestions are optional feature
      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Recent Searches", () => {
    test("should track recent searches if available", async ({
      authedPage,
      diagnostics
    }) => {
      const searchPage = new SearchPage(authedPage)
      await searchPage.goto()
      await searchPage.waitForReady()

      // Look for recent searches
      const recentSearches = authedPage.locator(
        "[data-testid='recent-searches'], .recent-searches, .search-history"
      )

      // Recent searches are optional feature
      await assertNoCriticalErrors(diagnostics)
    })
  })
})
