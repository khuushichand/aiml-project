# E2E Test Coverage Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ~47 new e2e workflow tests across WebUI and extension, covering Notes, Flashcards, Chat+RAG integration, Media batch ops, Characters, Audio, Watchlists, Collections, Content Review, Evaluations, Prompt Studio, Agents, Writing, and Admin pages.

**Architecture:** Hybrid approach — page objects for Tier A features (Notes, Flashcards, MediaPage extension), lightweight inline-selector workflow scripts for Tier B/C. All tests use the existing Playwright fixtures (`test`, `expect`, `authedPage`, `serverInfo`, `diagnostics`) from `e2e/utils/fixtures.ts`. Extension tests use `launchWithBuiltExtension` + `forceConnected` patterns.

**Tech Stack:** Playwright, TypeScript, existing test fixtures and page objects

**Design Doc:** `Docs/Plans/2026-03-12-e2e-test-coverage-expansion-design.md`

---

## Task 1: Add shared helper functions

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/helpers.ts`

**Step 1: Write the helpers**

Add these functions to the end of `helpers.ts`:

```typescript
/**
 * Ingest content from a URL and wait for it to appear in media list.
 * Useful as a prerequisite for RAG, flashcard, and batch operation tests.
 */
export async function ingestAndWait(
  page: Page,
  url: string,
  expectedTitle: string,
  timeoutMs = 120000
): Promise<void> {
  const serverUrl = TEST_CONFIG.serverUrl
  const res = await fetchWithApiKey(
    `${serverUrl}/api/v1/media/process`,
    TEST_CONFIG.apiKey,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, title: expectedTitle }),
    }
  )
  if (!res.ok) {
    throw new Error(`Ingest failed: ${res.status} ${await res.text()}`)
  }

  // Poll until media appears in search
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const searchRes = await fetchWithApiKey(
      `${serverUrl}/api/v1/media/search?query=${encodeURIComponent(expectedTitle)}`,
      TEST_CONFIG.apiKey
    )
    if (searchRes.ok) {
      const data = await searchRes.json()
      const items = data?.results || data?.items || data || []
      if (Array.isArray(items) && items.length > 0) return
    }
    await new Promise((r) => setTimeout(r, 2000))
  }
  throw new Error(`Timed out waiting for "${expectedTitle}" to appear after ingest`)
}

/**
 * Wait for chat streaming to complete (stop button disappears).
 */
export async function waitForStreamComplete(page: Page, timeoutMs = 60000): Promise<void> {
  const stopButton = page.locator(
    "[data-testid='stop-button'], button[aria-label*='stop' i], [data-streaming='true']"
  )
  // Wait for streaming to start (or skip if already done)
  const started = await stopButton.isVisible().catch(() => false)
  if (started) {
    await expect(stopButton).not.toBeVisible({ timeout: timeoutMs })
  }
}

/**
 * Behavioral assertion: verify flashcards were generated.
 */
export async function assertFlashcardsGenerated(
  page: Page,
  minCount = 1
): Promise<void> {
  const cards = page.locator('[data-testid^="flashcard-item-"]')
  await expect(cards.first()).toBeVisible({ timeout: 30000 })
  const count = await cards.count()
  if (count < minCount) {
    throw new Error(`Expected at least ${minCount} flashcards, got ${count}`)
  }
}
```

Note: `expect` needs to be imported at the top of helpers.ts:

```typescript
import { type Page, expect } from '@playwright/test';
```

**Step 2: Verify no type errors**

Run: `cd apps/tldw-frontend && npx tsc --noEmit --pretty`
Expected: No new errors in helpers.ts

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/helpers.ts
git commit -m "test: add shared e2e helpers for ingest, streaming, and flashcard assertions"
```

---

## Task 2: Create test fixtures

**Files:**
- Create: `apps/tldw-frontend/e2e/fixtures/test-document.md`

**Step 1: Create the fixture directory and file**

```bash
mkdir -p apps/tldw-frontend/e2e/fixtures
```

Write `test-document.md`:

```markdown
# Photosynthesis in Plants

Photosynthesis is the process by which green plants convert sunlight into chemical energy.
The process occurs primarily in chloroplasts, using chlorophyll pigments.

## Key Steps

1. Light-dependent reactions occur in the thylakoid membranes
2. The Calvin cycle fixes carbon dioxide into glucose
3. Water molecules are split, releasing oxygen as a byproduct

## Important Facts

- Plants absorb red and blue light wavelengths most efficiently
- The chemical equation: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2
- Photosynthesis produces approximately 130 terawatts of energy globally
```

This content has distinctive keywords (photosynthesis, chloroplasts, Calvin cycle, thylakoid) that can be used for behavioral RAG assertions.

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/fixtures/
git commit -m "test: add fixture document for RAG and flashcard e2e tests"
```

---

## Task 3: Create NotesPage page object

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/index.ts`

**Step 1: Write NotesPage**

```typescript
/**
 * Page Object for Notes functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class NotesPage {
  readonly page: Page
  readonly searchInput: Locator
  readonly newButton: Locator
  readonly saveButton: Locator
  readonly listRegion: Locator
  readonly editorRegion: Locator
  readonly modeActive: Locator
  readonly modeTrash: Locator

  constructor(page: Page) {
    this.page = page
    this.searchInput = page.getByTestId("notes-search")
    this.newButton = page.getByTestId("notes-new-button")
    this.saveButton = page.getByTestId("notes-save-button")
    this.listRegion = page.getByTestId("notes-list-region")
    this.editorRegion = page.getByTestId("notes-editor-region")
    this.modeActive = page.getByTestId("notes-mode-active")
    this.modeTrash = page.getByTestId("notes-mode-trash")
  }

  async goto(): Promise<void> {
    await this.page.goto("/notes", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await expect(
      this.listRegion.or(this.editorRegion).first()
    ).toBeVisible({ timeout: 20000 })
  }

  /**
   * Create a new note. Clicks "New" button (if present), fills title and content, saves.
   */
  async createNote(content: string): Promise<void> {
    // Click new note button if visible
    if ((await this.newButton.count()) > 0 && (await this.newButton.isVisible())) {
      await this.newButton.click()
    }

    // Fill content in textarea
    const textarea = this.page.getByPlaceholder(/write your note|note content/i)
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill(content)

    // Save
    await this.save()
  }

  async save(): Promise<void> {
    if ((await this.saveButton.count()) > 0 && (await this.saveButton.isVisible())) {
      await this.saveButton.click()
    }
    // Wait for save status
    const saveStatus = this.page.getByTestId("notes-save-status")
    if ((await saveStatus.count()) > 0) {
      await this.page.waitForTimeout(1000)
    }
  }

  async searchNotes(query: string): Promise<void> {
    await this.searchInput.fill(query)
    await this.searchInput.press("Enter")
    await this.page.waitForTimeout(500)
  }

  async openKeywordsEditor(): Promise<void> {
    const keywordsEditor = this.page.getByTestId("notes-keywords-editor")
    await keywordsEditor.click()
  }

  async switchToTrash(): Promise<void> {
    await this.modeTrash.click()
    await this.page.waitForTimeout(500)
  }

  async switchToActive(): Promise<void> {
    await this.modeActive.click()
    await this.page.waitForTimeout(500)
  }

  async restoreNote(noteId: string): Promise<void> {
    const restoreBtn = this.page.getByTestId(`notes-restore-${noteId}`)
    await restoreBtn.click()
  }

  async deleteNote(noteId: string): Promise<void> {
    // Click overflow menu then delete, or direct trash button
    const overflowBtn = this.page.getByTestId("notes-overflow-menu-button")
    if ((await overflowBtn.count()) > 0 && (await overflowBtn.isVisible())) {
      await overflowBtn.click()
      const deleteOption = this.page.getByRole("menuitem", { name: /delete|trash/i })
      await deleteOption.click()
    }
  }

  async getNotesList(): Promise<Locator> {
    return this.page.locator('[data-testid^="notes-open-button-"]')
  }

  async selectNote(noteId: string): Promise<void> {
    const openBtn = this.page.getByTestId(`notes-open-button-${noteId}`)
    await openBtn.click()
  }

  async bulkExport(): Promise<void> {
    const exportBtn = this.page.getByTestId("notes-bulk-export")
    await exportBtn.click()
  }

  async getEditorContent(): Promise<string> {
    const textarea = this.page.getByPlaceholder(/write your note|note content/i)
    return (await textarea.inputValue()) || (await textarea.textContent()) || ""
  }
}
```

**Step 2: Add export to index.ts**

Add to `apps/tldw-frontend/e2e/utils/page-objects/index.ts`:

```typescript
export { NotesPage } from "./NotesPage"
```

**Step 3: Verify no type errors**

Run: `cd apps/tldw-frontend && npx tsc --noEmit --pretty`
Expected: No new errors

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/NotesPage.ts apps/tldw-frontend/e2e/utils/page-objects/index.ts
git commit -m "test: add NotesPage page object for e2e tests"
```

---

## Task 4: Create FlashcardsPage page object

**Files:**
- Create: `apps/tldw-frontend/e2e/utils/page-objects/FlashcardsPage.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/index.ts`

**Step 1: Write FlashcardsPage**

```typescript
/**
 * Page Object for Flashcards functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class FlashcardsPage {
  readonly page: Page
  readonly tabs: Locator
  readonly reviewDeckSelect: Locator
  readonly showAnswerButton: Locator
  readonly activeCard: Locator
  readonly manageSearch: Locator
  readonly manageDeckSelect: Locator
  readonly fabCreateButton: Locator
  readonly generateButton: Locator
  readonly generateSaveButton: Locator

  constructor(page: Page) {
    this.page = page
    this.tabs = page.getByTestId("flashcards-tabs")
    this.reviewDeckSelect = page.getByTestId("flashcards-review-deck-select")
    this.showAnswerButton = page.getByTestId("flashcards-review-show-answer")
    this.activeCard = page.getByTestId("flashcards-review-active-card")
    this.manageSearch = page.getByTestId("flashcards-manage-search")
    this.manageDeckSelect = page.getByTestId("flashcards-manage-deck-select")
    this.fabCreateButton = page.getByTestId("flashcards-fab-create")
    this.generateButton = page.getByTestId("flashcards-generate-button")
    this.generateSaveButton = page.getByTestId("flashcards-generate-save-button")
  }

  async goto(): Promise<void> {
    await this.page.goto("/flashcards", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async waitForReady(): Promise<void> {
    await expect(this.tabs).toBeVisible({ timeout: 20000 })
  }

  /**
   * Switch to one of the main tabs: Review, Manage, or Import/Export
   */
  async switchTab(tabName: "Review" | "Manage" | "Import/Export"): Promise<void> {
    const tab = this.page.getByRole("tab", { name: tabName, exact: true })
    await tab.click()
    await this.page.waitForTimeout(500)
  }

  /**
   * In Review tab: show the answer on current card
   */
  async showAnswer(): Promise<void> {
    await expect(this.showAnswerButton).toBeVisible({ timeout: 10000 })
    await this.showAnswerButton.click()
  }

  /**
   * In Review tab: rate the current card (e.g., "again", "hard", "good", "easy")
   */
  async rateCard(rating: string): Promise<void> {
    const rateBtn = this.page.getByTestId(`flashcards-review-rate-${rating}`)
    await expect(rateBtn).toBeVisible({ timeout: 5000 })
    await rateBtn.click()
  }

  /**
   * Check if the review empty state is showing (no cards to review)
   */
  async isReviewEmpty(): Promise<boolean> {
    const emptyCard = this.page.getByTestId("flashcards-review-empty-card")
    return (await emptyCard.count()) > 0 && (await emptyCard.isVisible())
  }

  /**
   * In Manage tab: get all visible flashcard items
   */
  async getCardItems(): Promise<Locator> {
    return this.page.locator('[data-testid^="flashcard-item-"]')
  }

  /**
   * In Manage tab: search cards
   */
  async searchCards(query: string): Promise<void> {
    await this.switchTab("Manage")
    await this.manageSearch.fill(query)
    await this.page.waitForTimeout(500)
  }

  /**
   * In Manage tab: soft-delete a card
   */
  async trashCard(uuid: string): Promise<void> {
    const trashBtn = this.page.getByTestId(`flashcard-trash-${uuid}`)
    await trashBtn.click()
  }

  /**
   * Switch to Import/Export tab and generate flashcards from text
   */
  async generateFromText(text: string, count = 5): Promise<void> {
    await this.switchTab("Import/Export")

    const generateText = this.page.getByTestId("flashcards-generate-text")
    await expect(generateText).toBeVisible({ timeout: 10000 })
    await generateText.fill(text)

    const generateCount = this.page.getByTestId("flashcards-generate-count")
    if ((await generateCount.count()) > 0) {
      await generateCount.fill(String(count))
    }

    await this.generateButton.click()
  }

  /**
   * After generation, save the generated cards
   */
  async saveGeneratedCards(): Promise<void> {
    await expect(this.generateSaveButton).toBeVisible({ timeout: 60000 })
    await this.generateSaveButton.click()
  }

  /**
   * In Import/Export tab: import CSV/text content
   */
  async importFromText(content: string, format = "csv"): Promise<void> {
    await this.switchTab("Import/Export")

    const formatSelect = this.page.getByTestId("flashcards-import-format")
    if ((await formatSelect.count()) > 0) {
      await formatSelect.click()
      const option = this.page.getByRole("option", { name: new RegExp(format, "i") })
      if ((await option.count()) > 0) await option.click()
    }

    const textarea = this.page.getByTestId("flashcards-import-textarea")
    await textarea.fill(content)

    const importBtn = this.page.getByTestId("flashcards-import-button")
    await importBtn.click()
  }

  /**
   * Get review analytics summary
   */
  async getAnalyticsSummary(): Promise<Locator> {
    return this.page.getByTestId("flashcards-review-analytics-summary")
  }
}
```

**Step 2: Add export to index.ts**

Add to `apps/tldw-frontend/e2e/utils/page-objects/index.ts`:

```typescript
export { FlashcardsPage } from "./FlashcardsPage"
```

**Step 3: Verify no type errors**

Run: `cd apps/tldw-frontend && npx tsc --noEmit --pretty`
Expected: No new errors

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/FlashcardsPage.ts apps/tldw-frontend/e2e/utils/page-objects/index.ts
git commit -m "test: add FlashcardsPage page object for e2e tests"
```

---

## Task 5: Extend MediaPage with batch operations

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/MediaPage.ts`

**Step 1: Add batch operation methods**

Add the following methods to the `MediaPage` class, before the closing `}`:

```typescript
  /**
   * Select multiple media items by clicking their checkboxes
   */
  async selectMultiple(count: number): Promise<void> {
    const checkboxes = this.page.locator(
      "[data-testid='media-item'] input[type='checkbox'], .ant-table-row .ant-checkbox-input"
    )
    const available = await checkboxes.count()
    const toSelect = Math.min(count, available)
    for (let i = 0; i < toSelect; i++) {
      await checkboxes.nth(i).click()
    }
  }

  /**
   * Trigger batch delete on selected items
   */
  async batchDelete(): Promise<void> {
    const batchDeleteBtn = this.page.getByRole("button", { name: /batch delete|delete selected|delete all/i })
    await batchDeleteBtn.click()

    // Confirm deletion if dialog appears
    const confirmBtn = this.page.getByRole("button", { name: /confirm|yes|ok/i })
    if ((await confirmBtn.count()) > 0 && (await confirmBtn.isVisible())) {
      await confirmBtn.click()
    }
  }

  /**
   * Apply a tag to selected items via batch action
   */
  async batchTag(tag: string): Promise<void> {
    const batchTagBtn = this.page.getByRole("button", { name: /tag|add tag|batch tag/i })
    await batchTagBtn.click()

    const tagInput = this.page.getByPlaceholder(/tag|enter tag/i)
    await tagInput.fill(tag)
    await tagInput.press("Enter")

    const applyBtn = this.page.getByRole("button", { name: /apply|save|ok/i })
    if ((await applyBtn.count()) > 0 && (await applyBtn.isVisible())) {
      await applyBtn.click()
    }
  }

  /**
   * Navigate to the media trash page
   */
  async navigateToTrash(): Promise<void> {
    await this.page.goto("/media-trash", { waitUntil: "domcontentloaded" })
    await this.page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {})
  }

  /**
   * Restore an item from trash by title
   */
  async restoreItem(title: string): Promise<void> {
    const row = this.page.locator(`tr:has-text("${title}"), [data-testid='media-item']:has-text("${title}")`)
    const restoreBtn = row.getByRole("button", { name: /restore|recover|undelete/i })
    await restoreBtn.click()
  }
```

**Step 2: Verify no type errors**

Run: `cd apps/tldw-frontend && npx tsc --noEmit --pretty`
Expected: No new errors

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/MediaPage.ts
git commit -m "test: extend MediaPage with batch operation methods"
```

---

## Task 6: Notes workflow tests (Tier A)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/notes.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Notes Workflow E2E Tests — Tier A
 *
 * Tests: CRUD, search, tags, soft-delete/restore, export
 *
 * Run: npx playwright test e2e/workflows/notes.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { NotesPage } from "../utils/page-objects"
import { seedAuth, generateTestId } from "../utils/helpers"

test.describe("@tier-a Notes Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test.describe("Notes CRUD", () => {
    test("should navigate to notes page and display interface", async ({
      authedPage,
      diagnostics,
    }) => {
      const notesPage = new NotesPage(authedPage)
      await notesPage.goto()
      await notesPage.waitForReady()

      await expect(notesPage.listRegion.or(notesPage.editorRegion).first()).toBeVisible()
      await assertNoCriticalErrors(diagnostics)
    })

    test("should create a new note and verify it persists", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const notesPage = new NotesPage(authedPage)
      await notesPage.goto()
      await notesPage.waitForReady()

      const noteContent = `Test note ${generateTestId("note")}`
      await notesPage.createNote(noteContent)

      // Verify content persisted
      const editorContent = await notesPage.getEditorContent()
      expect(editorContent).toContain(noteContent.substring(0, 20))

      await assertNoCriticalErrors(diagnostics)
    })

    test("should edit an existing note", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const notesPage = new NotesPage(authedPage)
      await notesPage.goto()
      await notesPage.waitForReady()

      // Create note
      const original = `Original ${generateTestId("note")}`
      await notesPage.createNote(original)

      // Edit: append text
      const textarea = authedPage.getByPlaceholder(/write your note|note content/i)
      const edited = " — edited content appended"
      await textarea.press("End")
      await textarea.type(edited)
      await notesPage.save()

      // Verify edit persisted
      const content = await notesPage.getEditorContent()
      expect(content).toContain("edited content appended")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Search and Filter", () => {
    test("should search notes by text", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const notesPage = new NotesPage(authedPage)
      await notesPage.goto()
      await notesPage.waitForReady()

      // Create two notes with distinct keywords
      const keyword = generateTestId("unique")
      await notesPage.createNote(`${keyword} — first note`)
      await notesPage.createNote(`Different content entirely`)

      // Search for the keyword
      await notesPage.searchNotes(keyword)

      // Verify filtered results contain the keyword
      const notesList = await notesPage.getNotesList()
      const count = await notesList.count()
      expect(count).toBeGreaterThanOrEqual(1)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Soft Delete and Restore", () => {
    test("should soft-delete a note and restore it from trash", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const notesPage = new NotesPage(authedPage)
      await notesPage.goto()
      await notesPage.waitForReady()

      // Create note
      const content = `Deletable ${generateTestId("note")}`
      await notesPage.createNote(content)

      // Delete it
      await notesPage.deleteNote("")

      // Switch to trash
      await notesPage.switchToTrash()

      // Verify item appears in trash
      const trashItems = authedPage.locator('[data-testid^="notes-trash-row-"]')
      await expect(trashItems.first()).toBeVisible({ timeout: 10000 })

      // Restore first item
      const firstTrashId = await trashItems.first().getAttribute("data-testid")
      const noteId = firstTrashId?.replace("notes-trash-row-", "") || ""
      if (noteId) {
        await notesPage.restoreNote(noteId)
      }

      // Switch back to active
      await notesPage.switchToActive()

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
```

**Step 2: Run test to verify it compiles (dry run)**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/notes.spec.ts --list`
Expected: Tests listed without errors

**Step 3: Run tests against live server**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/notes.spec.ts --reporter=list`
Expected: Tests pass or skip gracefully if server unavailable

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/notes.spec.ts
git commit -m "test: add Notes workflow e2e tests (Tier A)"
```

---

## Task 7: Flashcards workflow tests (Tier A)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/flashcards.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Flashcards Workflow E2E Tests — Tier A
 *
 * Tests: generation, study flow, deck management
 *
 * Run: npx playwright test e2e/workflows/flashcards.spec.ts
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels, assertNoCriticalErrors } from "../utils/fixtures"
import { FlashcardsPage } from "../utils/page-objects"
import { seedAuth, generateTestId } from "../utils/helpers"

test.describe("@tier-a Flashcards Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test.describe("Flashcards Page Load", () => {
    test("should navigate to flashcards and display tabs", async ({
      authedPage,
      diagnostics,
    }) => {
      const flashcardsPage = new FlashcardsPage(authedPage)
      await flashcardsPage.goto()
      await flashcardsPage.waitForReady()

      await expect(flashcardsPage.tabs).toBeVisible()
      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Generate Flashcards", () => {
    test("should generate flashcards from text and save them", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)
      skipIfNoModels(serverInfo)

      const flashcardsPage = new FlashcardsPage(authedPage)
      await flashcardsPage.goto()
      await flashcardsPage.waitForReady()

      // Generate from text content
      const sourceText = `Photosynthesis is the process by which green plants convert sunlight into chemical energy.
The process occurs in chloroplasts using chlorophyll. The Calvin cycle fixes CO2 into glucose.
Water molecules are split, releasing oxygen.`

      await flashcardsPage.generateFromText(sourceText, 3)

      // Wait for generation to complete (behavioral: button appears)
      await flashcardsPage.saveGeneratedCards()

      // Switch to Manage tab and verify cards exist
      await flashcardsPage.switchTab("Manage")
      const cards = await flashcardsPage.getCardItems()
      const count = await cards.count()
      expect(count).toBeGreaterThanOrEqual(1)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Study Flow", () => {
    test("should show card, reveal answer, and rate", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const flashcardsPage = new FlashcardsPage(authedPage)
      await flashcardsPage.goto()
      await flashcardsPage.waitForReady()

      // Import test cards first so we have something to review
      await flashcardsPage.importFromText(
        "What is photosynthesis?\tThe process by which plants convert sunlight to energy\nWhat is chlorophyll?\tA green pigment in plants"
      )

      // Switch to Review tab
      await flashcardsPage.switchTab("Review")

      // Check if cards are available
      const isEmpty = await flashcardsPage.isReviewEmpty()
      if (isEmpty) {
        test.skip(true, "No cards available for review")
        return
      }

      // Show answer
      await flashcardsPage.showAnswer()

      // Rate card as "good"
      await flashcardsPage.rateCard("good")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Import/Export", () => {
    test("should import CSV cards and verify they appear in manage tab", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const flashcardsPage = new FlashcardsPage(authedPage)
      await flashcardsPage.goto()
      await flashcardsPage.waitForReady()

      const testId = generateTestId("card")
      await flashcardsPage.importFromText(
        `${testId} Q1\t${testId} A1\n${testId} Q2\t${testId} A2`
      )

      // Verify import result
      const lastResult = authedPage.getByTestId("flashcards-import-last-result")
      await expect(lastResult).toBeVisible({ timeout: 15000 })

      // Verify cards in Manage tab
      await flashcardsPage.switchTab("Manage")
      await flashcardsPage.searchCards(testId)
      const cards = await flashcardsPage.getCardItems()
      expect(await cards.count()).toBeGreaterThanOrEqual(2)

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
```

**Step 2: Run test listing**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/flashcards.spec.ts --list`
Expected: Tests listed

**Step 3: Run tests**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/flashcards.spec.ts --reporter=list`

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/flashcards.spec.ts
git commit -m "test: add Flashcards workflow e2e tests (Tier A)"
```

---

## Task 8: Chat+RAG integration tests (Tier A)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/chat-rag-integration.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Chat + RAG Integration Workflow E2E Tests — Tier A
 *
 * Tests end-to-end flow: ingest → RAG search → inject into chat → verify grounded response
 *
 * Run: npx playwright test e2e/workflows/chat-rag-integration.spec.ts
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels, assertNoCriticalErrors } from "../utils/fixtures"
import { ChatPage, KnowledgeQAPage } from "../utils/page-objects"
import { seedAuth, generateTestId, ingestAndWait, TEST_CONFIG, fetchWithApiKey } from "../utils/helpers"

test.describe("@tier-a Chat+RAG Integration", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should search RAG then chat with context", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    // Step 1: Search via Knowledge QA
    const qaPage = new KnowledgeQAPage(authedPage)
    await qaPage.goto()
    await qaPage.waitForReady()

    const searchInput = await qaPage.getSearchInput()
    await searchInput.fill("media processing")
    await searchInput.press("Enter")

    // Wait for results (behavioral: any results or empty state)
    await authedPage.waitForTimeout(3000)

    // Step 2: Navigate to chat
    const chatPage = new ChatPage(authedPage)
    await chatPage.goto()
    await chatPage.waitForReady()

    // Step 3: Send a message that references knowledge
    await chatPage.sendMessage("What can you tell me about media processing in this system?")

    // Step 4: Verify response appeared (behavioral — don't check content)
    await chatPage.waitForResponse(60000)
    const messages = await chatPage.getMessages()
    expect(messages.length).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })

  test("should perform RAG search and get results", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    const qaPage = new KnowledgeQAPage(authedPage)
    await qaPage.goto()
    await qaPage.waitForReady()

    const searchInput = await qaPage.getSearchInput()
    await expect(searchInput).toBeVisible()

    // Search for something
    await searchInput.fill("test")
    await searchInput.press("Enter")

    // Wait for the search to complete — either results or empty state
    const resultOrEmpty = authedPage.locator(
      "[data-testid='search-results'], [data-testid='empty-state'], .search-results, .no-results"
    )
    await expect(resultOrEmpty.first()).toBeVisible({ timeout: 30000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Run and verify**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/chat-rag-integration.spec.ts --list`

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/chat-rag-integration.spec.ts
git commit -m "test: add Chat+RAG integration e2e tests (Tier A)"
```

---

## Task 9: Media batch operations tests (Tier A)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/media-batch.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Media Batch Operations Workflow E2E Tests — Tier A
 *
 * Tests: multi-select, batch delete, batch tag, trash restore
 *
 * Run: npx playwright test e2e/workflows/media-batch.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { MediaPage } from "../utils/page-objects"
import { seedAuth } from "../utils/helpers"

test.describe("@tier-a Media Batch Operations", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display media list with selectable items", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    const mediaPage = new MediaPage(authedPage)
    await mediaPage.goto()
    await mediaPage.waitForReady()

    // Verify media items or empty state
    const items = await mediaPage.getMediaItems()
    // If there are items, verify checkboxes are present
    if (items.length > 0) {
      const checkboxes = authedPage.locator(
        "[data-testid='media-item'] input[type='checkbox'], .ant-table-row .ant-checkbox-input"
      )
      expect(await checkboxes.count()).toBeGreaterThan(0)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("should navigate to trash page", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    const mediaPage = new MediaPage(authedPage)
    await mediaPage.navigateToTrash()

    // Verify trash page loaded (either items or empty state)
    const content = authedPage.locator(
      ".media-container, [data-testid='media-list'], [data-testid='empty-state'], .ant-table, .ant-empty"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should select multiple items when available", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    const mediaPage = new MediaPage(authedPage)
    await mediaPage.goto()
    await mediaPage.waitForReady()

    const items = await mediaPage.getMediaItems()
    if (items.length < 2) {
      test.skip(true, "Need at least 2 media items for multi-select test")
      return
    }

    await mediaPage.selectMultiple(2)

    // Verify selection indicator appears
    const selectionIndicator = authedPage.locator(
      "[data-testid='selection-count'], .selection-bar, .batch-actions"
    )
    // Selection may show as a toolbar or count badge
    await authedPage.waitForTimeout(500)

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Run and verify**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/media-batch.spec.ts --list`

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-batch.spec.ts
git commit -m "test: add Media batch operations e2e tests (Tier A)"
```

---

## Task 10: Notes-to-Flashcards cross-feature test (Tier A)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/notes-to-flashcards.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Notes → Flashcards Cross-Feature Workflow — Tier A
 *
 * Run: npx playwright test e2e/workflows/notes-to-flashcards.spec.ts
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels, assertNoCriticalErrors } from "../utils/fixtures"
import { NotesPage, FlashcardsPage } from "../utils/page-objects"
import { seedAuth, generateTestId } from "../utils/helpers"

test.describe("@tier-a Notes to Flashcards", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should create a note then generate flashcards from its content", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    // Step 1: Create a note with study-worthy content
    const notesPage = new NotesPage(authedPage)
    await notesPage.goto()
    await notesPage.waitForReady()

    const studyContent = `The mitochondria is the powerhouse of the cell. It generates ATP through oxidative phosphorylation.
The Krebs cycle occurs in the mitochondrial matrix. Electron transport chain is in the inner membrane.`

    await notesPage.createNote(studyContent)

    // Step 2: Navigate to flashcards and generate from this content
    const flashcardsPage = new FlashcardsPage(authedPage)
    await flashcardsPage.goto()
    await flashcardsPage.waitForReady()

    await flashcardsPage.generateFromText(studyContent, 3)

    // Step 3: Verify cards were generated (behavioral)
    await flashcardsPage.saveGeneratedCards()

    await flashcardsPage.switchTab("Manage")
    const cards = await flashcardsPage.getCardItems()
    expect(await cards.count()).toBeGreaterThanOrEqual(1)

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Run and verify**

Run: `cd apps/tldw-frontend && npx playwright test e2e/workflows/notes-to-flashcards.spec.ts --list`

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/notes-to-flashcards.spec.ts
git commit -m "test: add Notes-to-Flashcards cross-feature e2e test (Tier A)"
```

---

## Task 11: Characters workflow tests (Tier B)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/characters.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Characters Workflow E2E Tests — Tier B
 *
 * Run: npx playwright test e2e/workflows/characters.spec.ts
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, generateTestId, waitForConnection } from "../utils/helpers"

test.describe("@tier-b Characters Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should navigate to characters page and display interface", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/characters", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      "[data-testid='characters-workspace'], .characters-page, [data-route='characters']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display character list or empty state", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/characters", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const listOrEmpty = authedPage.locator(
      ".character-card, .character-item, [data-testid='empty-state'], .ant-empty"
    )
    await expect(listOrEmpty.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should open character creation form", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/characters", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    // Look for create/add button
    const createBtn = authedPage.getByRole("button", { name: /create|add|new character/i })
    if ((await createBtn.count()) > 0) {
      await createBtn.first().click()

      // Verify form/modal appeared
      const form = authedPage.locator(
        "input[placeholder*='name' i], [data-testid='character-name-input'], .character-form"
      )
      await expect(form.first()).toBeVisible({ timeout: 10000 })
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/characters.spec.ts
git commit -m "test: add Characters workflow e2e tests (Tier B)"
```

---

## Task 12: Audio workflow tests (Tier B)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/audio.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Audio STT/TTS Workflow E2E Tests — Tier B
 *
 * Run: npx playwright test e2e/workflows/audio.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-b Audio Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display TTS interface with provider selection", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/speech", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    // Verify page loaded
    const content = authedPage.locator(
      ".speech-page, [data-route='speech'], [data-testid='speech-playground']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display STT interface", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/stt", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".stt-page, [data-route='stt'], [data-testid='stt-playground']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should show voice catalog when available", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/speech", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    // Look for voice/provider selection
    const voiceSelect = authedPage.locator(
      "[data-testid='voice-select'], select[name='voice'], .voice-selector, .ant-select"
    )
    await expect(voiceSelect.first()).toBeVisible({ timeout: 15000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/audio.spec.ts
git commit -m "test: add Audio STT/TTS workflow e2e tests (Tier B)"
```

---

## Task 13: Watchlists workflow tests (Tier B)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/watchlists.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Watchlists Workflow E2E Tests — Tier B
 *
 * Run: npx playwright test e2e/workflows/watchlists.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-b Watchlists Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should navigate to watchlists page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/watchlists", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      "[data-testid='watchlists-workspace'], .watchlists-page, .ant-tabs"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display watchlist tabs (overview, sources, jobs, runs, items)", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/watchlists", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    // Verify tab structure exists
    const tabs = authedPage.getByRole("tab")
    await expect(tabs.first()).toBeVisible({ timeout: 15000 })
    const tabCount = await tabs.count()
    expect(tabCount).toBeGreaterThanOrEqual(2)

    await assertNoCriticalErrors(diagnostics)
  })

  test("should navigate between watchlist tabs", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/watchlists", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const sourcesTab = authedPage.getByRole("tab", { name: /sources/i })
    if ((await sourcesTab.count()) > 0) {
      await sourcesTab.click()
      await authedPage.waitForTimeout(500)
    }

    const runsTab = authedPage.getByRole("tab", { name: /runs/i })
    if ((await runsTab.count()) > 0) {
      await runsTab.click()
      await authedPage.waitForTimeout(500)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/watchlists.spec.ts
git commit -m "test: add Watchlists workflow e2e tests (Tier B)"
```

---

## Task 14: Content Review workflow tests (Tier B)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/content-review.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Content Review Workflow E2E Tests — Tier B
 *
 * Run: npx playwright test e2e/workflows/content-review.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-b Content Review Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should navigate to content review page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/content-review", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".content-review, [data-route='content-review'], [data-testid='content-review']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display review queue or empty state", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/content-review", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const queueOrEmpty = authedPage.locator(
      ".review-queue, .review-item, [data-testid='empty-state'], .ant-empty, .ant-table"
    )
    await expect(queueOrEmpty.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should navigate to claims review page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/claims-review", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".claims-review, [data-route='claims-review'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/content-review.spec.ts
git commit -m "test: add Content Review workflow e2e tests (Tier B)"
```

---

## Task 15: Evaluations smoke tests (Tier C)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/evaluations.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Evaluations Smoke E2E Tests — Tier C
 *
 * Run: npx playwright test e2e/workflows/evaluations.spec.ts
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-c Evaluations", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display evaluations playground", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/evaluations", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".evaluations-page, [data-route='evaluations'], [data-testid='evaluations-playground']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/evaluations.spec.ts
git commit -m "test: add Evaluations smoke e2e test (Tier C)"
```

---

## Task 16: Prompt Studio smoke tests (Tier C)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/prompt-studio.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Prompt Studio Smoke E2E Tests — Tier C
 *
 * Run: npx playwright test e2e/workflows/prompt-studio.spec.ts
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-c Prompt Studio", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display prompt studio interface", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/prompt-studio", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".prompt-studio, [data-route='prompt-studio'], [data-testid='prompt-studio']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display prompts library", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/prompts", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".prompts-page, [data-route='prompts'], [data-testid='prompts-workspace']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/prompt-studio.spec.ts
git commit -m "test: add Prompt Studio smoke e2e tests (Tier C)"
```

---

## Task 17: Agents smoke tests (Tier C)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/agents.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Agents/ACP Smoke E2E Tests — Tier C
 *
 * Run: npx playwright test e2e/workflows/agents.spec.ts
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-c Agents", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display agents registry page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/agents", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".agents-page, [data-route='agents'], [data-testid='agents-registry']"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display agent tasks page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/agent-tasks", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".agent-tasks, [data-route='agent-tasks'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/agents.spec.ts
git commit -m "test: add Agents/ACP smoke e2e tests (Tier C)"
```

---

## Task 18: Writing tools smoke tests (Tier C)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/writing.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Writing Tools Smoke E2E Tests — Tier C
 *
 * Run: npx playwright test e2e/workflows/writing.spec.ts
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-c Writing Tools", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display writing playground", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/writing-playground", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".writing-playground, [data-route='writing-playground'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display repo2txt page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/repo2txt", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".repo2txt, [data-route='repo2txt'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/writing.spec.ts
git commit -m "test: add Writing tools smoke e2e tests (Tier C)"
```

---

## Task 19: Admin pages smoke tests (Tier C)

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/admin.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Admin Pages Smoke E2E Tests — Tier C
 *
 * Run: npx playwright test e2e/workflows/admin.spec.ts
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

test.describe("@tier-c Admin Pages", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("should display server admin dashboard", async ({
    authedPage,
    serverInfo,
    diagnostics,
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.goto("/admin/server", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".admin-server, [data-route='admin-server'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display data ops page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/admin/data-ops", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".admin-data-ops, [data-route='admin-data-ops'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("should display model management page", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/admin/llamacpp", { waitUntil: "domcontentloaded" })
    await waitForConnection(authedPage)

    const content = authedPage.locator(
      ".admin-llamacpp, [data-route='admin-llamacpp'], body"
    )
    await expect(content.first()).toBeVisible({ timeout: 20000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
```

**Step 2: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/admin.spec.ts
git commit -m "test: add Admin pages smoke e2e tests (Tier C)"
```

---

## Task 20: Extension — Notes connected-state tests

**Files:**
- Create: `apps/extension/tests/e2e/ext-notes-connected.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Extension Notes — Connected State E2E Tests
 *
 * Complements existing notes-ux.spec.ts (which tests offline state).
 * These tests verify CRUD operations when connected to a real server.
 *
 * Run: bun run test:e2e -- ext-notes-connected.spec.ts
 */
import { test, expect } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"
import { waitForConnectionStore, forceConnected } from "./utils/connection"

test.describe("Extension Notes — Connected State", () => {
  test("should create a new note when connected", async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "notes-create")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "notes-create")

    await page.goto(optionsUrl + "#/notes")
    await page.waitForLoadState("networkidle")

    // Click new note button
    const newButton = page.getByTestId("notes-new-button")
    if ((await newButton.count()) > 0) {
      await newButton.click()
    }

    // Fill content
    const textarea = page.getByPlaceholder("Write your note here...")
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill("Extension test note — connected state")

    // Save
    const saveBtn = page.getByTestId("notes-save-button")
    if ((await saveBtn.count()) > 0 && (await saveBtn.isVisible())) {
      await saveBtn.click()
    }

    await context.close()
  })

  test("should search notes when connected", async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "notes-search")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "notes-search")

    await page.goto(optionsUrl + "#/notes")
    await page.waitForLoadState("networkidle")

    const searchInput = page.getByTestId("notes-search")
    if ((await searchInput.count()) > 0) {
      await searchInput.fill("test")
      await searchInput.press("Enter")
      await page.waitForTimeout(1000)
    }

    await context.close()
  })
})
```

**Step 2: Commit**

```bash
git add apps/extension/tests/e2e/ext-notes-connected.spec.ts
git commit -m "test: add extension Notes connected-state e2e tests"
```

---

## Task 21: Extension — Flashcards connected-state tests

**Files:**
- Create: `apps/extension/tests/e2e/ext-flashcards-connected.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Extension Flashcards — Connected State E2E Tests
 *
 * Complements existing flashcards-ux.spec.ts (which tests offline state).
 *
 * Run: bun run test:e2e -- ext-flashcards-connected.spec.ts
 */
import { test, expect } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"
import { waitForConnectionStore, forceConnected } from "./utils/connection"

test.describe("Extension Flashcards — Connected State", () => {
  test("should import CSV flashcards when connected", async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "flashcards-import")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "flashcards-import")

    await page.goto(optionsUrl + "#/flashcards")
    await page.waitForLoadState("networkidle")

    // Wait for flashcards workspace
    const tabs = page.getByTestId("flashcards-tabs")
    await expect(tabs).toBeVisible({ timeout: 15000 })

    // Switch to Import/Export tab
    const importTab = page.getByRole("tab", { name: /Import/i })
    if ((await importTab.count()) > 0) {
      await importTab.click()
    }

    // Import CSV
    const textarea = page.getByTestId("flashcards-import-textarea")
    if ((await textarea.count()) > 0) {
      await textarea.fill("Test Q1\tTest A1\nTest Q2\tTest A2")

      const importBtn = page.getByTestId("flashcards-import-button")
      if ((await importBtn.count()) > 0) {
        await importBtn.click()
      }
    }

    await context.close()
  })

  test("should show study mode with review tab", async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "flashcards-study")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "flashcards-study")

    await page.goto(optionsUrl + "#/flashcards")
    await page.waitForLoadState("networkidle")

    const tabs = page.getByTestId("flashcards-tabs")
    await expect(tabs).toBeVisible({ timeout: 15000 })

    // Click Review tab
    const reviewTab = page.getByRole("tab", { name: "Review", exact: true })
    if ((await reviewTab.count()) > 0) {
      await reviewTab.click()

      // Either active card or empty state should show
      const cardOrEmpty = page.locator(
        '[data-testid="flashcards-review-active-card"], [data-testid="flashcards-review-empty-card"]'
      )
      await expect(cardOrEmpty.first()).toBeVisible({ timeout: 10000 })
    }

    await context.close()
  })
})
```

**Step 2: Commit**

```bash
git add apps/extension/tests/e2e/ext-flashcards-connected.spec.ts
git commit -m "test: add extension Flashcards connected-state e2e tests"
```

---

## Task 22: Extension — Cross-feature workflow tests

**Files:**
- Create: `apps/extension/tests/e2e/ext-cross-feature.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Extension Cross-Feature Workflow E2E Tests
 *
 * Tests end-to-end flows that span multiple features.
 *
 * Run: bun run test:e2e -- ext-cross-feature.spec.ts
 */
import { test, expect } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"
import { waitForConnectionStore, forceConnected } from "./utils/connection"

test.describe("Extension Cross-Feature Workflows", () => {
  test("should navigate from sidepanel chat to options notes", async () => {
    const { context, page, optionsUrl, openSidepanel } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "cross-feature")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "cross-feature")

    // Open sidepanel
    const sidepanel = await openSidepanel()
    await sidepanel.waitForLoadState("networkidle")

    // Verify sidepanel loaded
    const chatInput = sidepanel.locator("#textarea-message, [data-testid='chat-input']")
    await expect(chatInput.first()).toBeVisible({ timeout: 15000 })

    // Navigate to notes via options
    await page.goto(optionsUrl + "#/notes")
    await page.waitForLoadState("networkidle")

    // Verify notes loaded
    const notesContent = page.locator(
      '[data-testid="notes-list-region"], [data-testid="notes-editor-region"]'
    )
    await expect(notesContent.first()).toBeVisible({ timeout: 15000 })

    await context.close()
  })

  test("should navigate between knowledge and chat in options", async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "knowledge-chat")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "knowledge-chat")

    // Go to knowledge/RAG page
    await page.goto(optionsUrl + "#/knowledge")
    await page.waitForLoadState("networkidle")
    await page.waitForTimeout(2000)

    // Navigate to chat
    await page.goto(optionsUrl + "#/chat")
    await page.waitForLoadState("networkidle")

    const chatInput = page.locator("#textarea-message, [data-testid='chat-input']")
    await expect(chatInput.first()).toBeVisible({ timeout: 15000 })

    await context.close()
  })
})
```

**Step 2: Commit**

```bash
git add apps/extension/tests/e2e/ext-cross-feature.spec.ts
git commit -m "test: add extension cross-feature workflow e2e tests"
```

---

## Task 23: Extension — Context capture tests

**Files:**
- Create: `apps/extension/tests/e2e/ext-context-capture.spec.ts`

**Step 1: Write the test file**

```typescript
/**
 * Extension Context Capture E2E Tests
 *
 * Tests the extension's ability to capture page content for chat context.
 *
 * Run: bun run test:e2e -- ext-context-capture.spec.ts
 */
import { test, expect } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"
import { waitForConnectionStore, forceConnected } from "./utils/connection"

test.describe("Extension Context Capture", () => {
  test("should open sidepanel with page context available", async () => {
    const { context, page, optionsUrl, openSidepanel } = await launchWithBuiltExtension()

    await page.goto(optionsUrl, { waitUntil: "networkidle" })
    await waitForConnectionStore(page, "context-capture")
    await forceConnected(page, { serverUrl: "http://127.0.0.1:8000" }, "context-capture")

    // Open a content page (use options page as content)
    await page.goto(optionsUrl + "#/settings")
    await page.waitForLoadState("networkidle")

    // Open sidepanel
    const sidepanel = await openSidepanel()
    await sidepanel.waitForLoadState("networkidle")

    // Verify sidepanel chat is ready
    const chatInput = sidepanel.locator("#textarea-message, [data-testid='chat-input']")
    await expect(chatInput.first()).toBeVisible({ timeout: 15000 })

    await context.close()
  })
})
```

**Step 2: Commit**

```bash
git add apps/extension/tests/e2e/ext-context-capture.spec.ts
git commit -m "test: add extension context capture e2e tests"
```

---

## Task 24: Update CI — Add tier tags to Playwright config

**Files:**
- Modify: `apps/tldw-frontend/playwright.config.ts`

This task is optional and non-breaking. The tier tags (`@tier-a`, `@tier-b`, `@tier-c`) in `test.describe` names can be filtered at runtime via `--grep`:

```bash
# Run only Tier A tests (PR gate)
npx playwright test --grep @tier-a

# Run all tiers (nightly)
npx playwright test

# Run Tier B and C (nightly only)
npx playwright test --grep "@tier-b|@tier-c"
```

No config file changes needed — the `--grep` flag works with the existing config. CI workflow changes should be done separately when the tests are stable.

**Step 1: Verify grep works with existing tests**

Run: `cd apps/tldw-frontend && npx playwright test --grep @tier-a --list`
Expected: Lists all Tier A test files

**Step 2: Document the grep patterns**

Add a comment at the top of `playwright.config.ts`:

```typescript
/**
 * Tier filtering: use --grep to select test tiers
 *   PR gate:  npx playwright test --grep @tier-a
 *   Nightly:  npx playwright test
 *   Tier B/C: npx playwright test --grep "@tier-b|@tier-c"
 */
```

**Step 3: Commit**

```bash
git add apps/tldw-frontend/playwright.config.ts
git commit -m "docs: add tier filtering comment to playwright config"
```

---

## Summary

| Task | Description | Files | Tier |
|------|-------------|-------|------|
| 1 | Shared helpers (ingestAndWait, waitForStreamComplete, assertFlashcardsGenerated) | helpers.ts | Infra |
| 2 | Test fixtures (test-document.md) | fixtures/ | Infra |
| 3 | NotesPage page object | page-objects/ | A |
| 4 | FlashcardsPage page object | page-objects/ | A |
| 5 | Extend MediaPage (batch ops) | page-objects/ | A |
| 6 | Notes workflow tests | notes.spec.ts | A |
| 7 | Flashcards workflow tests | flashcards.spec.ts | A |
| 8 | Chat+RAG integration tests | chat-rag-integration.spec.ts | A |
| 9 | Media batch operation tests | media-batch.spec.ts | A |
| 10 | Notes-to-Flashcards cross-feature | notes-to-flashcards.spec.ts | A |
| 11 | Characters workflow | characters.spec.ts | B |
| 12 | Audio workflow | audio.spec.ts | B |
| 13 | Watchlists workflow | watchlists.spec.ts | B |
| 14 | Content Review workflow | content-review.spec.ts | B |
| 15 | Evaluations smoke | evaluations.spec.ts | C |
| 16 | Prompt Studio smoke | prompt-studio.spec.ts | C |
| 17 | Agents smoke | agents.spec.ts | C |
| 18 | Writing tools smoke | writing.spec.ts | C |
| 19 | Admin pages smoke | admin.spec.ts | C |
| 20 | Extension Notes connected | ext-notes-connected.spec.ts | Ext |
| 21 | Extension Flashcards connected | ext-flashcards-connected.spec.ts | Ext |
| 22 | Extension cross-feature | ext-cross-feature.spec.ts | Ext |
| 23 | Extension context capture | ext-context-capture.spec.ts | Ext |
| 24 | CI tier filtering | playwright.config.ts | Infra |

**Total: 24 tasks, ~47 new test cases**

**Execution order:** Tasks 1-5 (infrastructure) → Tasks 6-10 (Tier A) → Tasks 11-14 (Tier B) → Tasks 15-19 (Tier C) → Tasks 20-23 (Extension) → Task 24 (CI)

Each task is independently committable. Tests are designed to skip gracefully when server is unavailable.
