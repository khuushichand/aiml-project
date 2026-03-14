/**
 * Workspace Playground Workflow E2E Tests
 *
 * Dedicated interaction coverage for /workspace-playground beyond smoke checks.
 */
import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"
import { seedAuth } from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

const buildSeedSources = () => {
  const base = Date.now() % 1_000_000
  return [
    {
      mediaId: 9_000_000 + base,
      title: "Workspace E2E Source A",
      type: "document" as const,
      url: "https://example.com/workspace-source-a"
    },
    {
      mediaId: 9_100_000 + base,
      title: "Workspace E2E Source B",
      type: "website" as const,
      url: "https://example.com/workspace-source-b"
    }
  ]
}

test.describe("Workspace Playground Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)

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

  test("supports selecting store-seeded sources without runtime errors", async ({
    authedPage,
    diagnostics
  }) => {
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    await workspacePage.goto()
    await workspacePage.waitForReady()
    await workspacePage.seedSources(buildSeedSources())

    await expect
      .poll(async () => (await workspacePage.getSourceIds()).length, {
        timeout: 10_000
      })
      .toBeGreaterThanOrEqual(2)

    await authedPage.evaluate(() => {
      const store = (window as { __tldw_useWorkspaceStore?: unknown })
        .__tldw_useWorkspaceStore as
        | {
            getState?: () => {
              deselectAllSources?: () => void
              setSourceSearchQuery?: (query: string) => void
            }
          }
        | undefined
      const state = store?.getState?.()
      state?.deselectAllSources?.()
      state?.setSourceSearchQuery?.("")
    })

    const sourceIds = await workspacePage.getSourceIds()
    const firstSourceId = sourceIds[0]
    await workspacePage.selectSourceById(firstSourceId)
    await workspacePage.expectSourceSelected(firstSourceId)
    await expect(
      workspacePage.sourcesPanel.getByText(/^1 selected$/)
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})
