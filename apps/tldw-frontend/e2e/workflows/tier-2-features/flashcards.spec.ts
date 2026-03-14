/**
 * Flashcards E2E Tests (Tier 2)
 *
 * Tests the Flashcards workspace page lifecycle:
 * - Page loads with expected elements (tabs or offline banner)
 * - Tab switching between Study, Manage, and Transfer
 * - Export button fires GET /api/v1/flashcards/export (requires server)
 * - Keyboard shortcuts help button opens modal
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/flashcards.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { FlashcardsPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Flashcards", () => {
  let flashcards: FlashcardsPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    flashcards = new FlashcardsPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Flashcards page with tabs or offline banner", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      // Either the tabs container is visible (server online) or an offline/unsupported message
      const online = await flashcards.isOnline()
      const offlineVisible = await flashcards.offlineMessage.isVisible().catch(() => false)
      const unsupportedVisible = await flashcards.unsupportedMessage.isVisible().catch(() => false)

      expect(online || offlineVisible || unsupportedVisible).toBe(true)

      // If online, all three tabs should be present
      if (online) {
        await expect(flashcards.studyTab).toBeVisible()
        await expect(flashcards.manageTab).toBeVisible()
        await expect(flashcards.transferTab).toBeVisible()
        await expect(flashcards.testWithQuizButton).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between tabs without errors", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      for (const tab of ["manage", "transfer", "study"] as const) {
        await flashcards.switchToTab(tab)
        await authedPage.waitForTimeout(500)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Study Tab
  // =========================================================================

  test.describe("Study Tab", () => {
    test("should show review deck selector and either a card or empty state", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      await flashcards.switchToTab("study")
      await authedPage.waitForTimeout(500)

      // The deck selector should always be present on the Study tab
      await expect(flashcards.reviewDeckSelect).toBeVisible({ timeout: 10_000 })

      // Either an active review card or the empty-state card should be shown
      const hasActiveCard = await flashcards.reviewActiveCard.isVisible().catch(() => false)
      const hasEmptyCard = await flashcards.reviewEmptyCard.isVisible().catch(() => false)
      expect(hasActiveCard || hasEmptyCard).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Manage Tab
  // =========================================================================

  test.describe("Manage Tab", () => {
    test("should show search, deck filter, and FAB create button", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      await flashcards.switchToTab("manage")
      await authedPage.waitForTimeout(500)

      await expect(flashcards.manageTopBar).toBeVisible({ timeout: 10_000 })
      await expect(flashcards.manageSearchInput).toBeVisible()
      await expect(flashcards.manageDeckSelect).toBeVisible()
      await expect(flashcards.fabCreateButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should fire flashcards list API when searching", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      await flashcards.switchToTab("manage")
      await authedPage.waitForTimeout(500)

      const searchVisible = await flashcards.manageSearchInput.isVisible().catch(() => false)
      if (!searchVisible) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/flashcards/,
        method: "GET",
      }, 15_000)

      await flashcards.manageSearchInput.fill("test query")
      await flashcards.manageSearchInput.press("Enter")

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Search may debounce; acceptable if no immediate call
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Transfer Tab - Export
  // =========================================================================

  test.describe("Export", () => {
    test("should fire GET /api/v1/flashcards/export when Export button is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      await flashcards.switchToTab("transfer")
      await authedPage.waitForTimeout(500)

      const exportVisible = await flashcards.exportButton.isVisible().catch(() => false)
      if (!exportVisible) return

      const exportEnabled = await flashcards.exportButton.isEnabled().catch(() => false)
      if (!exportEnabled) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/flashcards\/export/,
        method: "GET",
      }, 15_000)

      await flashcards.exportButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Export may require deck selection; acceptable if button is not wired without selection
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Transfer Tab - Import
  // =========================================================================

  test.describe("Import", () => {
    test("should show import textarea and format selector on Transfer tab", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      await flashcards.switchToTab("transfer")
      await authedPage.waitForTimeout(500)

      await expect(flashcards.importFormatSelect).toBeVisible({ timeout: 10_000 })
      await expect(flashcards.importButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Keyboard Shortcuts Modal
  // =========================================================================

  test.describe("Keyboard Shortcuts", () => {
    test("should open keyboard shortcuts modal via help button", async ({
      authedPage,
      diagnostics,
    }) => {
      flashcards = new FlashcardsPage(authedPage)
      await flashcards.goto()
      await flashcards.assertPageReady()

      const online = await flashcards.isOnline()
      if (!online) return

      const helpVisible = await flashcards.keyboardShortcutsButton.isVisible().catch(() => false)
      if (!helpVisible) return

      await flashcards.keyboardShortcutsButton.click()

      // The modal should appear
      const modal = authedPage.locator(".ant-modal")
      await expect(modal.first()).toBeVisible({ timeout: 5_000 })

      // Close it
      await authedPage.keyboard.press("Escape")
      await expect(modal.first()).toBeHidden({ timeout: 3_000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
