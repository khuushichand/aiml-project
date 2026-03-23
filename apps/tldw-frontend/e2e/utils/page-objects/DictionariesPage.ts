/**
 * Page Object for Chat Dictionaries workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForAppShell, waitForConnection } from "../helpers"

const escapeRegex = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

export class DictionariesPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  // ── Navigation ──────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/dictionaries", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for table or empty state
    const container = this.page.locator(".ant-table, .ant-empty, [data-testid='dictionaries-list']")
    await container.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  async searchDictionaries(query: string): Promise<void> {
    const searchInput = this.page.getByRole("textbox", { name: /search dictionaries/i })
    await searchInput.fill(query)
  }

  // ── API Request Helpers ─────────────────────────────────────────────

  /** Intercept and wait for a specific API pattern */
  async waitForApiCall(
    urlPattern: string | RegExp,
    method: string = "GET"
  ): Promise<{ status: number; body: any }> {
    const response = await this.page.waitForResponse(
      (res) =>
        (typeof urlPattern === "string"
          ? res.url().includes(urlPattern)
          : urlPattern.test(res.url())) &&
        res.request().method() === method,
      { timeout: 15_000 }
    )
    const body = await response.json().catch(() => null)
    return { status: response.status(), body }
  }

  // ── Dictionary CRUD ─────────────────────────────────────────────────

  async clickNewDictionary(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /^New Dictionary$/i })
    await btn.click()
  }

  async fillDictionaryForm(name: string, description?: string): Promise<void> {
    const modal = this.page.getByRole("dialog", { name: /create dictionary|edit dictionary/i }).last()
    await modal.waitFor({ state: "visible", timeout: 10_000 })
    const nameInput = modal.getByRole("textbox").first()
    await nameInput.fill(name)
    if (description) {
      const descInput = modal.getByRole("textbox").nth(1)
      await descInput.fill(description)
    }
  }

  async submitDictionaryForm(): Promise<void> {
    const submitBtn = this.page.getByRole("dialog", {
      name: /create dictionary|edit dictionary/i
    }).last().getByRole("button", {
      name: /create|save|ok|submit/i
    })
    await submitBtn.click()
  }

  async createDictionary(name: string, description?: string): Promise<void> {
    await this.clickNewDictionary()
    await this.fillDictionaryForm(name, description)
    await this.submitDictionaryForm()
    // Wait for modal to close
    await this.page.locator(".ant-modal").waitFor({ state: "hidden", timeout: 10_000 }).catch(() => {})
  }

  async findDictionaryRow(name: string): Promise<Locator> {
    await this.searchDictionaries(name)
    return this.page.locator(".ant-table-row").filter({
      has: this.page.getByRole("cell", { name: new RegExp(`^${escapeRegex(name)}$`) })
    })
  }

  async clickEditOnRow(name: string): Promise<void> {
    await this.searchDictionaries(name)
    const button = this.page.getByRole("button", {
      name: new RegExp(`^Edit dictionary ${escapeRegex(name)}$`)
    })
    await this.clickRowActionButton(button)
    await this.page.getByRole("dialog", { name: /edit dictionary/i }).waitFor({
      state: "visible",
      timeout: 10_000
    })
  }

  async clickDeleteOnRow(name: string): Promise<void> {
    await this.searchDictionaries(name)
    const button = this.page.getByRole("button", {
      name: new RegExp(`^Delete dictionary ${escapeRegex(name)}$`)
    })
    await this.clickRowActionButton(button)
  }

  async confirmDeletion(): Promise<void> {
    const confirmBtn = this.page.getByRole("button", { name: /ok|confirm|yes|delete/i }).last()
    await confirmBtn.click()
  }

  async getDictionaryNames(): Promise<string[]> {
    const rows = this.page.locator(".ant-table-row")
    const count = await rows.count()
    const names: string[] = []
    for (let i = 0; i < count; i++) {
      const text = await rows.nth(i).locator("td").first().textContent()
      if (text) names.push(text.trim())
    }
    return names
  }

  // ── Entry Management ────────────────────────────────────────────────

  async clickManageEntries(dictionaryName: string): Promise<void> {
    await this.searchDictionaries(dictionaryName)
    const button = this.page.getByRole("button", {
      name: new RegExp(`^Manage entries for ${escapeRegex(dictionaryName)}$`)
    })
    await this.clickRowActionButton(button)
    await this.page.locator(".ant-drawer:visible").last().waitFor({
      state: "visible",
      timeout: 10_000
    })
  }

  async fillEntryForm(pattern: string, replacement: string, type: "literal" | "regex" = "literal"): Promise<void> {
    const drawer = this.page.locator(".ant-drawer:visible").last()
    await drawer.waitFor({ state: "visible", timeout: 10_000 })
    const patternInput = drawer.getByRole("textbox", { name: /find/i }).first()
    await patternInput.fill(pattern)

    const replacementInput = drawer.getByRole("textbox", { name: /replace with/i }).first()
    await replacementInput.fill(replacement)

    // Select type if dropdown exists
    const typeSelect = drawer.getByRole("combobox", { name: /match type/i }).first().or(
      drawer.locator("[id*='type'], [data-testid*='type']").first()
    )
    if (await typeSelect.isVisible().catch(() => false)) {
      await typeSelect.click()
      await this.page.getByTitle(type, { exact: true }).or(
        this.page.locator(`.ant-select-item:has-text("${type}")`)
      ).first().click()
    }
  }

  async submitEntry(): Promise<void> {
    const drawer = this.page.locator(".ant-drawer:visible").last()
    const btn = drawer.getByRole("button", { name: /^Add Entry$/i }).last()
    await btn.click()
  }

  async getEntryCount(): Promise<number> {
    const drawer = this.page.locator(".ant-drawer:visible").last()
    const rows = drawer.getByRole("row")
    const count = await rows.count()
    return Math.max(0, count - 1)
  }

  // ── Validate & Preview ──────────────────────────────────────────────

  async clickValidate(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /validate/i })
    await btn.click()
  }

  async clickPreview(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /preview|test/i })
    await btn.click()
  }

  async fillPreviewText(text: string): Promise<void> {
    const input = this.page.locator("textarea, [data-testid='preview-input']").last()
    await input.fill(text)
  }

  // ── Import / Export ─────────────────────────────────────────────────

  async clickExportJSON(dictionaryName: string): Promise<void> {
    const row = await this.findDictionaryRow(dictionaryName)
    const exportBtn = row.getByRole("button", { name: /export/i }).or(
      row.locator("[title*='Export']")
    )
    await exportBtn.first().click()
    // If a dropdown appears, click JSON
    const jsonOption = this.page.locator(".ant-dropdown").getByText(/json/i)
    if (await jsonOption.isVisible().catch(() => false)) {
      await jsonOption.click()
    }
  }

  async clickImport(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /import/i })
    await btn.click()
  }

  async uploadImportFile(filePath: string): Promise<void> {
    const fileInput = this.page.locator("input[type='file']")
    await fileInput.setInputFiles(filePath)
  }

  // ── Statistics ──────────────────────────────────────────────────────

  async clickStats(dictionaryName: string): Promise<void> {
    const row = await this.findDictionaryRow(dictionaryName)
    const statsBtn = row.getByRole("button", { name: /stat/i }).or(
      row.locator("[title*='Stat'], [title*='stat']")
    )
    await statsBtn.first().click()
  }

  private async clickRowActionButton(button: Locator): Promise<void> {
    await button.scrollIntoViewIfNeeded()
    await button.waitFor({ state: "visible", timeout: 10_000 })
    await button.evaluate((element: Element) => {
      ;(element as HTMLElement).click()
    })
  }
}
