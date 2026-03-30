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
  get recipesTab(): Locator {
    return this.page.getByTestId("evaluations-tab-recipes")
  }

  /** Evaluations tab trigger */
  get evaluationsTab(): Locator {
    return this.page.getByTestId("evaluations-tab-evaluations")
  }

  /** Synthetic review tab trigger */
  get syntheticReviewTab(): Locator {
    return this.page.getByTestId("evaluations-tab-synthetic-review")
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

  get recipeUseButtons(): Locator {
    return this.page.getByRole("button", { name: /^Use / })
  }

  recipeUseButton(recipeName: string): Locator {
    return this.page.getByRole("button", { name: `Use ${recipeName}` })
  }

  get validateDatasetButton(): Locator {
    return this.page.getByRole("button", { name: "Validate dataset" })
  }

  get runRecipeButton(): Locator {
    return this.page.getByRole("button", { name: /Run recipe|Try matching run/ })
  }

  get recipeValidationAlert(): Locator {
    return this.page.getByText(/Dataset format is valid\.|Dataset format needs attention\./)
  }

  get recipeWorkerUnavailableAlert(): Locator {
    return this.page.getByText(
      "Recipe runs are unavailable because the recipe worker is not running on this server. Enable the evaluations recipe worker and try again."
    )
  }

  get currentRunCard(): Locator {
    return this.page.getByText("Current run")
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
    await expect(this.recipesTab).toBeVisible({ timeout: 10_000 })
  }

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Recipes tab",
        locator: this.recipesTab,
        expectation: {
          type: "state_change",
          stateCheck: async () => {
            return this.page.url()
          },
        },
      },
      {
        name: "Review tab",
        locator: this.syntheticReviewTab,
        expectation: {
          type: "state_change",
          stateCheck: async () => {
            return this.page.url()
          },
        },
      },
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
    await this.ensureRecipesTabSelected()
    await expect(this.runRecipeButton).toBeVisible({ timeout: 10_000 })
    await this.runRecipeButton.click()
  }

  /**
   * Switch to a specific tab by clicking its trigger.
   */
  async switchTab(
    tab:
      | "recipes"
      | "synthetic-review"
      | "evaluations"
      | "runs"
      | "datasets"
      | "webhooks"
      | "history"
  ): Promise<void> {
    const tabLocators: Record<string, Locator> = {
      recipes: this.recipesTab,
      "synthetic-review": this.syntheticReviewTab,
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

  async ensureRecipesTabSelected(): Promise<void> {
    const recipesTab = this.tabTrigger(this.recipesTab)
    await expect(this.recipesTab).toBeVisible({ timeout: 10_000 })
    if ((await recipesTab.getAttribute("aria-selected")) !== "true") {
      await recipesTab.click()
    }
    await expect(recipesTab).toHaveAttribute("aria-selected", "true", {
      timeout: 5_000,
    })
  }

  async selectRecipe(recipeName: string): Promise<void> {
    await this.ensureRecipesTabSelected()
    const button = this.recipeUseButton(recipeName)
    await expect(button).toBeVisible({ timeout: 10_000 })
    await button.click()
  }

  async assertRecipeCatalogVisible(): Promise<void> {
    await this.ensureRecipesTabSelected()
    await expect(this.recipeUseButtons.first()).toBeVisible({ timeout: 10_000 })
    await expect(this.validateDatasetButton).toBeVisible({ timeout: 10_000 })
    await expect(this.runRecipeButton).toBeVisible({ timeout: 10_000 })
  }

  async validateCurrentRecipe(): Promise<void> {
    await this.ensureRecipesTabSelected()
    await expect(this.validateDatasetButton).toBeVisible({ timeout: 10_000 })
    await this.validateDatasetButton.click()
    await expect(this.recipeValidationAlert).toBeVisible({ timeout: 10_000 })
  }

  async assertRecipeRunOutcome(): Promise<void> {
    await expect(
      this.currentRunCard.or(this.recipeWorkerUnavailableAlert).first()
    ).toBeVisible({ timeout: 10_000 })
    await expect(
      this.page.getByText("recipe_run_enqueue_failed")
    ).toHaveCount(0)
  }
}
