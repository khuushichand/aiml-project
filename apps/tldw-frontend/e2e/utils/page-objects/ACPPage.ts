/**
 * Page Object for ACP Playground workflow
 *
 * The ACP Playground provides an Agent Client Protocol interface with:
 * - Left pane: Session list and creation
 * - Center: Agent chat/conversation view
 * - Right pane: Tools and workspace panels (tabbed)
 * - Permission modal for pending tool approvals
 *
 * Route: /acp-playground
 * Component: packages/ui/src/components/Option/ACPPlayground/index.tsx
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class ACPPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/acp-playground", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    // Wait for the header title "Agent Playground" or session panel to appear
    const heading = this.page.getByText("Agent Playground")
    const sessionsLabel = this.page.getByText("Sessions")
    await Promise.race([
      heading.first().waitFor({ state: "visible", timeout: 20_000 }),
      sessionsLabel.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** Main header title */
  get heading(): Locator {
    return this.page.getByRole("heading", { name: /agent playground/i })
  }

  /** Header subtitle */
  get subtitle(): Locator {
    return this.page.getByText("Interact with AI coding agents via ACP")
  }

  /** Sessions panel heading */
  get sessionsHeading(): Locator {
    return this.page.getByText("Sessions", { exact: true }).first()
  }

  /** New Session button (Plus icon in the session panel header) */
  get newSessionButton(): Locator {
    return this.page.getByRole("button", { name: /new session/i })
  }

  /** Create Session button (in the empty state) */
  get createSessionButton(): Locator {
    return this.page.getByRole("button", { name: /create session/i })
  }

  /** Session search input */
  get sessionSearchInput(): Locator {
    return this.page.getByPlaceholder(/search sessions/i)
  }

  /** Session state filter dropdown */
  get stateFilterSelect(): Locator {
    return this.page.locator("[data-testid='acp-session-filter-state']")
  }

  /** Session sort dropdown */
  get sortSelect(): Locator {
    return this.page.locator("[data-testid='acp-session-sort']")
  }

  /** No active sessions empty state */
  get noSessionsMessage(): Locator {
    return this.page.getByText("No active sessions")
  }

  /** Session items in the list */
  get sessionItems(): Locator {
    return this.page.locator("[data-testid='acp-session-item']")
  }

  /** Left pane toggle button (show/hide sessions) */
  get leftPaneToggle(): Locator {
    return this.page.getByRole("button", { name: /show sessions|hide sessions/i })
  }

  /** Right pane toggle button (show/hide tools) */
  get rightPaneToggle(): Locator {
    return this.page.getByRole("button", { name: /show tools|hide tools/i })
  }

  /** Tools tab in the right pane */
  get toolsTab(): Locator {
    return this.page.getByRole("tab", { name: /tools/i })
  }

  /** Workspace tab in the right pane */
  get workspaceTab(): Locator {
    return this.page.getByRole("tab", { name: /workspace/i })
  }

  /** Refresh sessions button */
  get refreshSessionsButton(): Locator {
    return this.page.getByRole("button", { name: /refresh sessions/i })
  }

  // -- Mobile-specific locators -----------------------------------------------

  /** Sessions tab (mobile) */
  get mobileSessionsTab(): Locator {
    return this.page.getByRole("tab", { name: /sessions/i })
  }

  /** Chat tab (mobile) */
  get mobileChatTab(): Locator {
    return this.page.getByRole("tab", { name: /chat/i })
  }

  // -- Helpers ----------------------------------------------------------------

  /** Check if the page is in "no sessions" empty state */
  async isEmptyState(): Promise<boolean> {
    return this.noSessionsMessage.isVisible().catch(() => false)
  }

  /** Get the count of visible session items */
  async getSessionCount(): Promise<number> {
    return this.sessionItems.count()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Create Session button (empty state)",
        locator: this.createSessionButton,
        expectation: {
          type: "modal",
          modalSelector: ".ant-modal",
        },
      },
      {
        name: "Refresh sessions button",
        locator: this.refreshSessionsButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/acp\/sessions/,
          method: "GET",
        },
      },
    ]
  }
}
