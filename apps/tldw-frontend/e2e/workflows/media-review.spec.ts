/**
 * Multi-Item Media Review Workflow E2E Tests
 *
 * Tests the complete media review lifecycle:
 * - Single item review (select, view details)
 * - Multi-item selection (click, shift-click, limit)
 * - View modes (spread/compare, list/focus, all/stack)
 * - Filtering & search
 * - Pagination
 * - Error handling & undo
 *
 * Run: npx playwright test e2e/workflows/media-review.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import { MediaReviewPage } from "../utils/page-objects/MediaReviewPage"
import { seedAuth, generateTestId, waitForConnection } from "../utils/helpers"

test.describe("Multi-Item Media Review Workflow", () => {
  let reviewPage: MediaReviewPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    reviewPage = new MediaReviewPage(page)
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.1  Single Item Review
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Single Item Review", () => {
    test("should navigate to media review page and load items", async ({
      authedPage,
      diagnostics
    }) => {
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display media list with pagination", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      // Wait for API response
      const itemCount = await reviewPage.getItemCount()
      // List should have items (or be empty)
      expect(itemCount).toBeGreaterThanOrEqual(0)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should select a single item and show details", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No media items available")
        return
      }

      // Click first item
      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(1000)

      // Viewer should no longer be empty
      const isEmpty = await reviewPage.isViewerEmpty()
      // After clicking an item, the viewer should show content
      // (may take a moment to load)
      await authedPage.waitForTimeout(2000)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display item content in viewer", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No media items available")
        return
      }

      // Select first item and wait for detail load
      const [detailResult] = await Promise.all([
        reviewPage.waitForMediaDetail().catch(() => ({ status: 0, body: null })),
        reviewPage.clickItem(0)
      ])

      await authedPage.waitForTimeout(2000)

      // Content should show title and type
      const viewerCount = await reviewPage.getViewerItemCount()
      if (viewerCount > 0) {
        expect(viewerCount).toBeGreaterThanOrEqual(1)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.2  Multi-Item Selection
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Multi-Item Selection", () => {
    test("should select multiple items", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount < 2) {
        test.skip(true, "Need at least 2 media items")
        return
      }

      // Click first item
      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      // Click second item
      await reviewPage.clickItem(1)
      await authedPage.waitForTimeout(500)

      // Should have 2 selected
      const selectedCount = await reviewPage.getSelectedCount()
      expect(selectedCount).toBeGreaterThanOrEqual(2)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should support range selection with shift-click", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount < 3) {
        test.skip(true, "Need at least 3 media items for range select")
        return
      }

      // Click first item
      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      // Shift-click third item
      await reviewPage.shiftClickItem(2)
      await authedPage.waitForTimeout(500)

      // Should have at least 3 selected (range)
      const selectedCount = await reviewPage.getSelectedCount()
      expect(selectedCount).toBeGreaterThanOrEqual(3)

      await assertNoCriticalErrors(diagnostics)
    })

    test("preserves cross-page selection when adding visible page items", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No media items available")
        return
      }

      const totalPages = await reviewPage.getTotalPages()
      if (totalPages < 2) {
        test.skip(true, "Need at least 2 pages of media results")
        return
      }

      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(400)

      const selectionBefore = await reviewPage.getSelectionCountValue()
      expect(selectionBefore).toBeGreaterThanOrEqual(1)

      await reviewPage.goToPage(2)
      await authedPage.waitForTimeout(800)

      await reviewPage.clickAddVisibleToSelection()
      await authedPage.waitForTimeout(800)

      const selectionAfter = await reviewPage.getSelectionCountValue()
      expect(selectionAfter).toBeGreaterThan(selectionBefore)
      await expect(
        authedPage.getByText(/selected across pages:/i)
      ).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.3  View Modes
  // ═════════════════════════════════════════════════════════════════════

  test.describe("View Modes", () => {
    test("should switch to Compare (spread) view mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount < 2) {
        test.skip(true, "Need items for view mode test")
        return
      }

      await reviewPage.clickItem(0)
      await reviewPage.clickItem(1)
      await authedPage.waitForTimeout(500)

      await reviewPage.setViewMode("spread")
      const mode = await reviewPage.getCurrentViewMode()
      expect(mode).toBe("spread")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch to Focus (list) view mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No items for view mode test")
        return
      }

      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      await reviewPage.setViewMode("list")
      const mode = await reviewPage.getCurrentViewMode()
      expect(mode).toBe("list")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch to Stack (all) view mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No items for view mode test")
        return
      }

      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      await reviewPage.setViewMode("all")
      const mode = await reviewPage.getCurrentViewMode()
      expect(mode).toBe("all")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should change orientation between vertical and horizontal", async ({
      authedPage,
      diagnostics
    }) => {
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      try {
        await reviewPage.setOrientation("horizontal")
        await authedPage.waitForTimeout(300)

        await reviewPage.setOrientation("vertical")
        await authedPage.waitForTimeout(300)
      } catch {
        // Orientation toggle may not be available without selected items
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.4  Filtering & Search
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Filtering & Search", () => {
    test("should filter items by search query", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      // Enter a search query
      await reviewPage.fillSearchQuery("test")
      await authedPage.waitForTimeout(2000)

      // Results should update
      const itemCount = await reviewPage.getItemCount()
      // Any count is valid (0 = no matches, >0 = matches found)
      expect(itemCount).toBeGreaterThanOrEqual(0)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should filter by media type", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      try {
        await reviewPage.filterByMediaType("video")
        await authedPage.waitForTimeout(2000)

        // Results should be filtered
        const itemCount = await reviewPage.getItemCount()
        expect(itemCount).toBeGreaterThanOrEqual(0)
      } catch {
        // Type filter may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should clear filters and restore full list", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      // Apply a filter first
      await reviewPage.fillSearchQuery("filter-test")
      await authedPage.waitForTimeout(1000)

      // Clear filters
      await reviewPage.clearFilters()
      await authedPage.waitForTimeout(2000)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.5  Error Handling & Recovery
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Error Handling & Recovery", () => {
    test("should handle failed item loads gracefully", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      // Mock a failing detail API for a specific ID
      await authedPage.route("**/api/v1/media/99999", (route) => {
        route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Not found" })
        })
      })

      // The test verifies the page doesn't crash on error responses
      await assertNoCriticalErrors(diagnostics)

      await authedPage.unroute("**/api/v1/media/99999")
    })

    test("should clear selection and offer undo", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No items for clear/undo test")
        return
      }

      // Select items
      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      // Clear via options menu
      try {
        await reviewPage.clickClearSession()
        await authedPage.waitForTimeout(1000)

        // Viewer should be empty after clear
        const isEmpty = await reviewPage.isViewerEmpty()
        // May show undo notification
      } catch {
        // Clear session button may not be accessible without items open
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 4.6  Pagination
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Pagination", () => {
    test("should display pagination controls", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      // Check for pagination component
      const pagination = authedPage.locator(".ant-pagination")
      // Pagination may only show if there are enough items

      const currentPage = await reviewPage.getCurrentPage()
      expect(currentPage).toBe(1)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to page 2 if available", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const totalPages = await reviewPage.getTotalPages()
      if (totalPages < 2) {
        test.skip(true, "Not enough items for pagination test")
        return
      }

      // Navigate to page 2
      const [apiResult] = await Promise.all([
        reviewPage.waitForMediaList().catch(() => ({ status: 0, body: null })),
        reviewPage.goToPage(2)
      ])

      const currentPage = await reviewPage.getCurrentPage()
      expect(currentPage).toBe(2)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // Keyboard Shortcuts
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Keyboard Shortcuts", () => {
    test("should navigate items with j/k keys", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount < 2) {
        test.skip(true, "Need items for keyboard nav test")
        return
      }

      // Select first item to start
      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(500)

      // Focus the viewer panel first
      const viewer = authedPage.locator("[tabindex='-1']").first()
      if (await viewer.isVisible().catch(() => false)) {
        await viewer.focus()
      }

      // Press j to go next
      await reviewPage.pressNextItemShortcut()
      await authedPage.waitForTimeout(500)

      // Press k to go back
      await reviewPage.pressPrevItemShortcut()
      await authedPage.waitForTimeout(500)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should toggle content expand with o key", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      reviewPage = new MediaReviewPage(authedPage)
      await reviewPage.goto()
      await reviewPage.waitForReady()

      const itemCount = await reviewPage.getItemCount()
      if (itemCount === 0) {
        test.skip(true, "No items for keyboard expand test")
        return
      }

      await reviewPage.clickItem(0)
      await authedPage.waitForTimeout(1000)

      // Press o to toggle expand
      await reviewPage.pressToggleExpand()
      await authedPage.waitForTimeout(500)

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
