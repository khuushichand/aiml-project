/**
 * Page Object for Chat Workflows page
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection } from "../helpers"

export class ChatWorkflowsPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/chat-workflows", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for heading or connection gate offline message
    const heading = this.page.getByRole("heading", { name: /chat workflows/i })
    const connectionGate = this.page.getByText("Chat Workflows depends on your connected tldw server")
    await Promise.race([
      heading.first().waitFor({ state: "visible", timeout: 20_000 }),
      connectionGate.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** Main page heading */
  get heading(): Locator {
    return this.page.getByRole("heading", { name: /chat workflows/i })
  }

  /** Connection gate message (offline) */
  get connectionGateMessage(): Locator {
    return this.page.getByText("Chat Workflows depends on your connected tldw server")
  }

  /** Structured QA badge */
  get structuredQaBadge(): Locator {
    return this.page.getByText("Structured QA")
  }

  /** Beta alert */
  get betaAlert(): Locator {
    return this.page.getByText("Beta feature")
  }

  /** New Template button */
  get newTemplateButton(): Locator {
    return this.page.getByRole("button", { name: /new template/i })
  }

  /** Use Socratic Dialogue button */
  get socraticDialogueButton(): Locator {
    return this.page.getByRole("button", { name: /use socratic dialogue/i })
  }

  /** Open Generator button */
  get openGeneratorButton(): Locator {
    return this.page.getByRole("button", { name: /open generator/i })
  }

  /** Library tab */
  get libraryTab(): Locator {
    return this.page.getByRole("tab", { name: /library/i })
  }

  /** Builder tab */
  get builderTab(): Locator {
    return this.page.getByRole("tab", { name: /builder/i })
  }

  /** Generate tab */
  get generateTab(): Locator {
    return this.page.getByRole("tab", { name: /generate/i })
  }

  /** Run tab */
  get runTab(): Locator {
    return this.page.getByRole("tab", { name: /run/i })
  }

  /** Empty state in library */
  get libraryEmpty(): Locator {
    return this.page.getByText("No chat workflow templates yet")
  }

  /** Template cards in library */
  get templateCards(): Locator {
    return this.page.locator(".ant-card").filter({ hasText: /steps/ })
  }

  /** Edit in Builder buttons */
  get editInBuilderButtons(): Locator {
    return this.page.getByRole("button", { name: /edit in builder/i })
  }

  /** Load as Copy buttons */
  get loadAsCopyButtons(): Locator {
    return this.page.getByRole("button", { name: /load as copy/i })
  }

  /** Start Run buttons */
  get startRunButtons(): Locator {
    return this.page.getByRole("button", { name: /start run/i })
  }

  /** Save Template button (in builder tab) */
  get saveTemplateButton(): Locator {
    return this.page.getByRole("button", { name: /save template/i })
  }

  /** Reset Draft button (in builder tab) */
  get resetDraftButton(): Locator {
    return this.page.getByRole("button", { name: /reset draft/i })
  }

  // -- Tab Navigation --------------------------------------------------------

  async switchToTab(tab: "library" | "builder" | "generate" | "run"): Promise<void> {
    const tabLocator = {
      library: this.libraryTab,
      builder: this.builderTab,
      generate: this.generateTab,
      run: this.runTab,
    }[tab]
    await tabLocator.click()
  }

  // -- Helpers ---------------------------------------------------------------

  /** Check if offline connection gate is showing */
  async isOffline(): Promise<boolean> {
    return this.connectionGateMessage.isVisible().catch(() => false)
  }

  /** Get number of template cards in library */
  async getTemplateCount(): Promise<number> {
    return this.templateCards.count()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "New Template button",
        locator: this.newTemplateButton,
        expectation: {
          type: "state_change",
          stateCheck: async (page: Page) => {
            // Clicking switches to builder tab
            const builderVisible = await page.getByRole("tab", { name: /builder/i })
              .getAttribute("aria-selected")
              .catch(() => "false")
            return builderVisible
          },
        },
      },
    ]
  }
}
