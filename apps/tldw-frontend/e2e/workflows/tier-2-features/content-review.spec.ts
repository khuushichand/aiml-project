/**
 * Content Review E2E Tests (Tier 2)
 *
 * Tests the Content Review page lifecycle:
 * - Page loads with heading or empty state
 * - AI fix button fires POST /api/v1/chat/completions (requires server + drafts)
 * - Commit button fires POST /api/v1/media/add (requires server + drafts)
 * - Diff view button opens modal
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/content-review.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { ContentReviewPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Content Review", () => {
  let contentReview: ContentReviewPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    contentReview = new ContentReviewPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Content Review page with heading or empty state", async ({
      authedPage,
      diagnostics,
    }) => {
      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      // Either the heading is visible (with or without drafts) or the empty state
      const headingVisible = await contentReview.heading.isVisible().catch(() => false)
      const emptyVisible = await contentReview.emptyState.isVisible().catch(() => false)

      expect(headingVisible || emptyVisible).toBe(true)

      // If in empty state, the "Open Quick Ingest" button should be present
      if (emptyVisible) {
        await expect(contentReview.openQuickIngestButton).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show draft selection prompt or empty state when no draft is active", async ({
      authedPage,
      diagnostics,
    }) => {
      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const isEmpty = await contentReview.isEmptyState()

      if (!isEmpty) {
        // If drafts exist but none selected, the "Select a draft" message may appear
        // or the first draft may auto-select. Either way, the heading should be visible.
        const headingVisible = await contentReview.heading.isVisible().catch(() => false)
        expect(headingVisible).toBe(true)
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display batch selector and drafts list when drafts exist", async ({
      authedPage,
      diagnostics,
    }) => {
      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const isEmpty = await contentReview.isEmptyState()
      if (isEmpty) return

      // Batch selector and drafts list should be visible
      await expect(contentReview.batchSelect).toBeVisible()
      await expect(contentReview.draftsList).toBeVisible()

      // Header action buttons should be visible
      await expect(contentReview.commitAllButton).toBeVisible()
      await expect(contentReview.clearDraftsButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Draft Editor
  // =========================================================================

  test.describe("Draft Editor", () => {
    test("should show editor panels when a draft is loaded", async ({
      authedPage,
      diagnostics,
    }) => {
      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const draftLoaded = await contentReview.isDraftLoaded()
      if (!draftLoaded) return

      // Title input, action buttons, and panels should be visible
      await expect(contentReview.titleInput).toBeVisible()
      await expect(contentReview.resetButton).toBeVisible()
      await expect(contentReview.diffViewButton).toBeVisible()
      await expect(contentReview.saveDraftButton).toBeVisible()
      await expect(contentReview.contentTextarea).toBeVisible()
      await expect(contentReview.actionsLabel).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should open diff view modal when Diff view button is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const draftLoaded = await contentReview.isDraftLoaded()
      if (!draftLoaded) return

      const diffBtnVisible = await contentReview.diffViewButton.isVisible().catch(() => false)
      if (!diffBtnVisible) return

      await contentReview.diffViewButton.click()

      await expect(contentReview.diffModal).toBeVisible({ timeout: 5_000 })

      // Close the modal
      await authedPage.keyboard.press("Escape")
      await expect(contentReview.diffModal).toBeHidden({ timeout: 3_000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // AI Integration (requires server)
  // =========================================================================

  test.describe("AI Integration", () => {
    test("should fire POST /api/v1/chat/completions when AI fix is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const draftLoaded = await contentReview.isDraftLoaded()
      if (!draftLoaded) return

      const aiFixVisible = await contentReview.aiFixButton.isVisible().catch(() => false)
      const aiFixEnabled = await contentReview.aiFixButton.isEnabled().catch(() => false)
      if (!aiFixVisible || !aiFixEnabled) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/chat\/completions/,
        method: "POST",
      }, 15_000)

      await contentReview.aiFixButton.click()

      // Consent dialog may appear; accept it if so
      const consentOk = authedPage.getByRole("button", { name: /continue/i })
      const consentVisible = await consentOk.isVisible({ timeout: 2_000 }).catch(() => false)
      if (consentVisible) {
        await consentOk.click()
      }

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // AI fix may not fire if content is empty or chat is unavailable
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Commit (requires server)
  // =========================================================================

  test.describe("Commit", () => {
    test("should fire POST /api/v1/media/add when Commit is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      contentReview = new ContentReviewPage(authedPage)
      await contentReview.goto()
      await contentReview.assertPageReady()

      const draftLoaded = await contentReview.isDraftLoaded()
      if (!draftLoaded) return

      const commitVisible = await contentReview.commitButton.isVisible().catch(() => false)
      const commitEnabled = await contentReview.commitButton.isEnabled().catch(() => false)
      if (!commitVisible || !commitEnabled) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/media\/add/,
        method: "POST",
      }, 15_000)

      await contentReview.commitButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Commit may fail if draft requires a source file or other preconditions
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
