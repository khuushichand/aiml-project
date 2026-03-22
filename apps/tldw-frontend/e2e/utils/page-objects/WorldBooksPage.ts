/**
 * Page Object for World Books workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

export class WorldBooksPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  // ── Navigation ──────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/world-books", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    const container = this.page.locator(
      "[data-testid='world-books-table'], .ant-table, .ant-empty, [data-testid='world-books-list']"
    )
    await container.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  // ── API Intercept ───────────────────────────────────────────────────

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

  // ── World Book CRUD ─────────────────────────────────────────────────

  async clickNewWorldBook(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /new world book|create|add/i })
    await btn.click()
  }

  private worldBookDialog(title: RegExp): Locator {
    return this.page.getByRole("dialog", { name: title })
  }

  async fillWorldBookForm(fields: {
    name: string
    description?: string
    scanDepth?: number
    tokenBudget?: number
  }): Promise<void> {
    const modal = this.worldBookDialog(/create world book/i)
    await expect(modal).toBeVisible({ timeout: 10_000 })
    const nameInput = modal.getByLabel(/name/i).first()
    await nameInput.fill(fields.name)

    if (fields.description) {
      const descInput = modal.getByLabel(/description/i).first()
      await descInput.fill(fields.description)
    }
    if (fields.scanDepth !== undefined) {
      const depthInput = modal.getByLabel(/scan.depth/i).first()
      if (await depthInput.isVisible().catch(() => false)) {
        await depthInput.fill(String(fields.scanDepth))
      }
    }
    if (fields.tokenBudget !== undefined) {
      const budgetInput = modal.getByLabel(/token.budget/i).first()
      if (await budgetInput.isVisible().catch(() => false)) {
        await budgetInput.fill(String(fields.tokenBudget))
      }
    }
  }

  async submitWorldBookForm(title: RegExp = /create world book/i): Promise<void> {
    const modal = this.worldBookDialog(title)
    await expect(modal).toBeVisible({ timeout: 10_000 })
    const btn = modal.getByRole("button", { name: /create|save|ok|submit/i })
    await btn.click()
  }

  async createWorldBook(name: string, description?: string): Promise<void> {
    await this.clickNewWorldBook()
    await this.fillWorldBookForm({ name, description })
    await this.submitWorldBookForm(/create world book/i)
    await this.worldBookDialog(/create world book/i)
      .waitFor({ state: "hidden", timeout: 10_000 })
      .catch(() => {})
  }

  async searchWorldBooks(query: string): Promise<void> {
    const searchInput = this.page.getByTestId("world-books-search-input")
    await expect(searchInput).toBeVisible({ timeout: 10_000 })
    await searchInput.fill(query)
    await this.page.waitForTimeout(500)
  }

  async findWorldBookRow(name: string): Promise<Locator> {
    await this.searchWorldBooks(name)
    return this.page
      .getByRole("row")
      .filter({ hasText: new RegExp(escapeRegex(name), "i") })
  }

  async clickEditOnRow(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const editBtn = row.getByRole("button", { name: /edit world book|edit/i }).or(
      row.locator("[title='Edit'], [aria-label='Edit']")
    )
    await editBtn.first().click()
  }

  async clickDeleteOnRow(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const deleteBtn = row.getByRole("button", { name: /delete world book|delete/i }).or(
      row.locator("[title='Delete'], [aria-label='Delete']")
    )
    await deleteBtn.first().click()
  }

  async confirmDeletion(): Promise<void> {
    const confirmBtn = this.page.getByRole("button", { name: /ok|confirm|yes|delete/i }).last()
    await confirmBtn.click()
  }

  async clickUndoDelete(): Promise<void> {
    const undoBtn = this.page.getByRole("button", { name: /undo/i }).or(
      this.page.locator(".ant-notification").getByText(/undo/i)
    )
    await undoBtn.first().click()
  }

  async getWorldBookNames(): Promise<string[]> {
    const rows = this.page.getByRole("row")
    const count = await rows.count()
    const names: string[] = []
    for (let i = 0; i < count; i++) {
      const text = await rows.nth(i).getByRole("cell").nth(2).textContent().catch(() => null)
      if (text) names.push(text.trim())
    }
    return names
  }

  // ── Entry Management ────────────────────────────────────────────────

  async clickEntriesOnRow(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const entriesBtn = row.getByRole("button", { name: /manage entries|entries|manage/i }).or(
      row.locator("[title*='Entries'], [title*='entries']")
    )
    await entriesBtn.first().click()
  }

  private entryDialog(): Locator {
    return this.page.getByRole("dialog", { name: /entries:/i })
  }

  async fillEntryForm(keywords: string, content: string, priority?: number): Promise<void> {
    const container = this.entryDialog()
    await expect(container).toBeVisible({ timeout: 10_000 })
    const keywordsInput = container.getByRole("combobox", { name: /keywords/i }).first()
    await keywordsInput.click()
    await keywordsInput.fill(keywords)
    await keywordsInput.press("Enter")

    const contentInput = container.locator("textarea").first().or(
      container.getByLabel(/content/i).first()
    )
    await contentInput.fill(content)

    if (priority !== undefined) {
      const priorityInput = container.getByRole("spinbutton", { name: /priority/i }).first()
      if (await priorityInput.isVisible().catch(() => false)) {
        await priorityInput.fill(String(priority))
      }
    }
  }

  async submitEntry(): Promise<void> {
    const container = this.entryDialog()
    const singleEntryButton = container.getByRole("button", { name: /^add entry$/i })
    if (await singleEntryButton.isVisible().catch(() => false)) {
      await singleEntryButton.click()
      return
    }

    const bulkEntryButton = container.getByRole("button", { name: /^add entries$/i })
    await bulkEntryButton.click()
  }

  async getEntryCount(): Promise<number> {
    const container = this.entryDialog()
    const rows = container.locator(".ant-table-row")
    return rows.count()
  }

  async toggleBulkAddMode(): Promise<void> {
    await this.entryDialog().getByLabel(/toggle bulk add mode/i).click()
  }

  async fillBulkText(text: string): Promise<void> {
    const textarea = this.entryDialog().getByLabel(/bulk entry input/i)
    await textarea.fill(text)
  }

  // ── Bulk Operations ─────────────────────────────────────────────────

  async selectEntryCheckboxes(count: number): Promise<void> {
    const checkboxes = this.page.locator(".ant-modal .ant-checkbox, .ant-drawer .ant-checkbox")
    const total = await checkboxes.count()
    for (let i = 0; i < Math.min(count, total); i++) {
      await checkboxes.nth(i).click()
    }
  }

  async clickBulkAction(action: string): Promise<void> {
    const btn = this.page.getByRole("button", { name: new RegExp(action, "i") })
    await btn.click()
  }

  // ── Character Attachment ────────────────────────────────────────────

  async clickLinkOnRow(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const linkBtn = row.getByRole("button", { name: /quick attach characters|link|attach|character/i }).or(
      row.locator("[title*='Link'], [title*='Attach']")
    )
    await linkBtn.first().click()
  }

  async attachToCharacter(characterName: string): Promise<void> {
    const dropdown = this.page.locator(".ant-select").last()
    await dropdown.click()
    await this.page.locator(`.ant-select-item:has-text("${characterName}")`).click()
    const attachBtn = this.page.getByRole("button", { name: /attach|add|link/i }).last()
    await attachBtn.click()
  }

  async clickRelationshipMatrix(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /matrix|relationship/i })
    await btn.click()
  }

  // ── Import / Export ─────────────────────────────────────────────────

  async clickExport(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const exportBtn = row.getByRole("button", { name: /export world book|export/i }).or(
      row.locator("[title*='Export']")
    )
    await exportBtn.first().click()
  }

  async clickImport(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /import/i })
    await btn.click()
  }

  async uploadImportFile(filePath: string): Promise<void> {
    const fileInput = this.page.locator("input[type='file']")
    await fileInput.setInputFiles(filePath)
  }

  async toggleMergeOnConflict(): Promise<void> {
    const toggle = this.page.getByLabel(/merge/i).or(
      this.page.locator("[data-testid*='merge']")
    )
    await toggle.first().click()
  }

  // ── Statistics ──────────────────────────────────────────────────────

  async clickStats(name: string): Promise<void> {
    const row = await this.findWorldBookRow(name)
    const statsBtn = row.getByRole("button", { name: /view world book statistics|stat/i }).or(
      row.locator("[title*='Stat'], [title*='stat']")
    )
    await statsBtn.first().click()
  }

  async getStatsModalContent(): Promise<string> {
    const modal = this.page.getByRole("dialog", { name: /world book statistics/i })
    await modal.waitFor({ state: "visible", timeout: 10_000 })
    return (await modal.textContent()) ?? ""
  }
}
