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
   * Wait for the search page to be ready
   */
  async waitForReady(): Promise<void> {
    const searchReady = this.page.locator(
      "input[type='search'], [data-testid='search-input'], [role='searchbox']"
    )
    await expect(searchReady.first()).toBeVisible({ timeout: 20000 })
  }

  /**
   * Get the search input element
   */
  async getSearchInput(): Promise<Locator> {
    const candidates = [
      this.page.getByRole("searchbox"),
      this.page.getByTestId("search-input"),
      this.page.getByPlaceholder(/search|query|find/i),
      this.page.locator("input[type='search']")
    ]

    for (const candidate of candidates) {
      if ((await candidate.count()) > 0) {
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

    // Try clicking search button or pressing Enter
    const searchBtn = this.page.getByRole("button", { name: /search/i })
    if ((await searchBtn.count()) > 0 && (await searchBtn.isVisible())) {
      await searchBtn.click()
    } else {
      await input.press("Enter")
    }
  }

  /**
   * Wait for search results to load
   */
  async waitForResults(timeoutMs = 30000): Promise<void> {
    // Wait for either results or empty state
    const results = this.page.locator(
      "[data-testid='search-result'], .search-result, .result-item"
    )
    const empty = this.page.locator(
      "[data-testid='empty-results'], .no-results, .empty-state"
    )
    const loading = this.page.locator(".loading, .searching, [data-loading='true']")

    // Wait for loading to finish
    try {
      await expect(loading).not.toBeVisible({ timeout: timeoutMs })
    } catch {
      // Loading indicator may not exist
    }

    // Wait for results or empty state
    await expect(results.first().or(empty.first())).toBeVisible({
      timeout: timeoutMs
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

    const resultElements = this.page.locator(
      "[data-testid='search-result'], .search-result, .result-item"
    )
    const count = await resultElements.count()

    for (let i = 0; i < count; i++) {
      const el = resultElements.nth(i)

      const title =
        (await el.locator(".title, h3, h4, [data-field='title']").first().textContent()) ||
        (await el.textContent()) ||
        ""

      const snippet =
        (await el
          .locator(".snippet, .excerpt, .description, [data-field='snippet']")
          .first()
          .textContent()
          .catch(() => null)) ?? undefined

      const type =
        (await el
          .locator(".type, .category, [data-field='type']")
          .first()
          .textContent()
          .catch(() => null)) ?? undefined

      const scoreText = await el
        .locator(".score, [data-field='score']")
        .first()
        .textContent()
        .catch(() => null)
      const score = scoreText ? parseFloat(scoreText) : undefined

      items.push({
        title: title.trim(),
        snippet: snippet?.trim(),
        type: type?.trim(),
        score
      })
    }

    return items
  }

  /**
   * Check if there are no results
   */
  async hasNoResults(): Promise<boolean> {
    const noResults = this.page.locator(
      "[data-testid='empty-results'], .no-results, .empty-state"
    )
    return (await noResults.count()) > 0 && (await noResults.isVisible())
  }

  /**
   * Get the "no results" message
   */
  async getNoResultsMessage(): Promise<string | null> {
    const noResults = this.page.locator(
      "[data-testid='empty-results'], .no-results, .empty-state"
    )

    if ((await noResults.count()) === 0) return null

    return (await noResults.textContent()) || null
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
    await results.nth(index).click()
  }

  /**
   * Navigate back to search from result detail
   */
  async backToSearch(): Promise<void> {
    const backBtn = this.page.getByRole("button", { name: /back|return/i })

    if ((await backBtn.count()) > 0) {
      await backBtn.click()
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
