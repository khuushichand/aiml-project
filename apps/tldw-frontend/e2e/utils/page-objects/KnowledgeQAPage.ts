/**
 * Page Object for KnowledgeQA (RAG Search) workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class KnowledgeQAPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  // ── Navigation ──────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/knowledge", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    // Wait for search bar or main container
    const container = this.page.locator(
      "input[type='search'], input[type='text'], [data-testid*='search'], [placeholder*='search' i], [placeholder*='question' i], [placeholder*='ask' i]"
    )
    await container.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  // ── API Intercept ───────────────────────────────────────────────────

  async waitForRagSearch(): Promise<{ status: number; body: any }> {
    const response = await this.page.waitForResponse(
      (res) => res.url().includes("/rag/search") && res.request().method() === "POST",
      { timeout: 30_000 }
    )
    const body = await response.json().catch(() => null)
    return { status: response.status(), body }
  }

  // ── Search Bar ──────────────────────────────────────────────────────

  async getSearchInput(): Promise<Locator> {
    const candidates = [
      this.page.locator("[data-testid*='search-input']"),
      this.page.locator("[placeholder*='search' i]"),
      this.page.locator("[placeholder*='question' i]"),
      this.page.locator("[placeholder*='ask' i]"),
      this.page.locator("input[type='search']"),
      this.page.locator("input[type='text']").first()
    ]

    for (const candidate of candidates) {
      if ((await candidate.count()) > 0 && (await candidate.first().isVisible().catch(() => false))) {
        return candidate.first()
      }
    }

    return this.page.locator("input").first()
  }

  async search(query: string): Promise<void> {
    const input = await this.getSearchInput()
    await input.fill(query)
    await input.press("Enter")
  }

  async focusSearchBar(): Promise<void> {
    const input = await this.getSearchInput()
    await input.focus()
  }

  // ── Results ─────────────────────────────────────────────────────────

  async waitForResults(timeoutMs = 30_000): Promise<void> {
    // Wait for answer panel, source list, or no-results state
    const resultIndicator = this.page.locator(
      "[data-testid*='answer'], [data-testid*='source'], .answer-panel, .source-list, .ant-empty, [data-testid*='no-results']"
    )
    await resultIndicator.first().waitFor({ state: "visible", timeout: timeoutMs }).catch(() => {})
  }

  async getAnswerText(): Promise<string> {
    const answer = this.page.locator(
      "[data-testid*='answer'], .answer-panel, .answer-content"
    )
    if (await answer.first().isVisible().catch(() => false)) {
      return (await answer.first().textContent()) ?? ""
    }
    return ""
  }

  async getSourceCount(): Promise<number> {
    const sources = this.page.locator(
      "[data-testid*='source-card'], .source-card, .source-item"
    )
    return sources.count()
  }

  async clickCitation(index: number): Promise<void> {
    const citation = this.page.locator(
      `[data-testid*='citation'], .citation-badge, .citation-ref`
    ).nth(index)
    await citation.click()
  }

  async hasNoResults(): Promise<boolean> {
    const empty = this.page.locator(
      ".ant-empty, [data-testid*='no-results'], [data-testid*='empty']"
    )
    return (await empty.count()) > 0 && (await empty.first().isVisible().catch(() => false))
  }

  // ── Settings Panel ──────────────────────────────────────────────────

  async openSettings(): Promise<void> {
    const settingsBtn = this.page.getByRole("button", { name: /settings|gear|configure/i }).or(
      this.page.locator("[data-testid*='settings-toggle'], [aria-label*='settings' i]")
    )
    await settingsBtn.first().click()
  }

  async selectPreset(preset: "fast" | "balanced" | "thorough"): Promise<void> {
    const presetBtn = this.page.getByRole("button", { name: new RegExp(preset, "i") }).or(
      this.page.locator(`[data-testid*='preset-${preset}']`).or(
        this.page.getByText(new RegExp(`^${preset}$`, "i"))
      )
    )
    await presetBtn.first().click()
  }

  async toggleExpertMode(): Promise<void> {
    const toggle = this.page.getByText(/expert/i).or(
      this.page.locator("[data-testid*='expert']")
    )
    await toggle.first().click()
  }

  async setSearchMode(mode: "fts" | "vector" | "hybrid"): Promise<void> {
    const select = this.page.locator("[data-testid*='search-mode'], [id*='search_mode']")
    if (await select.first().isVisible().catch(() => false)) {
      await select.first().click()
      await this.page.locator(`.ant-select-item:has-text("${mode}")`).click()
    }
  }

  // ── Follow-Up Questions ─────────────────────────────────────────────

  async getFollowUpInput(): Promise<Locator> {
    return this.page.locator(
      "[data-testid*='follow-up'], [placeholder*='follow' i], [placeholder*='elaborate' i]"
    ).first()
  }

  async askFollowUp(question: string): Promise<void> {
    const input = await this.getFollowUpInput()
    await input.fill(question)
    await input.press("Enter")
  }

  async isFollowUpVisible(): Promise<boolean> {
    const input = await this.getFollowUpInput()
    return input.isVisible().catch(() => false)
  }

  // ── History Sidebar ─────────────────────────────────────────────────

  async toggleHistorySidebar(): Promise<void> {
    const toggle = this.page.getByRole("button", { name: /history/i }).or(
      this.page.locator("[data-testid*='history-toggle']")
    )
    await toggle.first().click()
  }

  async getHistoryItems(): Promise<Locator> {
    return this.page.locator(
      "[data-testid*='history-item'], .history-item, .search-history-item"
    )
  }

  async clickHistoryItem(index: number): Promise<void> {
    const items = await this.getHistoryItems()
    await items.nth(index).click()
  }

  // ── Keyboard Shortcuts ──────────────────────────────────────────────

  async pressNewSearch(): Promise<void> {
    await this.page.keyboard.press("Meta+k")
  }

  async pressSlashToFocus(): Promise<void> {
    await this.page.keyboard.press("/")
  }

  // ── Loading / Error States ──────────────────────────────────────────

  async isLoading(): Promise<boolean> {
    const loading = this.page.locator(
      ".ant-spin-spinning, [data-testid*='loading'], .searching"
    )
    return (await loading.count()) > 0 && (await loading.first().isVisible().catch(() => false))
  }

  async getErrorMessage(): Promise<string | null> {
    const error = this.page.locator(
      ".ant-alert-error, [data-testid*='error'], .error-message"
    )
    if (await error.first().isVisible().catch(() => false)) {
      return (await error.first().textContent()) ?? null
    }
    return null
  }
}
