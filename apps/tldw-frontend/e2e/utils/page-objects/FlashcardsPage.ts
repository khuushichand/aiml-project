/**
 * Page Object for the Flashcards workspace
 *
 * The route renders FlashcardsWorkspace which shows either:
 * - A connection/offline banner when the server is unreachable
 * - FlashcardsManager with three tabs: Study, Manage, Transfer
 *
 * API base paths:
 *   /api/v1/flashcards        (cards CRUD, review, generate, import, export)
 *   /api/v1/flashcards/decks  (deck CRUD)
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection, dismissConnectionModals } from "../helpers"

export class FlashcardsPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/flashcards", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Either the tabs container is visible (online) or a connection banner
    const tabs = this.page.locator('[data-testid="flashcards-tabs"]')
    const offline = this.page.getByText("Connect to use Flashcards")
    const unsupported = this.page.getByText("Flashcards API not available")
    await Promise.race([
      tabs.waitFor({ state: "visible", timeout: 20_000 }),
      offline.first().waitFor({ state: "visible", timeout: 20_000 }),
      unsupported.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators: Top-level ---------------------------------------------------

  /** The Ant Design Tabs container wrapping Study / Manage / Transfer */
  get tabsContainer(): Locator {
    return this.page.locator('[data-testid="flashcards-tabs"]')
  }

  /** Offline / not-connected banner */
  get offlineMessage(): Locator {
    return this.page.getByText("Connect to use Flashcards")
  }

  /** Feature-unavailable banner */
  get unsupportedMessage(): Locator {
    return this.page.getByText("Flashcards API not available")
  }

  // -- Locators: Tab buttons -------------------------------------------------

  get studyTab(): Locator {
    return this.page.getByRole("tab", { name: /study/i })
  }

  get manageTab(): Locator {
    return this.page.getByRole("tab", { name: /manage/i })
  }

  get transferTab(): Locator {
    return this.page.getByRole("tab", { name: /transfer/i })
  }

  // -- Locators: Tab bar extra content ---------------------------------------

  /** "Test with Quiz" CTA button in the tab bar */
  get testWithQuizButton(): Locator {
    return this.page.locator('[data-testid="flashcards-to-quiz-cta"]')
  }

  /** Keyboard shortcuts help button (icon-only) */
  get keyboardShortcutsButton(): Locator {
    return this.page.getByRole("button", { name: /keyboard shortcuts/i })
  }

  // -- Locators: Study (Review) tab ------------------------------------------

  get reviewDeckSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-review-deck-select"]')
  }

  get reviewModeToggle(): Locator {
    return this.page.locator('[data-testid="flashcards-review-mode-toggle"]')
  }

  get reviewActiveCard(): Locator {
    return this.page.locator('[data-testid="flashcards-review-active-card"]')
  }

  get reviewShowAnswerButton(): Locator {
    return this.page.locator('[data-testid="flashcards-review-show-answer"]')
  }

  get reviewEmptyCard(): Locator {
    return this.page.locator('[data-testid="flashcards-review-empty-card"]')
  }

  get reviewAnalyticsSummary(): Locator {
    return this.page.locator('[data-testid="flashcards-review-analytics-summary"]')
  }

  get reviewCreateCta(): Locator {
    return this.page.locator('[data-testid="flashcards-review-empty-create-cta"]')
  }

  get reviewImportCta(): Locator {
    return this.page.locator('[data-testid="flashcards-review-empty-import-cta"]')
  }

  // -- Locators: Manage tab --------------------------------------------------

  get manageTopBar(): Locator {
    return this.page.locator('[data-testid="flashcards-manage-topbar"]')
  }

  get manageSearchInput(): Locator {
    return this.page.locator('[data-testid="flashcards-manage-search"] input')
  }

  get manageDeckSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-manage-deck-select"]')
  }

  get manageDueStatusFilter(): Locator {
    return this.page.locator('[data-testid="flashcards-manage-due-status"]')
  }

  get manageSortSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-manage-sort-select"]')
  }

  get fabCreateButton(): Locator {
    return this.page.locator('[data-testid="flashcards-fab-create"]')
  }

  // -- Locators: Transfer (Import/Export) tab --------------------------------

  get importFormatSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-import-format"]')
  }

  get importTextarea(): Locator {
    return this.page.locator('[data-testid="flashcards-import-textarea"]')
  }

  get importButton(): Locator {
    return this.page.locator('[data-testid="flashcards-import-button"]')
  }

  get exportDeckSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-export-deck"]')
  }

  get exportFormatSelect(): Locator {
    return this.page.locator('[data-testid="flashcards-export-format"]')
  }

  get exportButton(): Locator {
    return this.page.locator('[data-testid="flashcards-export-button"]')
  }

  get generateTextarea(): Locator {
    return this.page.locator('[data-testid="flashcards-generate-text"]')
  }

  get generateButton(): Locator {
    return this.page.locator('[data-testid="flashcards-generate-button"]')
  }

  // -- Tab Navigation --------------------------------------------------------

  async switchToTab(tab: "study" | "manage" | "transfer"): Promise<void> {
    // Dismiss any overlays that might intercept clicks
    await dismissConnectionModals(this.page)
    const tabLocator = {
      study: this.studyTab,
      manage: this.manageTab,
      transfer: this.transferTab,
    }[tab]
    await tabLocator.click({ force: true })
  }

  /** Returns true when the main tabs container is visible (server online + feature available) */
  async isOnline(): Promise<boolean> {
    return await this.tabsContainer.isVisible().catch(() => false)
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Export flashcards button",
        locator: this.exportButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/flashcards\/export/,
          method: "GET",
        },
        setup: async () => {
          await this.switchToTab("transfer")
          await expect(this.importTextarea.or(this.exportDeckSelect)).toBeVisible({ timeout: 5_000 })
        },
      },
      {
        name: "Import flashcards button",
        locator: this.importButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/flashcards\/import/,
          method: "POST",
        },
        setup: async () => {
          await this.switchToTab("transfer")
          await expect(this.importTextarea.or(this.exportDeckSelect)).toBeVisible({ timeout: 5_000 })
        },
      },
    ]
  }
}
