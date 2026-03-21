import { expect, type Locator, type Page } from "@playwright/test"

import { COMPANION_HOME_PARITY_CARD_ROWS } from "./companion-home.fixtures"

export type CompanionHomeParityPlatform = "web" | "extension"

export interface CompanionHomeParityContext {
  platform: CompanionHomeParityPlatform
  page: Page
  optionsUrl?: string
}

export class CompanionHomeParityPage {
  readonly page: Page
  readonly shell: Locator
  readonly pageRoot: Locator
  readonly summary: Locator
  readonly summaryValues: Locator
  readonly customizeHomeButton: Locator
  readonly refreshButton: Locator

  constructor(page: Page) {
    this.page = page
    this.shell = page.getByTestId("companion-home-shell")
    this.pageRoot = page.getByTestId("companion-home-page")
    this.summary = page.getByTestId("companion-home-summary")
    this.summaryValues = this.summary.locator("p.text-2xl")
    this.customizeHomeButton = page.getByRole("button", { name: "Customize Home" })
    this.refreshButton = page.getByRole("button", { name: "Refresh" })
  }

  async goto(platform: CompanionHomeParityPlatform, optionsUrl?: string): Promise<void> {
    if (platform === "extension") {
      if (!optionsUrl) {
        throw new Error("optionsUrl is required for extension parity navigation")
      }
      await this.page.goto(`${optionsUrl}#/`, {
        waitUntil: "domcontentloaded"
      })
      return
    }

    await this.page.goto("/", {
      waitUntil: "domcontentloaded"
    })
  }

  async waitForReady(): Promise<void> {
    await expect(this.shell).toBeVisible({ timeout: 30_000 })
    await expect(this.pageRoot).toBeVisible({ timeout: 30_000 })
    await expect(this.customizeHomeButton).toBeVisible({ timeout: 30_000 })
    await expect(this.refreshButton).toBeVisible({ timeout: 30_000 })
    await expect(this.summary).toBeVisible({ timeout: 30_000 })
  }

  async assertDashboardVisible(): Promise<void> {
    await expect(this.pageRoot.getByText("Companion Home", { exact: true })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Companion" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Inbox Preview" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Needs Attention" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Resume Work" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Goals / Focus" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Recent Activity" })).toBeVisible()
    await expect(this.page.getByRole("heading", { name: "Reading Queue" })).toBeVisible()
  }

  async assertSummaryCounts(): Promise<void> {
    await expect(this.summary.getByText("Inbox", { exact: true })).toBeVisible()
    await expect(this.summary.getByText("Goals", { exact: true })).toBeVisible()
    await expect(this.summary.getByText("Reading", { exact: true })).toBeVisible()
    await expect(this.summary.getByText("Resume", { exact: true })).toBeVisible()
    await expect(this.summaryValues).toHaveText(["1", "1", "1", "3"])
  }

  async assertFixtureContent(): Promise<void> {
    await expect(this.page.getByText("Inbox capture").first()).toBeVisible()
    await expect(this.page.getByText("Queue article").first()).toBeVisible()
    await expect(this.page.getByText("Draft outline").first()).toBeVisible()
    await expect(this.page.getByText("Review the saved queue.").first()).toBeVisible()
    await expect(
      this.page.getByText("Turn the queue review into a checklist.").first()
    ).toBeVisible()
  }

  async openCustomizeDrawer(): Promise<void> {
    await this.customizeHomeButton.click()
    await expect(this.page.getByRole("dialog", { name: "Customize Home" })).toBeVisible()
  }

  async assertCustomizeDrawerVisible(): Promise<void> {
    const dialog = this.page.getByRole("dialog", { name: "Customize Home" })
    await expect(dialog).toBeVisible()
    await expect(
      this.page.getByText(
        "Keep system cards fixed, then hide or reorder the rest for this surface."
      )
    ).toBeVisible()
    for (const card of COMPANION_HOME_PARITY_CARD_ROWS) {
      const row = this.page.getByTestId(`companion-home-layout-row-${card.id}`)
      await expect(row).toBeVisible()
      await expect(row.getByText(card.title, { exact: true })).toBeVisible()
    }
  }

  async closeCustomizeDrawer(): Promise<void> {
    const dialog = this.page.getByRole("dialog", { name: "Customize Home" })
    await dialog.getByRole("button", { name: "Close", exact: true }).click()
    await expect(dialog).toHaveCount(0)
  }
}
