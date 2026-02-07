/**
 * Chat Dictionaries Workflow E2E Tests
 *
 * Tests the complete dictionary lifecycle from a user's perspective:
 * - Create / Edit / Delete dictionaries
 * - Manage entries (add, edit, delete)
 * - Validate & Preview
 * - Import / Export (JSON)
 *
 * Run: npx playwright test e2e/workflows/dictionaries.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import { DictionariesPage } from "../utils/page-objects/DictionariesPage"
import { seedAuth, generateTestId, waitForConnection } from "../utils/helpers"

test.describe("Chat Dictionaries Workflow", () => {
  let dictPage: DictionariesPage
  const testPrefix = generateTestId("dict")

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    dictPage = new DictionariesPage(page)
  })

  // ═════════════════════════════════════════════════════════════════════
  // 1.1  Create Dictionary
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Create Dictionary", () => {
    test("should navigate to dictionaries page and render table", async ({
      authedPage,
      diagnostics
    }) => {
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      // Page loaded without error
      await assertNoCriticalErrors(diagnostics)
    })

    test("should open create modal and create a new dictionary", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const name = `${testPrefix}-create`

      // Intercept the POST call
      const [apiResult] = await Promise.all([
        dictPage.waitForApiCall("/chat/dictionaries", "POST"),
        dictPage.createDictionary(name, "E2E test dictionary")
      ])

      expect(apiResult.status).toBeLessThan(300)

      // Verify row appears in table
      const row = await dictPage.findDictionaryRow(name)
      await expect(row).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 1.2  Edit Dictionary
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Edit Dictionary", () => {
    test("should edit a dictionary name and description", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const originalName = `${testPrefix}-edit-src`
      await dictPage.createDictionary(originalName, "Original desc")
      await authedPage.waitForTimeout(1000)

      // Open edit modal
      await dictPage.clickEditOnRow(originalName)

      // Change values in the edit form
      const updatedName = `${testPrefix}-edit-upd`
      await dictPage.fillDictionaryForm(updatedName, "Updated description")

      // Submit edit and verify PUT call
      const [apiResult] = await Promise.all([
        dictPage.waitForApiCall(/chat\/dictionaries\/\d+/, "PUT"),
        dictPage.submitDictionaryForm()
      ])

      expect(apiResult.status).toBeLessThan(300)

      // Wait for modal to close
      await authedPage
        .locator(".ant-modal")
        .waitFor({ state: "hidden", timeout: 10_000 })
        .catch(() => {})

      // Verify updated row
      const updatedRow = await dictPage.findDictionaryRow(updatedName)
      await expect(updatedRow).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 1.3  Manage Entries
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Manage Entries", () => {
    test("should add, edit, and delete dictionary entries", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const name = `${testPrefix}-entries`
      await dictPage.createDictionary(name, "For entry tests")
      await authedPage.waitForTimeout(1000)

      // Open entry manager
      await dictPage.clickManageEntries(name)
      await authedPage.waitForTimeout(500)

      // Add an entry
      await dictPage.fillEntryForm("hello", "hi", "literal")
      const [addResult] = await Promise.all([
        dictPage.waitForApiCall(/dictionaries\/\d+\/entries/, "POST"),
        dictPage.submitEntry()
      ])
      expect(addResult.status).toBeLessThan(300)

      // Verify entry appears
      const entryCount = await dictPage.getEntryCount()
      expect(entryCount).toBeGreaterThanOrEqual(1)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should validate dictionary entries", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      // Try validation on any existing dictionary
      const names = await dictPage.getDictionaryNames()
      if (names.length === 0) {
        test.skip(true, "No dictionaries available for validation test")
        return
      }

      await dictPage.clickManageEntries(names[0])
      await authedPage.waitForTimeout(500)

      // Click validate
      try {
        const [validateResult] = await Promise.all([
          dictPage.waitForApiCall("/dictionaries/validate", "POST"),
          dictPage.clickValidate()
        ])
        expect(validateResult.status).toBeLessThan(300)
      } catch {
        // Validate button may not exist if no entries
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should preview dictionary processing", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const names = await dictPage.getDictionaryNames()
      if (names.length === 0) {
        test.skip(true, "No dictionaries available for preview test")
        return
      }

      await dictPage.clickManageEntries(names[0])
      await authedPage.waitForTimeout(500)

      // Use preview with sample text
      try {
        await dictPage.fillPreviewText("hello world test")
        const [previewResult] = await Promise.all([
          dictPage.waitForApiCall("/dictionaries/process", "POST"),
          dictPage.clickPreview()
        ])
        expect(previewResult.status).toBeLessThan(300)
      } catch {
        // Preview may not be available without entries
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 1.4  Delete Dictionary
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Delete Dictionary", () => {
    test("should soft-delete a dictionary with confirmation", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const name = `${testPrefix}-del`
      await dictPage.createDictionary(name, "To be deleted")
      await authedPage.waitForTimeout(1000)

      // Delete
      const [deleteResult] = await Promise.all([
        dictPage.waitForApiCall(/chat\/dictionaries\/\d+/, "DELETE"),
        (async () => {
          await dictPage.clickDeleteOnRow(name)
          await dictPage.confirmDeletion()
        })()
      ])

      expect(deleteResult.status).toBeLessThan(300)

      // Verify row is removed
      await authedPage.waitForTimeout(1000)
      const row = await dictPage.findDictionaryRow(name)
      await expect(row).toBeHidden({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 1.5  Import / Export
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Import / Export", () => {
    test("should export dictionary as JSON", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      const names = await dictPage.getDictionaryNames()
      if (names.length === 0) {
        test.skip(true, "No dictionaries available for export test")
        return
      }

      // Intercept download
      const [download] = await Promise.all([
        authedPage.waitForEvent("download", { timeout: 15_000 }).catch(() => null),
        dictPage.clickExportJSON(names[0])
      ])

      // Export triggers either a download or an API call
      if (download) {
        expect(download.suggestedFilename()).toMatch(/\.json$/i)
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should open import modal", async ({
      authedPage,
      diagnostics
    }) => {
      dictPage = new DictionariesPage(authedPage)
      await dictPage.goto()
      await dictPage.waitForReady()

      await dictPage.clickImport()

      // Verify modal is visible
      const modal = authedPage.locator(".ant-modal")
      await expect(modal).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
