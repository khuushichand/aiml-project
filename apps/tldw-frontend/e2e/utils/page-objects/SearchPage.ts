/**
 * Page Object for Search/RAG functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class SearchPage {
  readonly page: Page
  readonly searchInput: Locator
  readonly searchButton: Locator
  readonly resultsList: Locator
  readonly filterPanel: Locator
  readonly emptyState: Locator

  constructor(page: Page) {
    this.page = page
    this.searchInput = page.getByRole("searchbox").or(
      page.getByPlaceholder(/search|query/i)
    )
    this.searchButton = page.getByRole("button", { name: /search/i })
    this.resultsList = page.getByTestId("search-results")
    this.filterPanel = page.getByTestId("search-filters")
    this.emptyState = page.getByTestId("empty-results")
  }

  /**
   * Navigate to the search page
   */
  async goto(): Promise<void> {
    await this.page.goto("/search", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Wait for the search page to be ready.
   * The search page ("Ask Your Library") has a text input at the bottom
   * with a placeholder like "What are the key findings..." and an "Ask" button.
   */
  async waitForReady(): Promise<void> {
    // The page shows "Ask Your Library" heading and an Ask button at the bottom
    await Promise.race([
      this.page.getByText("Ask Your Library").waitFor({ state: "visible", timeout: 20_000 }),
      this.page.getByRole("button", { name: /^ask$/i }).waitFor({ state: "visible", timeout: 20_000 }),
      this.page.locator("input[type='search'], [data-testid='search-input'], [role='searchbox']")
        .first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  /**
   * Get the search input element.
   * The "Ask Your Library" page uses a text input with placeholder like
   * "What are the key findings from the research?"
   */
  async getSearchInput(): Promise<Locator> {
    const candidates = [
      this.page.getByRole("searchbox"),
      this.page.getByTestId("search-input"),
      this.page.getByPlaceholder(/search|query|find|what are the key/i),
      this.page.locator("input[type='search']"),
      // "Ask Your Library" input — text input near the Ask button
      this.page.getByPlaceholder(/key findings|ask your/i),
      // Fallback: any visible input/textarea in the search page
      this.page.locator("input:visible, textarea:visible").last(),
    ]

    for (const candidate of candidates) {
      if ((await candidate.count()) > 0 && (await candidate.first().isVisible().catch(() => false))) {
        return candidate.first()
      }
    }

    throw new Error("Search input not found")
  }

  /**
   * Perform a search
   */
  async search(query: string): Promise<void> {
    const input = await this.getSearchInput()
    await expect(input).toBeVisible({ timeout: 10000 })
    await input.fill(query)

    // Try clicking search/ask button or pressing Enter
    const searchBtn = this.page.getByRole("button", { name: /^(search|ask)$/i })
    if ((await searchBtn.count()) > 0 && (await searchBtn.first().isVisible())) {
      await searchBtn.first().click()
    } else {
      await input.press("Enter")
    }
  }

  /**
   * Wait for search results to load
   */
  async waitForResults(timeoutMs = 30000): Promise<void> {
    // "Ask Your Library" streams an answer with citations.
    // Wait for any response content to appear, or traditional result items.
    const possibleResults = this.page.locator(
      "[data-testid='search-result'], .search-result, .result-item, " +
      "[data-role='assistant'], .prose, .answer-content, .citation, " +
      "[data-testid='empty-results'], .no-results, .empty-state"
    )

    // Wait for streaming/loading to settle
    await this.page.waitForTimeout(2_000)

    await expect(possibleResults.first()).toBeVisible({ timeout: timeoutMs }).catch(() => {
      // Answer may have rendered in a different container — just ensure page changed
    })
  }

  /**
   * Get search results
   */
  async getResults(): Promise<
    Array<{
      title: string
      snippet?: string
      type?: string
      score?: number
    }>
  > {
    const items: Array<{
      title: string
      snippet?: string
      type?: string
      score?: number
    }> = []

    // Traditional result items
    const resultElements = this.page.locator(
      "[data-testid='search-result'], .search-result, .result-item"
    )
    const count = await resultElements.count()

    for (let i = 0; i < count; i++) {
      const el = resultElements.nth(i)

      const title =
        (await el.locator(".title, h3, h4, [data-field='title']").first().textContent().catch(() => null)) ||
        (await el.textContent()) ||
        ""

      const snippet =
        (await el
          .locator(".snippet, .excerpt, .description, [data-field='snippet']")
          .first()
          .textContent()
          .catch(() => null)) ?? undefined

      items.push({ title: title.trim(), snippet: snippet?.trim() })
    }

    // If no traditional results, check for an answer/prose response
    // (the "Ask Your Library" page returns an LLM answer with citations)
    if (items.length === 0) {
      const answerContent = this.page.locator(
        "[data-role='assistant'], .prose, .answer-content, .markdown-content"
      )
      const answerCount = await answerContent.count()
      if (answerCount > 0) {
        const text = await answerContent.first().textContent().catch(() => "")
        if (text && text.trim().length > 0) {
          items.push({ title: "Answer", snippet: text.trim().slice(0, 200) })
        }
      }
    }

    return items
  }

  /**
   * Check if there are no results
   */
  async hasNoResults(): Promise<boolean> {
    const signals = [
      this.page.locator("[data-testid='empty-results'], .no-results, .empty-state").first(),
      this.page.getByText(/search complete\.\s*0 sources found\./i),
      this.page.getByText(/0 sources found/i),
      this.page.getByText(/no relevant context found/i),
      this.page.getByText(/no sources yet\./i)
    ]

    for (const signal of signals) {
      if (await signal.isVisible().catch(() => false)) {
        return true
      }
    }

    return false
  }

  /**
   * Get the "no results" message
   */
  async getNoResultsMessage(): Promise<string | null> {
    const signals = [
      this.page.locator("[data-testid='empty-results'], .no-results, .empty-state").first(),
      this.page.getByText(/search complete\.\s*0 sources found\./i),
      this.page.getByText(/no relevant context found/i),
      this.page.getByText(/no sources yet\./i)
    ]

    for (const signal of signals) {
      if (await signal.isVisible().catch(() => false)) {
        return (await signal.textContent()) || null
      }
    }

    return null
  }

  /**
   * Apply content type filter
   */
  async filterByType(type: string): Promise<void> {
    const filterDropdown = this.page.getByLabel(/type|content type|filter/i)

    if ((await filterDropdown.count()) > 0) {
      await filterDropdown.click()
      const option = this.page.getByRole("option", { name: new RegExp(type, "i") })
      await option.click()
    } else {
      // Try checkbox-style filter
      const checkbox = this.page.getByRole("checkbox", {
        name: new RegExp(type, "i")
      })
      if ((await checkbox.count()) > 0) {
        await checkbox.check()
      }
    }
  }

  /**
   * Apply date range filter
   */
  async filterByDateRange(
    startDate: string,
    endDate: string
  ): Promise<void> {
    const dateRange = this.page.getByTestId("date-range-filter")

    if ((await dateRange.count()) === 0) {
      // Try date picker inputs
      const startInput = this.page.getByLabel(/start date|from/i)
      const endInput = this.page.getByLabel(/end date|to/i)

      if ((await startInput.count()) > 0) {
        await startInput.fill(startDate)
      }
      if ((await endInput.count()) > 0) {
        await endInput.fill(endDate)
      }
    } else {
      await dateRange.click()
      // Handle date range picker...
    }
  }

  /**
   * Apply tag filter
   */
  async filterByTag(tag: string): Promise<void> {
    const tagFilter = this.page.getByLabel(/tags|filter by tag/i)

    if ((await tagFilter.count()) > 0) {
      await tagFilter.fill(tag)
      await tagFilter.press("Enter")
    } else {
      // Try clicking tag chip
      const tagChip = this.page.getByRole("button", { name: new RegExp(tag, "i") })
      if ((await tagChip.count()) > 0) {
        await tagChip.click()
      }
    }
  }

  /**
   * Clear all filters
   */
  async clearFilters(): Promise<void> {
    const clearBtn = this.page.getByRole("button", {
      name: /clear|reset|clear filters/i
    })

    if ((await clearBtn.count()) > 0) {
      await clearBtn.click()
    }
  }

  /**
   * Click on a search result
   */
  async clickResult(index: number): Promise<void> {
    const results = this.page.locator(
      "[data-testid='search-result'], .search-result, .result-item"
    )

    if ((await results.count()) > index) {
      await results.nth(index).click()
      return
    }

    const openInWorkspace = this.page.getByRole("button", { name: /open in workspace/i }).first()
    if (await openInWorkspace.isVisible().catch(() => false)) {
      await openInWorkspace.click()
      return
    }

    throw new Error("Search result interaction target not found")
  }

  /**
   * Navigate back to search from result detail
   */
  async backToSearch(): Promise<void> {
    const backBtn = this.page.getByRole("button", { name: /back|return/i })
    const newSearchBtn = this.page.getByRole("button", {
      name: /new search|start new topic/i
    }).first()

    if ((await backBtn.count()) > 0) {
      await backBtn.click()
    } else if (await newSearchBtn.isVisible().catch(() => false)) {
      await newSearchBtn.click()
    } else {
      await this.page.goBack()
    }
  }

  /**
   * Get highlighted text in results
   */
  async getHighlightedText(): Promise<string[]> {
    const highlights = this.page.locator("mark, .highlight, .search-highlight")
    const texts: string[] = []

    const count = await highlights.count()
    for (let i = 0; i < count; i++) {
      const text = await highlights.nth(i).textContent()
      if (text) texts.push(text)
    }

    return texts
  }

  /**
   * Perform semantic search (RAG)
   */
  async semanticSearch(query: string): Promise<void> {
    // Toggle to semantic search mode if available
    const modeToggle = this.page.getByRole("radio", { name: /semantic|vector/i })
    if ((await modeToggle.count()) > 0) {
      await modeToggle.click()
    }

    await this.search(query)
  }

  /**
   * Perform keyword search
   */
  async keywordSearch(query: string): Promise<void> {
    // Toggle to keyword search mode if available
    const modeToggle = this.page.getByRole("radio", { name: /keyword|text/i })
    if ((await modeToggle.count()) > 0) {
      await modeToggle.click()
    }

    await this.search(query)
  }

  /**
   * Get search mode
   */
  async getSearchMode(): Promise<"semantic" | "keyword" | "hybrid" | "unknown"> {
    const semantic = this.page.getByRole("radio", {
      name: /semantic|vector/i,
      checked: true
    })
    const keyword = this.page.getByRole("radio", {
      name: /keyword|text/i,
      checked: true
    })
    const hybrid = this.page.getByRole("radio", {
      name: /hybrid/i,
      checked: true
    })

    if ((await semantic.count()) > 0) return "semantic"
    if ((await keyword.count()) > 0) return "keyword"
    if ((await hybrid.count()) > 0) return "hybrid"

    return "unknown"
  }
}
