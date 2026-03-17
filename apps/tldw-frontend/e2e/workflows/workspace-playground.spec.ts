/**
 * Workspace Playground Workflow E2E Tests
 *
 * Dedicated interaction coverage for /workspace-playground beyond smoke checks.
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth } from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

test.describe("Workspace Playground Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)

    await page.route("**/api/v1/llm/models/metadata**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] })
      })
    })

    await page.route("**/api/v1/chat/commands**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ commands: [] })
      })
    })

    await page.route("**/api/v1/chats**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 })
      })
    })

    await page.route("**/api/v1/chats/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 })
      })
    })

    await page.route("**/api/v1/chat/conversations**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 })
      })
    })

    await page.route("**/api/v1/chat/conversations/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 })
      })
    })
  })

  test("loads workspace playground and renders core panes", async ({
    authedPage,
    diagnostics
  }) => {
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await expect(workspacePage.headerTitle).toBeVisible()
    await expect(workspacePage.sourcesPanel).toBeVisible()
    await expect(workspacePage.chatPanel).toBeVisible()
    await expect(workspacePage.studioPanel).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("opens and closes workspace search modal with keyboard shortcut", async ({
    authedPage,
    diagnostics
  }) => {
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.openGlobalSearchWithShortcut()
    await expect(
      workspacePage.globalSearchModal.getByPlaceholder(
        /search sources, chat, and notes/i
      )
    ).toBeVisible()

    await workspacePage.closeGlobalSearchWithEscape()

    await assertNoCriticalErrors(diagnostics)
  })

  test("collapses and restores sources + studio panes", async ({
    authedPage,
    diagnostics
  }) => {
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.hideSourcesPane()
    await workspacePage.showSourcesPane()
    await workspacePage.hideStudioPane()
    await workspacePage.showStudioPane()

    await assertNoCriticalErrors(diagnostics)
  })

  test("opens and dismisses add-sources modal from sources pane", async ({
    authedPage,
    diagnostics
  }) => {
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.openAddSourcesModal()
    await workspacePage.closeAddSourcesModal()

    await assertNoCriticalErrors(diagnostics)
  })

  test("adds a source through the URL tab and shows processing state in the sources pane", async ({
    authedPage,
    diagnostics
  }) => {
    const addedSource = {
      mediaId: 8_811_001,
      title: "Workspace URL Ingested Source",
      url: "https://example.com/workspace-url-ingested",
      mediaType: "website"
    }
    const keywordUpdates: Array<{
      keywords?: string[]
      mode?: string
    }> = []

    await authedPage.route("**/api/v1/media/add", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            {
              media_id: addedSource.mediaId,
              title: addedSource.title,
              url: addedSource.url,
              media_type: addedSource.mediaType
            }
          ]
        })
      })
    })

    await authedPage.route("**/api/v1/media/*/keywords", async (route) => {
      keywordUpdates.push(route.request().postDataJSON() as { keywords?: string[]; mode?: string })
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          media_id: addedSource.mediaId,
          keywords: keywordUpdates.at(-1)?.keywords || []
        })
      })
    })

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.openAddSourcesModal()
    await workspacePage.addSourceModal.getByRole("tab", { name: /^url$/i }).click()
    await workspacePage.addSourceModal
      .getByPlaceholder("https://example.com/article or YouTube URL")
      .fill(addedSource.url)
    await workspacePage.addSourceModal.getByRole("button", { name: /^add url$/i }).click()

    await expect(workspacePage.addSourceModal).toBeHidden({ timeout: 10_000 })

    const sourceRow = workspacePage.sourcesPanel
      .locator("[data-source-id]", { hasText: addedSource.title })
      .first()
    await expect(sourceRow).toBeVisible()
    await expect(
      sourceRow.locator("span").filter({ hasText: /^processing$/i }).first()
    ).toBeVisible()
    await expect(sourceRow.locator('input[type="checkbox"]')).toBeDisabled()
    await expect
      .poll(() => keywordUpdates.length, { timeout: 10_000 })
      .toBeGreaterThanOrEqual(1)
    await expect
      .poll(() => keywordUpdates[0]?.mode || null, { timeout: 10_000 })
      .toBe("add")
    expect(keywordUpdates[0]?.keywords?.[0]).toMatch(/^workspace:/)

    await assertNoCriticalErrors(diagnostics)
  })

  test("adds a ready source from My Media and allows selecting it without store seeding", async ({
    authedPage,
    diagnostics
  }) => {
    const librarySource = {
      mediaId: 8_822_002,
      title: "Workspace Library Source",
      type: "pdf",
      url: "https://example.com/workspace-library-source.pdf"
    }
    const keywordUpdates: Array<{
      keywords?: string[]
      mode?: string
    }> = []

    await authedPage.route("**/api/v1/media?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          media: [
            {
              id: librarySource.mediaId,
              title: librarySource.title,
              type: librarySource.type,
              url: librarySource.url
            }
          ],
          total_count: 1
        })
      })
    })

    await authedPage.route("**/api/v1/media/*/keywords", async (route) => {
      keywordUpdates.push(route.request().postDataJSON() as { keywords?: string[]; mode?: string })
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          media_id: librarySource.mediaId,
          keywords: keywordUpdates.at(-1)?.keywords || []
        })
      })
    })

    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()

    await workspacePage.openAddSourcesModal()
    await workspacePage.addSourceModal.getByRole("tab", { name: /my media/i }).click()
    await expect(
      workspacePage.addSourceModal.getByText(librarySource.title)
    ).toBeVisible()

    await workspacePage.addSourceModal.getByText(librarySource.title).click()
    await workspacePage.addSourceModal
      .getByRole("button", { name: /^add 1 selected$/i })
      .click()

    await expect(workspacePage.addSourceModal).toBeHidden({ timeout: 10_000 })

    const sourceRow = workspacePage.sourcesPanel
      .locator("[data-source-id]", { hasText: librarySource.title })
      .first()
    await expect(sourceRow).toBeVisible()

    const sourceId = await sourceRow.getAttribute("data-source-id")
    expect(sourceId).toBeTruthy()

    await workspacePage.selectSourceById(sourceId!)
    await workspacePage.expectSourceSelected(sourceId!)
    await expect(workspacePage.sourcesPanel.getByText(/^1 selected$/)).toBeVisible()
    await expect
      .poll(() => keywordUpdates[0]?.mode || null, { timeout: 10_000 })
      .toBe("add")
    expect(keywordUpdates[0]?.keywords?.[0]).toMatch(/^workspace:/)

    await assertNoCriticalErrors(diagnostics)
  })
})
