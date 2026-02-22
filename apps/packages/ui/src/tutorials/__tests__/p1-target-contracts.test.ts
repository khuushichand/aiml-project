import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { getTutorialById } from "../registry"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(testDir, "../../")

const readSource = (relativePath: string): string =>
  readFileSync(path.resolve(srcRoot, relativePath), "utf8")

describe("P1 tutorial selector contracts", () => {
  it("uses stable selector formats for all P1 tutorial steps", () => {
    const p1TutorialIds = [
      "prompts-basics",
      "evaluations-basics",
      "notes-basics",
      "flashcards-basics",
      "world-books-basics"
    ]

    for (const tutorialId of p1TutorialIds) {
      const tutorial = getTutorialById(tutorialId)
      expect(tutorial).toBeDefined()
      if (!tutorial) continue

      for (const step of tutorial.steps) {
        const selectors = step.target
          .split(",")
          .map((value) => value.trim())
          .filter((value) => value.length > 0)

        expect(selectors.length).toBeGreaterThan(0)
        for (const selector of selectors) {
          const isStableSelector =
            selector.startsWith('[data-testid="') || selector.startsWith("#")
          expect(isStableSelector).toBe(true)
        }
      }
    }
  })

  it("keeps required prompts tutorial anchors in source", () => {
    const content = readSource("components/Option/Prompt/index.tsx")
    const anchors = [
      'data-testid="prompts-segmented"',
      'data-testid="prompts-add"',
      'data-testid="prompts-search"',
      'data-testid="prompts-type-filter"',
      'data-testid="prompts-tag-filter"',
      'data-testid="prompts-export"',
      'data-testid="prompts-import"'
    ]

    for (const anchor of anchors) {
      expect(content).toContain(anchor)
    }
  })

  it("keeps required evaluations tutorial anchors in source", () => {
    const pageContent = readSource("components/Option/Evaluations/EvaluationsPage.tsx")
    const tabContent = readSource(
      "components/Option/Evaluations/tabs/EvaluationsTab.tsx"
    )
    const anchors = [
      'data-testid="evaluations-page-title"',
      'data-testid="evaluations-tabs"',
      'data-testid="evaluations-create-button"',
      'data-testid="evaluations-list-card"',
      'data-testid="evaluations-detail-card"'
    ]

    expect(pageContent).toContain(anchors[0])
    expect(pageContent).toContain(anchors[1])
    expect(tabContent).toContain(anchors[2])
    expect(tabContent).toContain(anchors[3])
    expect(tabContent).toContain(anchors[4])
  })

  it("keeps required notes tutorial anchors in source", () => {
    const managerContent = readSource("components/Notes/NotesManagerPage.tsx")
    const headerContent = readSource("components/Notes/NotesEditorHeader.tsx")
    const managerAnchors = [
      'data-testid="notes-list-region"',
      'data-testid="notes-mode-active"',
      'data-testid="notes-mode-trash"',
      'data-testid="notes-sort-select"',
      'data-testid="notes-notebook-select"',
      'data-testid="notes-editor-region"'
    ]

    for (const anchor of managerAnchors) {
      expect(managerContent).toContain(anchor)
    }
    expect(headerContent).toContain('data-testid="notes-save-button"')
  })

  it("keeps required flashcards tutorial anchors in source", () => {
    const managerContent = readSource("components/Flashcards/FlashcardsManager.tsx")
    const reviewContent = readSource("components/Flashcards/tabs/ReviewTab.tsx")
    const manageContent = readSource("components/Flashcards/tabs/ManageTab.tsx")
    const importExportContent = readSource(
      "components/Flashcards/tabs/ImportExportTab.tsx"
    )

    expect(managerContent).toContain('data-testid="flashcards-tabs"')
    expect(managerContent).toContain('data-testid="flashcards-to-quiz-cta"')
    expect(reviewContent).toContain('data-testid="flashcards-review-topbar"')
    expect(reviewContent).toContain('data-testid="flashcards-review-empty-card"')
    expect(manageContent).toContain('data-testid="flashcards-manage-topbar"')
    expect(manageContent).toContain('data-testid="flashcards-manage-search"')
    expect(importExportContent).toContain('data-testid="flashcards-import-format"')
    expect(importExportContent).toContain(
      'data-testid="flashcards-import-help-accordion"'
    )
  })

  it("keeps required world books tutorial anchors in source", () => {
    const workspaceContent = readSource(
      "components/Option/WorldBooks/WorldBooksWorkspace.tsx"
    )
    const managerContent = readSource("components/Option/WorldBooks/Manager.tsx")

    expect(workspaceContent).toContain('data-testid="world-books-tutorial-shell"')
    expect(managerContent).toContain('data-testid="world-books-search-input"')
    expect(managerContent).toContain('data-testid="world-books-enabled-filter"')
    expect(managerContent).toContain('data-testid="world-books-attachment-filter"')
    expect(managerContent).toContain('data-testid="world-books-table"')
    expect(managerContent).toContain('data-testid="world-books-new-button"')
    expect(managerContent).toContain('data-testid="world-books-import-button"')
  })
})
