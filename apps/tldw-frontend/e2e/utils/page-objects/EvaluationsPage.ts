/**
 * Page Object for Evaluations functionality
 *
 * Extends BasePage. Wraps the EvaluationsPage component which includes:
 * - Tabbed interface (Evaluations, Runs, Datasets, Webhooks, History)
 * - Create evaluation wizard
 * - Run evaluation actions
 */
import { type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class EvaluationsPage extends BasePage {
  private tabTrigger(tabLabel: Locator): Locator {
    return tabLabel.locator("xpath=ancestor-or-self::*[@role='tab'][1]").first()
  }

  /* ------------------------------------------------------------------ */
  /* Locators                                                            */
  /* ------------------------------------------------------------------ */

  /** Page title heading */
  get pageTitle(): Locator {
    return this.page.getByTestId("evaluations-page-title")
  }

  /** Evaluations tab trigger */
  get evaluationsTab(): Locator {
    return this.page.getByTestId("evaluations-tab-evaluations")
  }

  /** Runs tab trigger */
  get runsTab(): Locator {
    return this.page.getByTestId("evaluations-tab-runs")
  }

  /** Datasets tab trigger */
  get datasetsTab(): Locator {
    return this.page.getByTestId("evaluations-tab-datasets")
  }

  /** Webhooks tab trigger */
  get webhooksTab(): Locator {
    return this.page.getByTestId("evaluations-tab-webhooks")
  }

  /** History tab trigger */
  get historyTab(): Locator {
    return this.page.getByTestId("evaluations-tab-history")
  }

  /** "Create evaluation" or "New evaluation" button */
  get createEvaluationButton(): Locator {
    return this.page.getByTestId("evaluations-create-button")
  }

  /** Create/edit evaluation modal */
  get createEvaluationModal(): Locator {
    return this.page.getByRole("dialog", { name: /new evaluation|edit evaluation/i })
  }

  /** "Run" button (triggers an evaluation run) */
  get runButton(): Locator {
    return this.page.getByRole("button", { name: /run/i }).first()
  }

  /* ------------------------------------------------------------------ */
  /* BasePage overrides                                                  */
  /* ------------------------------------------------------------------ */

  async goto(): Promise<void> {
    await this.page.goto("/evaluations", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: 20_000 })
    await expect(this.evaluationsTab).toBeVisible({ timeout: 10_000 })
  }

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Evaluations tab",
        locator: this.evaluationsTab,
        expectation: {
          type: "state_change",
          stateCheck: async () => {
            return this.page.url()
          },
        },
      },
      {
        name: "Runs tab",
        locator: this.runsTab,
        expectation: {
          type: "state_change",
          stateCheck: async () => {
            return this.page.url()
          },
        },
      },
    ]
  }

  /* ------------------------------------------------------------------ */
  /* High-level actions                                                  */
  /* ------------------------------------------------------------------ */

  /**
   * Trigger an evaluation run by clicking the run button.
   * Expects the caller to set up an API call expectation beforehand.
   */
  async runEvaluation(): Promise<void> {
    // Ensure we are on the evaluations tab
    const evalTabLabel = this.evaluationsTab
    const evalTab = this.tabTrigger(evalTabLabel)
    if (await evalTabLabel.isVisible()) {
      await evalTab.click()
      await expect(evalTab).toHaveAttribute("aria-selected", "true", { timeout: 5_000 })
    }

    // Click "Create" or "New" to open the wizard/form if the run button isn't visible yet
    const runVisible = await this.runButton.isVisible().catch(() => false)
    if (!runVisible) {
      const createVisible = await this.createEvaluationButton.isVisible().catch(() => false)
      if (createVisible) {
        await this.createEvaluationButton.click()
        await expect(this.runButton.or(this.page.getByRole("dialog"))).toBeVisible({ timeout: 5_000 })
      }
    }

    // Click the run button if it becomes visible
    const runBtn = this.runButton
    if (await runBtn.isVisible().catch(() => false)) {
      await runBtn.click()
    }
  }

  async openCreateEvaluation(): Promise<void> {
    await expect(this.createEvaluationButton).toBeVisible({ timeout: 10_000 })
    await this.createEvaluationButton.click()
    await expect(this.createEvaluationModal).toBeVisible({ timeout: 10_000 })
  }

  /**
   * Switch to a specific tab by clicking its trigger.
   */
  async switchTab(tab: "evaluations" | "runs" | "datasets" | "webhooks" | "history"): Promise<void> {
    const tabLocators: Record<string, Locator> = {
      evaluations: this.evaluationsTab,
      runs: this.runsTab,
      datasets: this.datasetsTab,
      webhooks: this.webhooksTab,
      history: this.historyTab,
    }
    const tabLabel = tabLocators[tab]
    const tabTrigger = this.tabTrigger(tabLabel)
    await expect(tabLabel).toBeVisible({ timeout: 10_000 })
    await tabTrigger.click()
    await expect(tabTrigger).toHaveAttribute("aria-selected", "true", { timeout: 5_000 })
  }
}
