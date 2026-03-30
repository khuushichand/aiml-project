/**
 * Page Object for MCP Hub workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection } from "../helpers"

export class MCPHubPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/mcp-hub", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for MCP Hub heading or any tab content to appear
    const heading = this.page.getByRole("heading", { name: /mcp hub/i })
    await heading.first().waitFor({ state: "visible", timeout: 20_000 }).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** MCP Hub heading */
  get heading(): Locator {
    return this.page.getByRole("heading", { name: /mcp hub/i })
  }

  /** Profiles tab */
  get profilesTab(): Locator {
    return this.page.getByRole("tab", { name: /profiles/i })
  }

  /** Assignments tab */
  get assignmentsTab(): Locator {
    return this.page.getByRole("tab", { name: /assignments/i })
  }

  /** Path Scopes tab */
  get pathScopesTab(): Locator {
    return this.page.getByRole("tab", { name: /path scopes/i })
  }

  /** Workspace Sets tab */
  get workspaceSetsTab(): Locator {
    return this.page.getByRole("tab", { name: /workspace sets/i })
  }

  /** Shared Workspaces tab */
  get sharedWorkspacesTab(): Locator {
    return this.page.getByRole("tab", { name: /shared workspaces/i })
  }

  /** Audit tab */
  get auditTab(): Locator {
    return this.page.getByRole("tab", { name: /^audit$/i })
  }

  /** Approvals tab */
  get approvalsTab(): Locator {
    return this.page.getByRole("tab", { name: /approvals/i })
  }

  /** Catalog tab */
  get catalogTab(): Locator {
    return this.page.getByRole("tab", { name: /catalog/i })
  }

  /** Credentials tab */
  get credentialsTab(): Locator {
    return this.page.getByRole("tab", { name: /credentials/i })
  }

  // -- Helpers ---------------------------------------------------------------

  /** All available tab keys */
  static readonly TAB_KEYS = [
    "profiles",
    "assignments",
    "pathScopes",
    "workspaceSets",
    "sharedWorkspaces",
    "audit",
    "approvals",
    "catalog",
    "credentials",
  ] as const

  /** Switch to a specific tab */
  async switchToTab(
    tab:
      | "profiles"
      | "assignments"
      | "pathScopes"
      | "workspaceSets"
      | "sharedWorkspaces"
      | "audit"
      | "approvals"
      | "catalog"
      | "credentials"
  ): Promise<void> {
    const tabLocator = {
      profiles: this.profilesTab,
      assignments: this.assignmentsTab,
      pathScopes: this.pathScopesTab,
      workspaceSets: this.workspaceSetsTab,
      sharedWorkspaces: this.sharedWorkspacesTab,
      audit: this.auditTab,
      approvals: this.approvalsTab,
      catalog: this.catalogTab,
      credentials: this.credentialsTab,
    }[tab]
    await tabLocator.click()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Profiles tab",
        locator: this.profilesTab,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/mcp\/hub\/permission-profiles/,
          method: "GET",
        },
      },
      {
        name: "Assignments tab",
        locator: this.assignmentsTab,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/mcp\/hub\/policy-assignments/,
          method: "GET",
        },
      },
      {
        name: "Catalog tab",
        locator: this.catalogTab,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/mcp\/hub\/tool-registry/,
          method: "GET",
        },
      },
    ]
  }
}
