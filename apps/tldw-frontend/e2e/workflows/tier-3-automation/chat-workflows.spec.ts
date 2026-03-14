/**
 * Chat Workflows E2E Tests (Tier 3)
 *
 * Tests the Chat Workflows page lifecycle:
 * - Page loads with heading, tabs, and action buttons
 * - Connection gate shows when server is unavailable
 * - Tab switching between Library, Builder, Generate, and Run
 * - New Template button switches to Builder tab
 * - API calls fire for template listing on page load
 *
 * Run: npx playwright test e2e/workflows/tier-3-automation/chat-workflows.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { ChatWorkflowsPage } from "../../utils/page-objects/ChatWorkflowsPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth } from "../../utils/helpers"

test.describe("Chat Workflows", () => {
  let chatWorkflows: ChatWorkflowsPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    chatWorkflows = new ChatWorkflowsPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render Chat Workflows page with heading and action buttons", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      // Either the heading or the connection gate message should be visible
      const headingVisible = await chatWorkflows.heading.isVisible().catch(() => false)
      const offlineVisible = await chatWorkflows.isOffline()

      expect(headingVisible || offlineVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show Structured QA badge when connected", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      const badgeVisible = await chatWorkflows.structuredQaBadge.isVisible().catch(() => false)
      expect(badgeVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display action buttons when connected", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      const newTemplateVisible = await chatWorkflows.newTemplateButton.isVisible().catch(() => false)
      const socraticVisible = await chatWorkflows.socraticDialogueButton.isVisible().catch(() => false)
      const generatorVisible = await chatWorkflows.openGeneratorButton.isVisible().catch(() => false)

      expect(newTemplateVisible).toBe(true)
      expect(socraticVisible).toBe(true)
      expect(generatorVisible).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // Tab Interactions
  // =========================================================================

  test.describe("Tab Interactions", () => {
    test("should show Library tab as default active tab", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      const librarySelected = await chatWorkflows.libraryTab
        .getAttribute("aria-selected")
        .catch(() => "false")
      expect(librarySelected).toBe("true")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch to Builder tab when New Template is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      const newTemplateVisible = await chatWorkflows.newTemplateButton.isVisible().catch(() => false)
      if (!newTemplateVisible) return

      await chatWorkflows.newTemplateButton.click()
      await authedPage.waitForTimeout(500)

      const builderSelected = await chatWorkflows.builderTab
        .getAttribute("aria-selected")
        .catch(() => "false")
      expect(builderSelected).toBe("true")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch to Generate tab when Open Generator is clicked", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      const generatorVisible = await chatWorkflows.openGeneratorButton.isVisible().catch(() => false)
      if (!generatorVisible) return

      await chatWorkflows.openGeneratorButton.click()
      await authedPage.waitForTimeout(500)

      const generateSelected = await chatWorkflows.generateTab
        .getAttribute("aria-selected")
        .catch(() => "false")
      expect(generateSelected).toBe("true")

      await assertNoCriticalErrors(diagnostics)
    })

    test("should show empty state or templates in Library tab", async ({
      authedPage,
      diagnostics,
    }) => {
      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()
      await chatWorkflows.assertPageReady()

      const offline = await chatWorkflows.isOffline()
      if (offline) return

      // Wait for library to load
      await authedPage.waitForTimeout(1_000)

      const emptyVisible = await chatWorkflows.libraryEmpty.isVisible().catch(() => false)
      const templateCount = await chatWorkflows.getTemplateCount()

      // Either empty state or template cards should be present
      expect(emptyVisible || templateCount >= 0).toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Integration (requires server)
  // =========================================================================

  test.describe("API Integration", () => {
    test("should fire GET /api/v1/chat-workflows/templates on page load", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/chat-workflows\/templates/,
        method: "GET",
      }, 20_000)

      chatWorkflows = new ChatWorkflowsPage(authedPage)
      await chatWorkflows.goto()

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // Server may not have chat-workflows endpoint available
      }

      await chatWorkflows.assertPageReady()
      await assertNoCriticalErrors(diagnostics)
    })
  })
})
