/**
 * Page Object for Agent Registry workflow
 *
 * The Agent Registry page displays:
 * - ACP System Health card (runner binary, agent status, API keys)
 * - Registered Agents card with agent cards showing name, status, launch button
 * - Refresh button to reload health and agent data
 *
 * Route: /agents
 * Component: packages/ui/src/components/Option/AgentRegistry/index.tsx
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class AgentRegistryPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/agents", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    // Wait for the health card or agent list card to appear
    const healthCard = this.page.getByText("ACP System Health")
    const agentCard = this.page.getByText("Registered Agents")
    const healthWarning = this.page.getByText("Health check unavailable")
    await Promise.race([
      healthCard.first().waitFor({ state: "visible", timeout: 20_000 }),
      agentCard.first().waitFor({ state: "visible", timeout: 20_000 }),
      healthWarning.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** ACP System Health card title */
  get healthCardTitle(): Locator {
    return this.page.getByText("ACP System Health")
  }

  /** Registered Agents card title */
  get agentsCardTitle(): Locator {
    return this.page.getByText("Registered Agents")
  }

  /** Refresh button in the health card */
  get refreshButton(): Locator {
    return this.page.getByRole("button", { name: /refresh/i })
  }

  /** Runner Binary status label */
  get runnerBinaryLabel(): Locator {
    return this.page.getByText("Runner Binary")
  }

  /** Agent Status label */
  get agentStatusLabel(): Locator {
    return this.page.getByText("Agent Status")
  }

  /** API Keys status label */
  get apiKeysLabel(): Locator {
    return this.page.getByText("API Keys")
  }

  /** Health check unavailable warning */
  get healthUnavailableWarning(): Locator {
    return this.page.getByText("Health check unavailable")
  }

  /** No agents registered empty state */
  get noAgentsMessage(): Locator {
    return this.page.getByText("No agents registered")
  }

  /** Agent cards in the grid */
  get agentCards(): Locator {
    return this.page.locator(".rounded-lg.border.border-border.p-4")
  }

  /** Launch buttons on agent cards */
  get launchButtons(): Locator {
    return this.page.getByRole("button", { name: /launch/i })
  }

  // -- Helpers ----------------------------------------------------------------

  /** Check if health data loaded successfully (status indicators are visible) */
  async isHealthDataLoaded(): Promise<boolean> {
    const runnerVisible = await this.runnerBinaryLabel.isVisible().catch(() => false)
    const agentVisible = await this.agentStatusLabel.isVisible().catch(() => false)
    return runnerVisible && agentVisible
  }

  /** Get the count of visible agent cards */
  async getAgentCount(): Promise<number> {
    return this.agentCards.count()
  }

  /** Check if the page is showing health warning (server unreachable) */
  async isHealthUnavailable(): Promise<boolean> {
    return this.healthUnavailableWarning.isVisible().catch(() => false)
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Refresh button",
        locator: this.refreshButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/acp\//,
          method: "GET",
        },
      },
    ]
  }
}
