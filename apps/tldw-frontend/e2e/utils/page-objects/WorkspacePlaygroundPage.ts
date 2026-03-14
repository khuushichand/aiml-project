/**
 * Page Object for Workspace Playground workflow coverage
 */
import { type Locator, type Page, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

type WorkspaceSeedSource = {
  mediaId: number
  title: string
  type?: "pdf" | "video" | "audio" | "website" | "document" | "text"
  url?: string
}

export class WorkspacePlaygroundPage {
  readonly page: Page
  readonly headerTitle: Locator
  readonly workspacesButton: Locator
  readonly sourcesPanel: Locator
  readonly chatPanel: Locator
  readonly studioPanel: Locator
  readonly globalSearchModal: Locator
  readonly addSourceModal: Locator

  constructor(page: Page) {
    this.page = page
    this.headerTitle = page.locator("header h1").first()
    this.workspacesButton = page.getByRole("button", { name: /workspaces/i })
    this.sourcesPanel = page.locator("#workspace-sources-panel")
    this.chatPanel = page.locator("#workspace-main-content")
    this.studioPanel = page.locator("#workspace-studio-panel")
    this.globalSearchModal = page
      .getByRole("dialog")
      .filter({ hasText: /search workspace/i })
      .first()
    this.addSourceModal = page
      .getByRole("dialog")
      .filter({ hasText: /add sources/i })
      .first()
  }

  private async disableNextJsPortalPointerInterception(): Promise<void> {
    await this.page.evaluate(() => {
      const portals = document.querySelectorAll("nextjs-portal")
      portals.forEach((portal) => {
        ;(portal as HTMLElement).style.pointerEvents = "none"
      })
    })
  }

  async goto(): Promise<void> {
    await this.page.goto("/workspace-playground", {
      waitUntil: "domcontentloaded"
    })
    await waitForConnection(this.page).catch(() => {})
    await this.disableNextJsPortalPointerInterception()
  }

  async waitForReady(): Promise<void> {
    await expect(this.workspacesButton).toBeVisible({ timeout: 30_000 })
    await expect(this.chatPanel).toBeVisible({ timeout: 30_000 })
    await this.disableNextJsPortalPointerInterception()
  }

  async openGlobalSearchWithShortcut(): Promise<void> {
    await this.page.locator("body").click()
    await this.page.keyboard.press("Control+k")
    if (!(await this.globalSearchModal.isVisible().catch(() => false))) {
      await this.page.keyboard.press("Meta+k")
    }
    await expect(this.globalSearchModal).toBeVisible({ timeout: 10_000 })
  }

  async closeGlobalSearchWithEscape(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    const closeButton = this.globalSearchModal
      .locator("button.ant-modal-close")
      .first()
    if (await closeButton.isVisible().catch(() => false)) {
      await closeButton.click({ force: true })
    } else {
      await this.page.keyboard.press("Escape")
    }
    await expect(this.globalSearchModal).toBeHidden({ timeout: 10_000 })
  }

  async hideSourcesPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.sourcesPanel
      .getByRole("button", { name: /hide sources/i })
      .click({ force: true })
    await expect(this.sourcesPanel).toBeHidden({ timeout: 10_000 })
  }

  async showSourcesPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.page
      .getByRole("button", { name: /show sources/i })
      .first()
      .click({ force: true })
    await expect(this.sourcesPanel).toBeVisible({ timeout: 10_000 })
  }

  async hideStudioPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.studioPanel
      .getByRole("button", { name: /hide studio/i })
      .click({ force: true })
    await expect(this.studioPanel).toBeHidden({ timeout: 10_000 })
  }

  async showStudioPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.page
      .getByRole("button", { name: /show studio/i })
      .first()
      .click({ force: true })
    await expect(this.studioPanel).toBeVisible({ timeout: 10_000 })
  }

  async openAddSourcesModal(): Promise<void> {
    await expect(this.sourcesPanel).toBeVisible({ timeout: 10_000 })
    await this.disableNextJsPortalPointerInterception()
    await this.sourcesPanel
      .getByRole("button", { name: /^add$/i })
      .click({ force: true })
    await expect(this.addSourceModal).toBeVisible({ timeout: 10_000 })
  }

  async closeAddSourcesModal(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    const closeButton = this.addSourceModal
      .locator("button.ant-modal-close")
      .first()
    if (await closeButton.isVisible().catch(() => false)) {
      await closeButton.click({ force: true })
    } else {
      await this.page.keyboard.press("Escape")
    }
    await expect(this.addSourceModal).toBeHidden({ timeout: 10_000 })
  }

  async seedSources(sources: WorkspaceSeedSource[]): Promise<void> {
    await this.page.evaluate((seed) => {
      const store = (window as { __tldw_useWorkspaceStore?: unknown })
        .__tldw_useWorkspaceStore as
        | {
            getState?: () => {
              workspaceId?: string
              initializeWorkspace?: (name?: string) => void
              addSources?: (
                sources: Array<{
                  mediaId: number
                  title: string
                  type:
                    | "pdf"
                    | "video"
                    | "audio"
                    | "website"
                    | "document"
                    | "text"
                  url: string
                  status: "ready"
                }>
              ) => void
            }
          }
        | undefined
      if (!store?.getState) {
        throw new Error("Workspace store is unavailable on window")
      }
      const state = store.getState()
      if (!state.workspaceId) {
        state.initializeWorkspace?.("Workspace E2E")
      }
      state.addSources?.(
        seed.map((source) => ({
          mediaId: source.mediaId,
          title: source.title,
          type: source.type || "document",
          url: source.url || `https://example.com/source-${source.mediaId}`,
          status: "ready"
        }))
      )
    }, sources)
  }

  async getSourceIds(): Promise<string[]> {
    return await this.page
      .locator("[data-source-id]")
      .evaluateAll((rows) =>
        rows
          .map((row) => row.getAttribute("data-source-id"))
          .filter((id): id is string => Boolean(id))
      )
  }

  async selectSourceById(sourceId: string): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    const checkbox = this.page.locator(
      `[data-source-id="${sourceId}"] input[type="checkbox"]`
    )
    if (await checkbox.isChecked().catch(() => false)) {
      return
    }

    const hitArea = this.page.getByTestId(`source-checkbox-hitarea-${sourceId}`)
    if (await hitArea.isVisible().catch(() => false)) {
      await hitArea.click({ force: true })
      if (await checkbox.isChecked().catch(() => false)) {
        return
      }
    }

    const antCheckbox = this.page.locator(
      `[data-source-id="${sourceId}"] .ant-checkbox`
    )
    if (await antCheckbox.isVisible().catch(() => false)) {
      await antCheckbox.click({ force: true })
      if (await checkbox.isChecked().catch(() => false)) {
        return
      }
    }

    if (await checkbox.isVisible().catch(() => false)) {
      await checkbox.click({ force: true })
      return
    }
    await hitArea.click({ force: true })
  }

  async expectSourceSelected(sourceId: string): Promise<void> {
    await expect(
      this.page.locator(`[data-source-id="${sourceId}"] input[type="checkbox"]`)
    ).toBeChecked()
  }
}

export default WorkspacePlaygroundPage
