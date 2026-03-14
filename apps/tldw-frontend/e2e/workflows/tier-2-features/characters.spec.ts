/**
 * Characters Workflow E2E Tests
 *
 * Tests the character management page:
 * - Page loads with expected elements
 * - Create character fires POST /api/v1/characters/
 * - Delete character fires DELETE /api/v1/characters/{id}
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/characters.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../../utils/fixtures"
import { CharactersPage } from "../../utils/page-objects/CharactersPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth, generateTestId } from "../../utils/helpers"

test.describe("Characters Workflow", () => {
  let charPage: CharactersPage
  const testPrefix = generateTestId("char")

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    charPage = new CharactersPage(page)
  })

  // ═══════════════════════════════════════════════════════════════════
  // 1. Page loads with expected elements
  // ═══════════════════════════════════════════════════════════════════

  test("should load characters page with expected elements", async ({
    authedPage,
    diagnostics
  }) => {
    charPage = new CharactersPage(authedPage)
    await charPage.goto()
    await charPage.assertPageReady()

    // The page container should be visible
    const pageRoot = authedPage.locator('[data-testid="characters-page"]')
    const emptyState = authedPage.locator(".ant-empty, .ant-result")
    const anyReady = pageRoot.or(emptyState)
    await expect(anyReady.first()).toBeVisible({ timeout: 20_000 })

    // If the characters feature is available, verify the New button exists
    if (await pageRoot.isVisible().catch(() => false)) {
      await expect(charPage.newButton).toBeVisible()
      await expect(charPage.searchInput).toBeVisible()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  // ═══════════════════════════════════════════════════════════════════
  // 2. Create character fires API
  // ═══════════════════════════════════════════════════════════════════

  test("should create a character and fire POST /api/v1/characters/", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    charPage = new CharactersPage(authedPage)
    await charPage.goto()
    await charPage.assertPageReady()

    // Skip if characters feature is not available on this server
    const pageRoot = authedPage.locator('[data-testid="characters-page"]')
    if (!(await pageRoot.isVisible().catch(() => false))) {
      test.skip(true, "Characters feature not available on this server")
      return
    }

    const name = `${testPrefix}-create`

    // Set up API call expectation before triggering the action
    const [apiResult] = await Promise.all([
      charPage.waitForApiCall("/api/v1/characters", "POST"),
      charPage.createCharacter({
        name,
        description: "E2E test character",
        systemPrompt: "You are a helpful test assistant."
      })
    ])

    expect(apiResult.status).toBeLessThan(300)

    await assertNoCriticalErrors(diagnostics)
  })

  // ═══════════════════════════════════════════════════════════════════
  // 3. Delete character fires API
  // ═══════════════════════════════════════════════════════════════════

  test("should delete a character and fire DELETE /api/v1/characters/{id}", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    charPage = new CharactersPage(authedPage)
    await charPage.goto()
    await charPage.assertPageReady()

    // Skip if characters feature is not available
    const pageRoot = authedPage.locator('[data-testid="characters-page"]')
    if (!(await pageRoot.isVisible().catch(() => false))) {
      test.skip(true, "Characters feature not available on this server")
      return
    }

    const name = `${testPrefix}-delete`

    // First create a character to delete
    await charPage.createCharacter({
      name,
      description: "To be deleted",
      systemPrompt: "You are a test character that will be deleted."
    })

    // Wait for creation to complete and list to refresh
    await authedPage.waitForTimeout(2000)

    // Now delete and verify the API call
    const [deleteResult] = await Promise.all([
      charPage.waitForApiCall(/\/api\/v1\/characters\//, "DELETE"),
      charPage.deleteCharacter(name)
    ])

    expect(deleteResult.status).toBeLessThan(300)

    await assertNoCriticalErrors(diagnostics)
  })
})
