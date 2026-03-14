/**
 * Page Object for Workflow Editor (node-based visual editor)
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class WorkflowEditorPage extends BasePage {
  constructor(page: Page) {
    super(page)
  }

  // -- Navigation ------------------------------------------------------------

  async goto(): Promise<void> {
    await this.page.goto("/workflow-editor", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await this.page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})
    // Wait for the toolbar (Save button) or canvas area
    const saveButton = this.page.getByRole("button", { name: /^Save$/i })
    const statusBar = this.page.getByText(/\d+ nodes/)
    await Promise.race([
      saveButton.first().waitFor({ state: "visible", timeout: 20_000 }),
      statusBar.first().waitFor({ state: "visible", timeout: 20_000 }),
    ]).catch(() => {})
  }

  // -- Locators --------------------------------------------------------------

  /** Save button in toolbar */
  get saveButton(): Locator {
    return this.page.getByRole("button", { name: /^Save$/i })
  }

  /** Undo button */
  get undoButton(): Locator {
    return this.page.getByRole("button", { name: /undo/i })
  }

  /** Redo button */
  get redoButton(): Locator {
    return this.page.getByRole("button", { name: /redo/i })
  }

  /** Toggle Grid button */
  get toggleGridButton(): Locator {
    return this.page.getByRole("button", { name: /toggle grid/i })
  }

  /** Toggle Minimap button */
  get toggleMinimapButton(): Locator {
    return this.page.getByRole("button", { name: /toggle minimap/i })
  }

  /** More actions dropdown trigger */
  get moreActionsButton(): Locator {
    return this.page.getByRole("button", { name: /more actions/i })
  }

  /** Workflow name display (clickable to edit) */
  get workflowNameDisplay(): Locator {
    return this.page.locator("button.text-sm.font-medium")
  }

  /** Workflow name input (when editing) */
  get workflowNameInput(): Locator {
    return this.page.locator(".min-w-\\[200px\\] input")
  }

  /** Dirty indicator (asterisk) */
  get dirtyIndicator(): Locator {
    return this.page.locator("span:has-text('*')").first()
  }

  /** Status bar */
  get statusBar(): Locator {
    return this.page.locator(".flex.items-center.justify-between.px-3.py-1")
  }

  /** Node count in status bar */
  get nodeCount(): Locator {
    return this.page.getByText(/\d+ nodes/)
  }

  /** Connection count in status bar */
  get connectionCount(): Locator {
    return this.page.getByText(/\d+ connections/)
  }

  /** Sidebar panel segmented control (desktop) */
  get sidebarSegmented(): Locator {
    return this.page.locator(".ant-segmented")
  }

  /** Nodes (Palette) tab in sidebar */
  get nodesPaletteTab(): Locator {
    return this.page.getByTitle("Nodes")
  }

  /** Config tab in sidebar */
  get configTab(): Locator {
    return this.page.getByTitle("Config")
  }

  /** Run tab in sidebar */
  get runTab(): Locator {
    return this.page.getByTitle("Run")
  }

  /** Validation issues button */
  get validationIssuesButton(): Locator {
    return this.page.getByRole("button", { name: /validation issues/i })
  }

  /** Canvas area */
  get canvas(): Locator {
    return this.page.locator(".react-flow, [data-testid='workflow-canvas']").first()
  }

  /** Open workflow panels button (mobile) */
  get openPanelsButton(): Locator {
    return this.page.getByRole("button", { name: /open workflow panels/i })
  }

  // -- Dropdown menu items ---------------------------------------------------

  /** New Workflow menu item (from More actions) */
  get newWorkflowMenuItem(): Locator {
    return this.page.getByText("New Workflow")
  }

  /** Import menu item (from More actions) */
  get importMenuItem(): Locator {
    return this.page.locator(".ant-dropdown-menu-item").filter({ hasText: "Import" })
  }

  /** Export menu item (from More actions) */
  get exportMenuItem(): Locator {
    return this.page.locator(".ant-dropdown-menu-item").filter({ hasText: "Export" })
  }

  /** Clear Canvas menu item (from More actions) */
  get clearCanvasMenuItem(): Locator {
    return this.page.getByText("Clear Canvas")
  }

  // -- Helpers ---------------------------------------------------------------

  /** Click the workflow name to enter edit mode */
  async startEditingName(): Promise<void> {
    await this.workflowNameDisplay.click()
  }

  /** Open the More actions dropdown */
  async openMoreActions(): Promise<void> {
    await this.moreActionsButton.click()
  }

  /** Switch sidebar panel */
  async switchSidebarPanel(panel: "palette" | "config" | "execution"): Promise<void> {
    const panelLocator = {
      palette: this.nodesPaletteTab,
      config: this.configTab,
      execution: this.runTab,
    }[panel]
    await panelLocator.click()
  }

  // -- Interactive elements for assertAllButtonsWired() ----------------------

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Toggle Grid button",
        locator: this.toggleGridButton,
        expectation: {
          type: "state_change",
          stateCheck: async (page: Page) => {
            const btn = page.getByRole("button", { name: /toggle grid/i })
            return btn.getAttribute("class")
          },
        },
      },
      {
        name: "Toggle Minimap button",
        locator: this.toggleMinimapButton,
        expectation: {
          type: "state_change",
          stateCheck: async (page: Page) => {
            const btn = page.getByRole("button", { name: /toggle minimap/i })
            return btn.getAttribute("class")
          },
        },
      },
    ]
  }
}
