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
  readonly globalSearchInput: Locator
  readonly commandPalette: Locator
  readonly addSourceModal: Locator

  constructor(page: Page) {
    this.page = page
    this.headerTitle = page.locator("header h1").first()
    this.workspacesButton = page.getByRole("button", { name: /workspaces/i })
    this.sourcesPanel = page.locator("#workspace-sources-panel")
    this.chatPanel = page.locator("#workspace-main-content")
    this.studioPanel = page.locator("#workspace-studio-panel")
    this.globalSearchModal = page.getByRole("dialog", { name: /search workspace/i }).first()
    this.globalSearchInput = this.globalSearchModal.getByPlaceholder(
      /search sources, chat, and notes/i
    )
    this.commandPalette = page.getByRole("dialog", { name: /command palette/i }).first()
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

  private async waitForModalBackdropsToClear(): Promise<void> {
    await expect(
      this.page.locator(
        "div.fixed.inset-0.z-50.bg-black\\/50:visible, div.fixed.inset-0.z-50.backdrop-blur-sm:visible, .ant-modal-mask:visible"
      )
    ).toHaveCount(0, { timeout: 10_000 })
  }

  private async closeCommandPaletteIfOpen(): Promise<void> {
    if (!(await this.commandPalette.isVisible().catch(() => false))) {
      return
    }

    const input = this.commandPalette.getByPlaceholder(/type a command or search/i)
    if (await input.isVisible().catch(() => false)) {
      await input.click()
      await input.press("Escape")
    } else {
      await this.page.keyboard.press("Escape")
    }
    await expect(this.commandPalette).toBeHidden({ timeout: 10_000 })
  }

  private async clickWhenActionable(locator: Locator): Promise<void> {
    await expect(locator).toBeVisible({ timeout: 10_000 })
    await this.disableNextJsPortalPointerInterception()
    await this.waitForModalBackdropsToClear()
    try {
      await locator.click({ trial: true, timeout: 3_000 })
    } catch {
      await this.disableNextJsPortalPointerInterception()
      await this.waitForModalBackdropsToClear()
      await locator.click({ trial: true, timeout: 3_000 })
    }
    await locator.click()
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
    if (!(await this.globalSearchInput.isVisible().catch(() => false))) {
      await expect(this.globalSearchModal).toBeVisible({ timeout: 2_000 }).catch(() => {})
    }
    if (!(await this.globalSearchInput.isVisible().catch(() => false))) {
      await this.page.keyboard.press("Meta+k")
    }
    await expect(this.globalSearchModal).toBeVisible({ timeout: 10_000 })
    await expect(this.globalSearchInput).toBeVisible({ timeout: 10_000 })
    await this.closeCommandPaletteIfOpen()
  }

  async closeGlobalSearchWithEscape(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    if (await this.globalSearchInput.isVisible().catch(() => false)) {
      await this.globalSearchInput.click()
      await expect(this.globalSearchInput).toBeFocused({ timeout: 10_000 })
      await this.globalSearchInput.press("Escape")
    }
    await expect(this.globalSearchModal).toBeHidden({ timeout: 10_000 })
    await this.closeCommandPaletteIfOpen()
    await this.waitForModalBackdropsToClear()
  }

  async hideSourcesPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.clickWhenActionable(
      this.sourcesPanel.getByRole("button", { name: /hide sources/i })
    )
    await expect(this.sourcesPanel).toBeHidden({ timeout: 10_000 })
  }

  async showSourcesPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.clickWhenActionable(
      this.page.getByRole("button", { name: /show sources/i }).first()
    )
    await expect(this.sourcesPanel).toBeVisible({ timeout: 10_000 })
  }

  async hideStudioPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.clickWhenActionable(
      this.studioPanel.getByRole("button", { name: /hide studio/i })
    )
    await expect(this.studioPanel).toBeHidden({ timeout: 10_000 })
  }

  async showStudioPane(): Promise<void> {
    await this.disableNextJsPortalPointerInterception()
    await this.clickWhenActionable(
      this.page.getByRole("button", { name: /show studio/i }).first()
    )
    await expect(this.studioPanel).toBeVisible({ timeout: 10_000 })
  }

  async openAddSourcesModal(): Promise<void> {
    await expect(this.sourcesPanel).toBeVisible({ timeout: 10_000 })
    await this.disableNextJsPortalPointerInterception()
    await this.clickWhenActionable(
      this.sourcesPanel.getByRole("button", { name: /^add$/i })
    )
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
    await this.waitForModalBackdropsToClear()
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
