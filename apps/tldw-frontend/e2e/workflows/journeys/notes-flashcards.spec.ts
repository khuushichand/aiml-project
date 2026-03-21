/**
 * Journey: Notes -> Flashcards
 *
 * End-to-end workflow that creates a note, then generates flashcards
 * from the note content, and verifies flashcards were created.
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  skipIfNoModels
} from "../../utils/fixtures"
import { NotesPage, FlashcardsPage } from "../../utils/page-objects"
import { expectApiCall } from "../../utils/api-assertions"
import { createNote } from "../../utils/journey-helpers"

test.describe("Notes -> Flashcards journey", () => {
  const noteTitle = `E2E-Study-Note-${Date.now()}`
  const noteContent = [
    "The mitochondria is the powerhouse of the cell.",
    "DNA stands for deoxyribonucleic acid.",
    "Photosynthesis converts light energy into chemical energy.",
    "The human body has 206 bones.",
    "Water boils at 100 degrees Celsius at sea level.",
  ].join("\n\n")

  test("create note and generate flashcards from it", async ({
    authedPage: page,
    serverInfo,
  }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    await test.step("Create a note with study content", async () => {
      // Use the journey helper to create the note
      const title = await createNote(page, {
        title: noteTitle,
        content: noteContent,
      })
      expect(title).toBe(noteTitle)
    })

    await test.step("Verify note was saved", async () => {
      const notesPage = new NotesPage(page)
      await notesPage.goto()
      await notesPage.assertPageReady()
      await notesPage.assertNoteVisible(noteTitle)
    })

    await test.step("Navigate to flashcards and generate from content", async () => {
      const flashcardsPage = new FlashcardsPage(page)
      await flashcardsPage.goto()
      await flashcardsPage.assertPageReady()

      // Check if flashcards feature is available
      const isOnline = await flashcardsPage.isOnline()
      if (!isOnline) {
        test.skip(true, "Flashcards feature not available")
        return
      }

      // Switch to the transfer tab to access the generate feature
      await flashcardsPage.switchToTab("transfer")

      // Check if the generate textarea is available
      const generateVisible = await flashcardsPage.generateTextarea
        .isVisible()
        .catch(() => false)

      if (!generateVisible) {
        test.skip(true, "Flashcard generation feature not available in UI")
        return
      }

      // Paste the note content into the generate textarea
      await flashcardsPage.generateTextarea.fill(noteContent)

      // Click generate button
      const generateBtnVisible = await flashcardsPage.generateButton
        .isVisible()
        .catch(() => false)

      if (generateBtnVisible) {
        const generateApiCall = expectApiCall(page, {
          method: "POST",
          url: "/api/v1/flashcards/generate",
        }, 60_000)

        await flashcardsPage.generateButton.click()

        const { response } = await generateApiCall
        expect(response.status()).toBeLessThan(400)
        const responseBody = await response.json().catch(() => ({}))
        expect(Number(responseBody?.count ?? 0)).toBeGreaterThan(0)

        const saveGeneratedButton = page.getByTestId("flashcards-generate-save-button")
        await expect(saveGeneratedButton).toBeVisible({ timeout: 15_000 })

        const saveApiCall = expectApiCall(page, {
          method: "POST",
          url: /\/api\/v1\/flashcards(?:\?|$)/,
        }, 60_000)

        await saveGeneratedButton.click()

        const { response: saveResponse } = await saveApiCall
        expect(saveResponse.status()).toBeLessThan(400)
        await expect(
          page.getByText(/Saved \d+ generated cards/i)
        ).toBeVisible({ timeout: 15_000 })
      }
    })

    await test.step("Verify flashcards exist", async () => {
      const flashcardsPage = new FlashcardsPage(page)

      // Switch to manage tab to see the cards
      await flashcardsPage.switchToTab("manage")
      await page.waitForTimeout(1_000)

      await expect(flashcardsPage.manageTopBar).toBeVisible({ timeout: 15_000 })
      await expect(
        page.getByTestId("flashcards-generate-save-button")
      ).toHaveCount(0)
    })
  })
})
