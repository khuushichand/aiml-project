/**
 * Page Object for Media functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class MediaPage {
  readonly page: Page
  readonly heading: Locator
  readonly uploadButton: Locator
  readonly urlInput: Locator
  readonly processButton: Locator
  readonly mediaList: Locator
  readonly searchInput: Locator
  readonly reviewStatusBar: Locator
  readonly reviewResultsList: Locator
  readonly reviewResultsHeading: Locator
  readonly reviewResultItems: Locator
  readonly reviewEmptyState: Locator

  constructor(page: Page) {
    this.page = page
    this.heading = page.getByRole("heading", { name: /media inspector/i })
    this.uploadButton = page.getByRole("button", { name: /upload|add file/i })
    this.urlInput = page.getByPlaceholder(/url|enter url/i)
    this.processButton = page.getByRole("button", { name: /process|ingest|add/i })
    this.mediaList = page
      .getByTestId("media-results-list")
      .or(page.locator("button[aria-label^='Select media:']").first())
    this.searchInput = page
      .getByRole("textbox", { name: /search media/i })
      .or(page.getByPlaceholder(/search media/i))
      .first()
    this.reviewStatusBar = page.getByTestId("media-review-status-bar")
    this.reviewResultsList = page.getByTestId("media-review-results-list")
    this.reviewResultsHeading = page.getByRole("heading", { name: /^results/i }).first()
    this.reviewResultItems = page.getByRole("button").filter({
      has: page.locator("input[type='checkbox'], [role='checkbox']")
    })
    this.reviewEmptyState = page.getByText(/^No results$/i).first()
  }

  /**
   * Navigate to the media page
   */
  async goto(): Promise<void> {
    await this.page.goto("/media", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Wait for the media page to be ready
   */
  async waitForReady(): Promise<void> {
    await Promise.race([
      this.heading.waitFor({ state: "visible", timeout: 20_000 }),
      this.searchInput.waitFor({ state: "visible", timeout: 20_000 }),
      this.mediaList.waitFor({ state: "visible", timeout: 20_000 })
    ])
  }

  /**
   * Upload a file
   */
  async uploadFile(filePath: string): Promise<void> {
    // Find file input
    const fileInput = this.page.locator("input[type='file']")

    // Set the file
    await fileInput.setInputFiles(filePath)
  }

  /**
   * Upload multiple files
   */
  async uploadFiles(filePaths: string[]): Promise<void> {
    const fileInput = this.page.locator("input[type='file']")
    await fileInput.setInputFiles(filePaths)
  }

  /**
   * Ingest content from a URL
   */
  async ingestFromUrl(url: string): Promise<void> {
    // Look for URL input field
    const urlInputCandidates = [
      this.page.getByPlaceholder(/url|paste url|enter url/i),
      this.page.getByLabel(/url/i),
      this.page.getByTestId("url-input")
    ]

    let urlInput: Locator | null = null
    for (const candidate of urlInputCandidates) {
      if ((await candidate.count()) > 0) {
        urlInput = candidate.first()
        break
      }
    }

    if (!urlInput) {
      throw new Error("URL input field not found")
    }

    await urlInput.fill(url)

    // Find and click process/ingest button
    const processBtn = this.page.getByRole("button", {
      name: /process|ingest|add|submit/i
    })
    await processBtn.click()
  }

  /**
   * Wait for processing to complete
   */
  async waitForProcessingComplete(timeoutMs = 120000): Promise<boolean> {
    // Wait for success indicator or processing to complete
    const successIndicator = this.page.locator(
      "[data-status='completed'], [data-status='success'], .processing-complete"
    )
    const errorIndicator = this.page.locator(
      "[data-status='error'], [data-status='failed'], .processing-error"
    )

    try {
      await expect(successIndicator.or(errorIndicator).first()).toBeVisible({
        timeout: timeoutMs
      })

      // Check if it was successful
      return (await successIndicator.count()) > 0
    } catch {
      return false
    }
  }

  /**
   * Get progress status
   */
  async getProgressStatus(): Promise<{
    status: "idle" | "processing" | "completed" | "error"
    progress?: number
    message?: string
  }> {
    const progressBar = this.page.locator(
      "[data-testid='progress-bar'], .ant-progress, .progress"
    )
    const statusText = this.page.locator(
      "[data-testid='status-text'], .status-message"
    )

    let status: "idle" | "processing" | "completed" | "error" = "idle"
    let progress: number | undefined
    let message: string | undefined

    if ((await progressBar.count()) > 0) {
      const progressValue = await progressBar.getAttribute("aria-valuenow")
      if (progressValue) {
        progress = parseInt(progressValue, 10)
        status = progress >= 100 ? "completed" : "processing"
      }
    }

    if ((await statusText.count()) > 0) {
      message = (await statusText.textContent()) ?? undefined
      if (message?.toLowerCase().includes("error")) {
        status = "error"
      } else if (message?.toLowerCase().includes("complete")) {
        status = "completed"
      }
    }

    return { status, progress, message }
  }

  /**
   * Edit media metadata
   */
  async editMetadata(fields: {
    title?: string
    keywords?: string[]
    tags?: string[]
    description?: string
  }): Promise<void> {
    // Find edit button or metadata form
    const editBtn = this.page.getByRole("button", { name: /edit|modify/i })
    if ((await editBtn.count()) > 0) {
      await editBtn.first().click()
    }

    if (fields.title) {
      const titleInput = this.page.getByLabel(/title/i)
      await titleInput.fill(fields.title)
    }

    if (fields.description) {
      const descInput = this.page.getByLabel(/description|summary/i)
      await descInput.fill(fields.description)
    }

    if (fields.keywords && fields.keywords.length > 0) {
      const keywordsInput = this.page.getByLabel(/keywords/i)
      await keywordsInput.fill(fields.keywords.join(", "))
    }

    if (fields.tags && fields.tags.length > 0) {
      const tagsInput = this.page.getByLabel(/tags/i)
      await tagsInput.fill(fields.tags.join(", "))
    }

    // Save changes
    const saveBtn = this.page.getByRole("button", { name: /save|update/i })
    await saveBtn.click()
  }

  /**
   * Search media items
   */
  async searchMedia(query: string): Promise<void> {
    const searchInput = this.page.getByPlaceholder(/search|filter/i)
    await searchInput.fill(query)
    await searchInput.press("Enter")
  }

  /**
   * Get list of media items
   */
  async getMediaItems(): Promise<
    Array<{ title: string; type?: string; date?: string }>
  > {
    const items: Array<{ title: string; type?: string; date?: string }> = []

    const mediaItems = this.page.locator(
      "[data-testid='media-item'], .media-item, .ant-table-row"
    )
    const count = await mediaItems.count()

    for (let i = 0; i < count; i++) {
      const item = mediaItems.nth(i)
      const title =
        (await item.locator(".title, [data-field='title']").textContent()) ||
        (await item.textContent()) ||
        ""
      const type =
        (await item.locator(".type, [data-field='type']").textContent()) ?? undefined
      const date =
        (await item.locator(".date, [data-field='date']").textContent()) ?? undefined

      items.push({ title: title.trim(), type: type?.trim(), date: date?.trim() })
    }

    return items
  }

  /**
   * Delete a media item
   */
  async deleteItem(titleOrIndex: string | number): Promise<void> {
    let item: Locator

    if (typeof titleOrIndex === "number") {
      const mediaItems = this.page.locator(
        "[data-testid='media-item'], .media-item"
      )
      item = mediaItems.nth(titleOrIndex)
    } else {
      item = this.page.locator(
        `[data-testid='media-item']:has-text("${titleOrIndex}")`
      )
    }

    // Find delete button within item
    const deleteBtn = item.getByRole("button", { name: /delete|remove|trash/i })
    await deleteBtn.click()

    // Confirm deletion if dialog appears
    const confirmBtn = this.page.getByRole("button", { name: /confirm|yes|delete/i })
    if ((await confirmBtn.count()) > 0) {
      await confirmBtn.click()
    }
  }

  /**
   * Open Quick Ingest modal
   */
  async openQuickIngest(): Promise<Locator> {
    const modal = this.page.getByRole("dialog", { name: /Quick Ingest/i }).first()
    if (await modal.isVisible().catch(() => false)) return modal

    // Try different triggers
    const triggers = [
      this.page.getByTestId("open-quick-ingest"),
      this.page.getByRole("button", { name: /Quick ingest/i })
    ]

    for (const trigger of triggers) {
      if ((await trigger.count()) > 0 && (await trigger.first().isVisible())) {
        await trigger.first().click()
        if (await modal.isVisible().catch(() => false)) return modal
      }
    }

    // Fallback: dispatch custom event
    await this.page.evaluate(() => {
      window.dispatchEvent(new CustomEvent("tldw:open-quick-ingest"))
    })

    await expect(modal).toBeVisible({ timeout: 15000 })
    await expect(modal.locator('[data-testid="qi-file-input"]').first()).toHaveCount(1, {
      timeout: 20000,
    })
    return modal
  }

  /**
   * Navigate to content review page
   */
  async gotoReview(): Promise<void> {
    await this.page.goto("/review", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Wait for the content review surface to reach a stable visible state.
   */
  async waitForReviewReady(): Promise<void> {
    await Promise.race([
      this.reviewStatusBar.waitFor({ state: "visible", timeout: 20_000 }),
      this.reviewResultsHeading.waitFor({ state: "visible", timeout: 20_000 }),
      this.reviewEmptyState.waitFor({ state: "visible", timeout: 20_000 })
    ])
  }

  /**
   * Get draft items from review page
   */
  async getDraftItems(): Promise<Array<{ title: string; status: string }>> {
    await this.waitForReviewReady()

    const items: Array<{ title: string; status: string }> = []
    const draftItems = this.reviewResultItems
    const count = await draftItems.count()

    for (let i = 0; i < count; i++) {
      const item = draftItems.nth(i)
      const itemLines = (await item.innerText())
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
      const title = itemLines[0] ?? ""
      const status = itemLines[1] ?? "draft"

      items.push({ title: title.trim(), status })
    }

    return items
  }
}
