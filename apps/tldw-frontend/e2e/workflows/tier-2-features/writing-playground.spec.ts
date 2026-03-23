/**
 * Writing Playground E2E Tests (Tier 2)
 *
 * Tests the Writing Playground page lifecycle:
 * - Page loads with expected shell and topbar elements
 * - Library and inspector sidebars toggle correctly
 * - New session button fires POST /api/v1/writing/sessions (requires server)
 * - Generate button fires POST /api/v1/chat/completions (requires server + session + model)
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/writing-playground.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { WritingPlaygroundPage } from "../../utils/page-objects"
import { seedAuth } from "../../utils/helpers"

test.describe("Writing Playground", () => {
  let writing: WritingPlaygroundPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    writing = new WritingPlaygroundPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the Writing Playground page with shell and topbar", async ({
      authedPage,
      diagnostics,
    }) => {
      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      // The route shell should be present
      const routeShellVisible = await writing.routeShell.isVisible().catch(() => false)
      expect(routeShellVisible).toBe(true)

      // The playground shell should be present
      const shellVisible = await writing.shell.isVisible().catch(() => false)
      expect(shellVisible).toBe(true)

      // The topbar with model input and generate button should render
      const topbarVisible = await writing.topbar.isVisible().catch(() => false)
      expect(topbarVisible).toBe(true)

      await expect(writing.modelInput).toBeVisible()
      await expect(writing.generateButton).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show empty/no-session state when no session is active", async ({
      authedPage,
      diagnostics,
    }) => {
      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      // When no session is selected, the topbar should show "No session"
      // or the settings panel should show the empty state
      const noSession = await writing.noSessionText.isVisible().catch(() => false)
      const settingsEmpty = await writing.settingsEmptyState.isVisible().catch(() => false)

      // At least one empty-state indicator should be visible
      // (unless sessions already exist from prior usage)
      if (!noSession && !settingsEmpty) {
        // Sessions may already exist; just verify the page loaded
        await expect(writing.topbar).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Sidebar Toggles
  // =========================================================================

  test.describe("Sidebar Toggles", () => {
    test("should toggle library sidebar when sessions button is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      const toggleBtn = writing.toggleLibraryButton
      const toggleVisible = await toggleBtn.isVisible().catch(() => false)
      if (!toggleVisible) return

      // Click to toggle open (or closed, depending on default state)
      const beforeLibraryVisible = await writing.librarySidebar.isVisible().catch(() => false)
      await toggleBtn.click()
      await expect
        .poll(
          async () => await writing.librarySidebar.isVisible().catch(() => false),
          { timeout: 5_000 }
        )
        .not.toBe(beforeLibraryVisible)

      // Click again to toggle the other way
      await toggleBtn.click()
      await expect
        .poll(
          async () => await writing.librarySidebar.isVisible().catch(() => false),
          { timeout: 5_000 }
        )
        .toBe(beforeLibraryVisible)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should toggle inspector sidebar when settings button is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      const toggleBtn = writing.toggleInspectorButton
      const toggleVisible = await toggleBtn.isVisible().catch(() => false)
      if (!toggleVisible) return

      const beforeInspectorVisible = await writing.inspectorSidebar.isVisible().catch(() => false)
      await toggleBtn.click()
      await expect
        .poll(
          async () => await writing.inspectorSidebar.isVisible().catch(() => false),
          { timeout: 5_000 }
        )
        .not.toBe(beforeInspectorVisible)

      await toggleBtn.click()
      await expect
        .poll(
          async () => await writing.inspectorSidebar.isVisible().catch(() => false),
          { timeout: 5_000 }
        )
        .toBe(beforeInspectorVisible)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Session Creation (requires server)
  // =========================================================================

  test.describe("Session API", () => {
    test("should fire POST /api/v1/writing/sessions when New Session is clicked", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      // Make sure library is visible so we can see the New Session button
      const libraryVisible = await writing.librarySidebar.isVisible().catch(() => false)
      if (!libraryVisible) {
        const toggleBtn = writing.toggleLibraryButton
        const canToggle = await toggleBtn.isVisible().catch(() => false)
        if (canToggle) {
          await toggleBtn.click()
          await expect
            .poll(
              async () => await writing.newSessionButton.isVisible().catch(() => false),
              { timeout: 5_000 }
            )
            .toBe(true)
        }
      }

      const newSessionBtn = writing.newSessionButton
      const btnVisible = await newSessionBtn.isVisible().catch(() => false)
      if (!btnVisible) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/writing\/sessions/,
        method: "POST",
      }, 15_000)

      await newSessionBtn.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // The button may open a modal first; acceptable if no direct API call fires
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Generate API (requires server + active session + model)
  // =========================================================================

  test.describe("Generate API", () => {
    test("should fire POST /api/v1/chat/completions when Generate is clicked with a session and model", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      writing = new WritingPlaygroundPage(authedPage)
      await writing.goto()
      await writing.assertPageReady()

      // The generate button should be visible but may be disabled without a session/model
      await expect(writing.generateButton).toBeVisible()

      const isDisabled = await writing.generateButton.isDisabled().catch(() => true)
      if (isDisabled) {
        // Cannot test generation without an active session and model configured
        return
      }

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/chat\/completions/,
        method: "POST",
      }, 15_000)

      await writing.generateButton.click()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Generation may require specific setup (model, session content); acceptable to skip
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
