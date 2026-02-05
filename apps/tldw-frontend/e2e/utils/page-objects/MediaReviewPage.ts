/**
 * Page Object for Multi-Item Media Review workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class MediaReviewPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  // ── Navigation ──────────────────────────────────────────────────────

  async goto(): Promise<void> {
    await this.page.goto("/content-review", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    // Wait for the media list or empty state
    const container = this.page.locator(
      ".ant-table, .ant-empty, [data-testid*='media-list'], .ant-pagination"
    )
    await container.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  // ── API Intercept ───────────────────────────────────────────────────

  async waitForMediaList(): Promise<{ status: number; body: any }> {
    const response = await this.page.waitForResponse(
      (res) =>
        (res.url().includes("/api/v1/media/") || res.url().includes("/api/v1/media?")) &&
        res.request().method() === "GET",
      { timeout: 15_000 }
    )
    const body = await response.json().catch(() => null)
    return { status: response.status(), body }
  }

  async waitForMediaDetail(id?: string | number): Promise<{ status: number; body: any }> {
    const response = await this.page.waitForResponse(
      (res) => {
        const url = res.url()
        const isMediaDetail = id
          ? url.includes(`/api/v1/media/${id}`)
          : /\/api\/v1\/media\/\d+/.test(url) && !url.includes("search")
        return isMediaDetail && res.request().method() === "GET"
      },
      { timeout: 15_000 }
    )
    const body = await response.json().catch(() => null)
    return { status: response.status(), body }
  }

  // ── Item Selection ──────────────────────────────────────────────────

  async getMediaItems(): Promise<Locator> {
    return this.page.locator(
      "[data-testid*='media-item'], .media-item, .ant-table-row"
    )
  }

  async getItemCount(): Promise<number> {
    const items = await this.getMediaItems()
    return items.count()
  }

  async clickItem(index: number): Promise<void> {
    const items = await this.getMediaItems()
    await items.nth(index).click()
  }

  async shiftClickItem(index: number): Promise<void> {
    const items = await this.getMediaItems()
    await items.nth(index).click({ modifiers: ["Shift"] })
  }

  async ctrlClickItem(index: number): Promise<void> {
    const items = await this.getMediaItems()
    await items.nth(index).click({ modifiers: ["Meta"] })
  }

  async getSelectedCount(): Promise<number> {
    // Look for selection indicators
    const selectedItems = this.page.locator(
      "[data-selected='true'], .ring-primary, .ring-2, .ant-checkbox-checked"
    )
    return selectedItems.count()
  }

  async getSelectionCountDisplay(): Promise<string> {
    const countDisplay = this.page.locator(
      "[data-testid*='selection-count'], .selection-count"
    )
    if (await countDisplay.first().isVisible().catch(() => false)) {
      return (await countDisplay.first().textContent()) ?? ""
    }
    return ""
  }

  // ── View Modes ──────────────────────────────────────────────────────

  async setViewMode(mode: "spread" | "list" | "all"): Promise<void> {
    // Ant Design Radio.Group buttons
    const modeLabels: Record<string, string> = {
      spread: "Compare",
      list: "Focus",
      all: "Stack"
    }
    const label = modeLabels[mode]
    const radioBtn = this.page.locator(`.ant-radio-button-wrapper:has-text("${label}")`).or(
      this.page.getByRole("radio", { name: new RegExp(label, "i") })
    )
    await radioBtn.first().click()
  }

  async getCurrentViewMode(): Promise<string> {
    const checked = this.page.locator(".ant-radio-button-wrapper-checked")
    const text = await checked.textContent()
    if (text?.match(/compare/i)) return "spread"
    if (text?.match(/focus/i)) return "list"
    if (text?.match(/stack/i)) return "all"
    return "unknown"
  }

  async setOrientation(orientation: "vertical" | "horizontal"): Promise<void> {
    const radioBtn = this.page.locator(
      `.ant-radio-button-wrapper:has-text("${orientation}")`
    ).or(
      this.page.getByRole("radio", { name: new RegExp(orientation, "i") })
    )
    await radioBtn.first().click()
  }

  // ── Navigation Controls ─────────────────────────────────────────────

  async clickPrevItem(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /prev/i })
    await btn.click()
  }

  async clickNextItem(): Promise<void> {
    const btn = this.page.getByRole("button", { name: /next/i })
    await btn.click()
  }

  async getItemPosition(): Promise<string> {
    const positionText = this.page.locator(
      ":text-matches('Item \\\\d+ of \\\\d+')"
    ).or(this.page.locator(".text-text-muted:has-text('Item')"))
    if (await positionText.first().isVisible().catch(() => false)) {
      return (await positionText.first().textContent()) ?? ""
    }
    return ""
  }

  // ── Filtering & Search ──────────────────────────────────────────────

  async fillSearchQuery(query: string): Promise<void> {
    const input = this.page.locator(
      "[placeholder*='search' i], [placeholder*='filter' i], input[type='search']"
    ).first()
    await input.fill(query)
    await input.press("Enter")
  }

  async filterByMediaType(type: string): Promise<void> {
    // Look for type filter select/dropdown
    const typeSelect = this.page.locator(
      "[data-testid*='type-filter'], .ant-select:has-text('Type')"
    ).first()
    await typeSelect.click()
    await this.page.locator(`.ant-select-item:has-text("${type}")`).click()
  }

  async clearFilters(): Promise<void> {
    const clearBtn = this.page.getByRole("button", { name: /clear|reset/i })
    if (await clearBtn.first().isVisible().catch(() => false)) {
      await clearBtn.first().click()
    }
  }

  // ── Content Interaction ─────────────────────────────────────────────

  async expandContent(index: number = 0): Promise<void> {
    const expandBtns = this.page.locator(
      "[data-testid*='expand-content'], [aria-label*='expand' i]"
    )
    if ((await expandBtns.count()) > index) {
      await expandBtns.nth(index).click()
    }
  }

  async clickCopyButton(index: number = 0): Promise<void> {
    const copyBtns = this.page.locator(
      "[data-testid*='copy'], [aria-label*='copy' i], button:has-text('Copy')"
    )
    if ((await copyBtns.count()) > index) {
      await copyBtns.nth(index).click()
    }
  }

  // ── Viewer Panel ────────────────────────────────────────────────────

  async getViewerItemCount(): Promise<number> {
    const cards = this.page.locator(
      "[data-testid*='review-card'], .review-card, .media-detail-card"
    )
    return cards.count()
  }

  async isViewerEmpty(): Promise<boolean> {
    const empty = this.page.locator(
      ".ant-empty, [data-testid*='empty'], :text('Select items')"
    )
    return (await empty.count()) > 0 && (await empty.first().isVisible().catch(() => false))
  }

  // ── Pagination ──────────────────────────────────────────────────────

  async goToPage(pageNum: number): Promise<void> {
    const pagination = this.page.locator(".ant-pagination")
    const pageBtn = pagination.locator(`[title='${pageNum}'], li:has-text("${pageNum}")`)
    await pageBtn.click()
  }

  async getCurrentPage(): Promise<number> {
    const active = this.page.locator(".ant-pagination-item-active")
    const text = await active.textContent()
    return text ? parseInt(text, 10) : 1
  }

  async getTotalPages(): Promise<number> {
    const pages = this.page.locator(".ant-pagination-item")
    return pages.count()
  }

  // ── Clear Selection / Undo ──────────────────────────────────────────

  async clickClearSelection(): Promise<void> {
    const clearBtn = this.page.getByRole("button", { name: /clear.*session|clear.*selection/i }).or(
      this.page.locator("[data-testid*='clear-selection']")
    )
    await clearBtn.first().click()
  }

  async clickUndo(): Promise<void> {
    const undoBtn = this.page.getByRole("button", { name: /undo/i }).or(
      this.page.locator(".ant-notification").getByText(/undo/i).or(
        this.page.locator(".ant-message").getByText(/undo/i)
      )
    )
    await undoBtn.first().click()
  }

  // ── Error Handling ──────────────────────────────────────────────────

  async hasFailedItems(): Promise<boolean> {
    const failed = this.page.locator(
      "[data-testid*='failed'], .ant-btn-dangerous, [data-status='error']"
    )
    return (await failed.count()) > 0
  }

  async clickRetry(): Promise<void> {
    const retryBtn = this.page.getByRole("button", { name: /retry/i })
    await retryBtn.first().click()
  }

  // ── Keyboard Shortcuts ──────────────────────────────────────────────

  async pressNextItemShortcut(): Promise<void> {
    await this.page.keyboard.press("j")
  }

  async pressPrevItemShortcut(): Promise<void> {
    await this.page.keyboard.press("k")
  }

  async pressToggleExpand(): Promise<void> {
    await this.page.keyboard.press("o")
  }

  async pressSelectAll(): Promise<void> {
    await this.page.keyboard.press("Control+a")
  }

  async pressEscapeTwice(): Promise<void> {
    await this.page.keyboard.press("Escape")
    await this.page.keyboard.press("Escape")
  }

  // ── Options Menu ────────────────────────────────────────────────────

  async openOptionsMenu(): Promise<void> {
    const optionsBtn = this.page.getByRole("button", { name: /options/i })
    await optionsBtn.click()
  }

  async clickOpenAllOnPage(): Promise<void> {
    await this.openOptionsMenu()
    const menuItem = this.page.locator(".ant-dropdown-menu-item:has-text('Review all')")
    await menuItem.click()
  }

  async clickClearSession(): Promise<void> {
    await this.openOptionsMenu()
    const menuItem = this.page.locator(".ant-dropdown-menu-item:has-text('Clear review session')")
    await menuItem.click()
  }
}
