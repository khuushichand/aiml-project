/**
 * Page Object for Notes Manager functionality
 *
 * Extends BasePage. Wraps the NotesManagerPage component which includes:
 * - NotesSidebar (with NotesToolbar search/filter and NotesListPanel)
 * - NotesEditorPane (title input, content textarea, save/delete actions)
 * - NotesEditorHeader (save button, overflow menu with delete)
 */
import { type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export interface CreateNoteOptions {
  title: string
  content: string
}

export class NotesPage extends BasePage {
  /* ------------------------------------------------------------------ */
  /* Locators                                                            */
  /* ------------------------------------------------------------------ */

  /** "New note" button in the toolbar (aria-label "New note") */
  get newNoteButton(): Locator {
    return this.page.getByRole("button", { name: /new note/i })
  }

  /** Search input in the toolbar (placeholder "Search notes...") */
  get searchInput(): Locator {
    return this.page.getByPlaceholder(/search notes/i)
  }

  /** Title input in the editor pane (placeholder "Title") */
  get titleInput(): Locator {
    return this.page.getByPlaceholder(/^title$/i)
  }

  /** Content textarea in the editor pane (aria-label "Note content") */
  get contentTextarea(): Locator {
    return this.page.getByLabel(/note content/i)
  }

  /** Save button (data-testid "notes-save-button") */
  get saveButton(): Locator {
    return this.page.getByTestId("notes-save-button")
  }

  /** Overflow / "More actions" button (data-testid "notes-overflow-menu-button") */
  get overflowMenuButton(): Locator {
    return this.page.getByTestId("notes-overflow-menu-button")
  }

  /** Editor region (data-testid "notes-editor-region") */
  get editorRegion(): Locator {
    return this.page.getByTestId("notes-editor-region")
  }

  /* ------------------------------------------------------------------ */
  /* BasePage overrides                                                  */
  /* ------------------------------------------------------------------ */

  async goto(): Promise<void> {
    await this.page.goto("/notes", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    // The toolbar search input and new-note button should be visible
    await expect(this.searchInput).toBeVisible({ timeout: 20_000 })
    await expect(this.newNoteButton).toBeVisible({ timeout: 10_000 })
  }

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "New note",
        locator: this.newNoteButton,
        expectation: {
          type: "state_change",
          stateCheck: async () => {
            // Title input should appear or change after clicking new note
            return this.titleInput.inputValue().catch(() => "__absent__")
          },
        },
      },
    ]
  }

  /* ------------------------------------------------------------------ */
  /* High-level actions                                                  */
  /* ------------------------------------------------------------------ */

  /**
   * Create a new note: click "New note", fill title + content, save.
   */
  async createNote(opts: CreateNoteOptions): Promise<void> {
    await this.newNoteButton.click()

    // Wait for the editor to be ready
    await expect(this.titleInput).toBeVisible({ timeout: 10_000 })

    await this.titleInput.fill(opts.title)

    // The content textarea may be a plain <textarea> or a contenteditable div (WYSIWYG).
    // Prefer the textarea; fall back to the contenteditable editor.
    const textarea = this.contentTextarea
    if ((await textarea.count()) > 0 && (await textarea.isVisible())) {
      await textarea.fill(opts.content)
    } else {
      // WYSIWYG fallback
      const wysiwyg = this.page.getByTestId("notes-wysiwyg-editor")
      await wysiwyg.click()
      await this.page.keyboard.type(opts.content)
    }

    await this.saveButton.click()

    // Wait for save to complete (button stops showing loading state)
    await expect(this.saveButton).toBeEnabled({ timeout: 15_000 })
  }

  /**
   * Type a search query in the toolbar search input and press Enter.
   */
  async searchNotes(query: string): Promise<void> {
    await expect(this.searchInput).toBeVisible({ timeout: 10_000 })
    await this.searchInput.fill(query)
    await this.searchInput.press("Enter")
    // Allow list to update
    await this.page.waitForTimeout(1_000)
  }

  /**
   * Assert that a note with the given title is visible in the list panel.
   */
  async assertNoteVisible(title: string): Promise<void> {
    const noteItem = this.page.getByText(title, { exact: false })
    await expect(noteItem.first()).toBeVisible({ timeout: 15_000 })
  }

  /**
   * Assert that a note with the given title is NOT visible in the list panel.
   */
  async assertNoteNotVisible(title: string): Promise<void> {
    const noteItem = this.page.getByText(title, { exact: false })
    await expect(noteItem).toBeHidden({ timeout: 10_000 })
  }

  /**
   * Select a note by clicking its title in the list, then delete it
   * via the overflow menu.
   */
  async deleteNote(title: string): Promise<void> {
    // Click on the note in the list to select it
    const noteItem = this.page.getByText(title, { exact: false }).first()
    await noteItem.click()

    // Wait for editor header to show the title
    await expect(this.overflowMenuButton).toBeVisible({ timeout: 10_000 })

    // Open overflow menu
    await this.overflowMenuButton.click()

    // Click "Delete" in the dropdown menu
    const deleteMenuItem = this.page.getByRole("menuitem", { name: /delete/i })
    await expect(deleteMenuItem).toBeVisible({ timeout: 5_000 })
    await deleteMenuItem.click()

    // Handle confirmation modal if present (the component uses useConfirmDanger)
    const confirmButton = this.page.getByRole("button", { name: /ok|confirm|yes|delete/i })
    if ((await confirmButton.count()) > 0) {
      try {
        await confirmButton.first().click({ timeout: 3_000 })
      } catch {
        // No confirmation needed
      }
    }
  }
}
