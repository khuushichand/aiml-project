/**
 * Page Object for Data Tables Studio workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection } from "../helpers"

export class DataTablesPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/data-tables", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for heading or the offline empty state
    const heading = this.page.getByText("Data Tables Studio")
    const offline = this.page.getByText("Server is offline. Please connect to use Data Tables.")
    await Promise.race([
      heading.first().waitFor({ state: "visible", timeout: 20_000 }),
      offline.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  get heading(): Locator {
    return this.page.getByRole("heading", { name: /data tables studio/i })
  }

  get offlineMessage(): Locator {
    return this.page.getByText("Server is offline. Please connect to use Data Tables.")
  }

  get description(): Locator {
    return this.page.getByText(
      "Generate structured tables from your chats, documents, and knowledge base using natural language prompts."
    )
  }

  /** Beta notice alert */
  get betaAlert(): Locator {
    return this.page.getByText("Beta Feature")
  }

  /** My Tables tab */
  get myTablesTab(): Locator {
    return this.page.getByRole("tab", { name: /my tables/i })
  }

  /** Create Table tab */
  get createTableTab(): Locator {
    return this.page.getByRole("tab", { name: /create table/i })
  }

  /** Search input in the My Tables list */
  get searchInput(): Locator {
    return this.page.getByPlaceholder(/search/i).first()
  }

  /** Refresh button in the My Tables list */
  get refreshButton(): Locator {
    return this.page.getByRole("button", { name: /refresh/i })
  }

  /** Empty state when no tables exist */
  get emptyState(): Locator {
    return this.page.getByText("No tables yet. Create your first table!")
  }

  /** No search results state */
  get noSearchResults(): Locator {
    return this.page.getByText("No tables found matching your search")
  }

  // -- Tab Navigation --------------------------------------------------------

  async switchToTab(tab: "tables" | "create"): Promise<void> {
    const tabLocator = {
      tables: this.myTablesTab,
      create: this.createTableTab,
    }[tab]
    await tabLocator.click()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Refresh tables button",
        locator: this.refreshButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/data-tables/,
          method: "GET",
        },
      },
    ]
  }
}
