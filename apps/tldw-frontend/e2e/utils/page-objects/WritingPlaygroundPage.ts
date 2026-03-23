/**
 * Page Object for Writing Playground workflow
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForAppShell, waitForConnection } from "../helpers"

export class WritingPlaygroundPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/writing-playground", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await waitForAppShell(this.page, 30_000)
    // Wait for the shell or the topbar to appear
    const shell = this.page.locator('[data-testid="writing-playground-shell"]')
    const routeShell = this.page.locator('[data-testid="writing-playground-route-shell"]')
    await Promise.race([
      shell.waitFor({ state: "visible", timeout: 20_000 }),
      routeShell.waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** The outermost route shell wrapper */
  get routeShell(): Locator {
    return this.page.locator('[data-testid="writing-playground-route-shell"]')
  }

  /** The WritingPlaygroundShell layout container */
  get shell(): Locator {
    return this.page.locator('[data-testid="writing-playground-shell"]')
  }

  /** Top bar with model input, generate button, and diagnostics */
  get topbar(): Locator {
    return this.page.locator('[data-testid="writing-playground-topbar"]')
  }

  /** Model name input in the top bar */
  get modelInput(): Locator {
    return this.page.locator('[data-testid="writing-topbar-model"]')
  }

  /** Generate / Stop button in the top bar */
  get generateButton(): Locator {
    return this.page.locator('[data-testid="writing-topbar-generate"]')
  }

  /** Main editor grid area */
  get mainGrid(): Locator {
    return this.page.locator('[data-testid="writing-playground-main-grid"]')
  }

  /** Toggle sessions sidebar button (Menu icon) */
  get toggleLibraryButton(): Locator {
    return this.page.getByRole("button", { name: /toggle sessions/i })
  }

  /** Toggle settings/inspector sidebar button (Settings icon) */
  get toggleInspectorButton(): Locator {
    return this.page.getByRole("button", { name: /toggle settings/i })
  }

  /** Library sidebar (expanded mode) */
  get librarySidebar(): Locator {
    return this.page.locator('[data-testid="writing-library-sidebar"]')
  }

  /** Inspector sidebar (expanded mode) */
  get inspectorSidebar(): Locator {
    return this.page.locator('[data-testid="writing-inspector-sidebar"]')
  }

  /** Inspector panel inside the sidebar/drawer */
  get inspectorPanel(): Locator {
    return this.page.locator('[data-testid="writing-playground-inspector-panel"]')
  }

  /** Settings card inside the inspector */
  get settingsCard(): Locator {
    return this.page.locator('[data-testid="writing-playground-settings-card"]')
  }

  /** New session button in the library sidebar */
  get newSessionButton(): Locator {
    return this.page.getByRole("button", { name: /new session/i })
  }

  /** Status bar at the bottom of the editor */
  get statusBar(): Locator {
    return this.page.locator('[data-testid="writing-playground-statusbar"]')
  }

  /** Prompt chunks section in the editor */
  get promptChunksSection(): Locator {
    return this.page.locator('[data-testid="writing-section-prompt-chunks"]')
  }

  /** "No session" empty state text */
  get noSessionText(): Locator {
    return this.page.getByText("No session")
  }

  /** "Select a session to edit settings" empty state */
  get settingsEmptyState(): Locator {
    return this.page.getByText("Select a session to edit settings.")
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "New session button",
        locator: this.newSessionButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/writing\/sessions/,
          method: "POST",
        },
        setup: async (page: Page) => {
          // Ensure the library sidebar is open so the button is visible
          const visible = await this.newSessionButton.isVisible().catch(() => false)
          if (!visible) {
            await this.toggleLibraryButton.click()
            await expect
              .poll(
                async () => {
                  const buttonVisible = await this.newSessionButton.isVisible().catch(() => false)
                  const sidebarVisible = await this.librarySidebar.isVisible().catch(() => false)
                  return buttonVisible || sidebarVisible
                },
                { timeout: 5_000 }
              )
              .toBe(true)
          }
        },
      },
      {
        name: "Generate button",
        locator: this.generateButton,
        expectation: {
          type: "api_call",
          apiPattern: /\/api\/v1\/chat\/completions/,
          method: "POST",
        },
      },
    ]
  }
}
