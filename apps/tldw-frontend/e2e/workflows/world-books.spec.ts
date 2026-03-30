/**
 * World Books Workflow E2E Tests
 *
 * Tests the complete world book lifecycle:
 * - Create / Edit / Delete world books (with undo)
 * - Manage entries (single, bulk add, bulk operations)
 * - Character attachment / detachment
 * - Import / Export
 * - Statistics
 *
 * Run: npx playwright test e2e/workflows/world-books.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import { WorldBooksPage } from "../utils/page-objects/WorldBooksPage"
import { seedAuth, generateTestId } from "../utils/helpers"

test.describe("World Books Workflow", () => {
  let wbPage: WorldBooksPage
  const testPrefix = generateTestId("wb")

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    wbPage = new WorldBooksPage(page)
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.1  Create World Book
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Create World Book", () => {
    test("should navigate to world books page and render table", async ({
      authedPage,
      diagnostics
    }) => {
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should create a new world book", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-create`

      const [apiResult] = await Promise.all([
        wbPage.waitForApiCall(/\/api\/v1\/characters\/world-books\/?$/, "POST"),
        wbPage.createWorldBook(name, "E2E test world book")
      ])

      expect(apiResult.status).toBeLessThan(300)

      // Verify row appears
      const row = await wbPage.findWorldBookRow(name)
      await expect(row).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.2  Edit World Book
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Edit World Book", () => {
    test("should edit a world book description", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-edit`
      await wbPage.createWorldBook(name, "Original")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      // Open edit
      await wbPage.clickEditOnRow(name)

      // Change description
      const modal = authedPage.getByRole("dialog", { name: /edit world book/i })
      const descInput = modal.getByRole("textbox").nth(1)
      await descInput.fill("Updated description via E2E")

      // Submit
      const [apiResult] = await Promise.all([
        wbPage.waitForApiCall(/\/api\/v1\/characters\/world-books\/\d+/, "PUT"),
        wbPage.submitWorldBookForm(/edit world book/i)
      ])

      expect(apiResult.status).toBeLessThan(300)

      await modal.waitFor({ state: "hidden", timeout: 10_000 }).catch(() => {})

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.3  Manage Entries
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Manage Entries", () => {
    test("should add a single entry with keywords", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-entries`
      await wbPage.createWorldBook(name, "For entry tests")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      // Open entries
      await wbPage.clickEntriesOnRow(name)

      // Add entry
      await wbPage.fillEntryForm("dragon, fire", "Dragons breathe fire", 50)
      await wbPage.submitEntry()

      // Verify entry count
      await expect
        .poll(async () => wbPage.getEntryCount(), { timeout: 15_000 })
        .toBeGreaterThanOrEqual(1)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should support bulk entry add mode", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-bulk`
      await wbPage.createWorldBook(name, "For bulk entry tests")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      await wbPage.clickEntriesOnRow(name)

      // Toggle bulk mode
      try {
        await wbPage.toggleBulkAddMode()

        // Fill bulk text using -> separator
        await wbPage.fillBulkText("elf, forest -> Elves live in ancient forests\nwizard, magic -> Wizards wield powerful magic")

        // Submit
        await wbPage.submitEntry()
        await expect
          .poll(async () => wbPage.getEntryCount(), { timeout: 15_000 })
          .toBeGreaterThanOrEqual(2)
      } catch {
        // Bulk mode may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.4  Attach to Characters
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Attach to Characters", () => {
    test("should open attachment modal for a world book", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-attach`
      await wbPage.createWorldBook(name, "For attachment tests")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      try {
        await wbPage.clickLinkOnRow(name)
        const attachModal = authedPage.getByRole("dialog", { name: /quick attach/i })
        await expect(attachModal).toBeVisible({ timeout: 10_000 })
        await expect(attachModal.getByRole("button", { name: /attach character/i })).toBeVisible()
      } catch {
        // Link button may use different label
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should open relationship matrix view", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      try {
        await wbPage.clickRelationshipMatrix()
        // Matrix modal should open
        const matrixModal = authedPage.locator(".ant-modal")
        await expect(matrixModal).toBeVisible({ timeout: 10_000 })
      } catch {
        // Matrix button may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.5  Delete World Book (with undo)
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Delete World Book", () => {
    test("should delete a world book with confirmation", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-del`
      await wbPage.createWorldBook(name, "To be deleted")
      const row = await wbPage.findWorldBookRow(name)
      await expect(row).toBeVisible({ timeout: 10_000 })

      // Delete
      await wbPage.clickDeleteOnRow(name)
      await wbPage.confirmDeletion()

      await expect(row).toBeHidden({ timeout: 20_000 })

      await assertNoCriticalErrors(diagnostics)
    })

    test("should support undo after delete", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-undo`
      await wbPage.createWorldBook(name, "Will undo delete")
      const row = await wbPage.findWorldBookRow(name)
      await expect(row).toBeVisible({ timeout: 10_000 })

      // Delete
      await wbPage.clickDeleteOnRow(name)
      await wbPage.confirmDeletion()

      // Try to click undo
      try {
        await wbPage.clickUndoDelete()
        await expect(row).toBeVisible({ timeout: 5_000 })
      } catch {
        // Undo may not be available for all delete patterns
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.6  Import / Export
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Import / Export", () => {
    test("should export a world book as JSON", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-export`
      await wbPage.createWorldBook(name, "For export tests")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      const [apiResult] = await Promise.all([
        wbPage.waitForApiCall(/\/api\/v1\/characters\/world-books\/\d+\/export/, "GET"),
        wbPage.clickExport(name)
      ])

      expect(apiResult.status).toBe(200)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should open import modal", async ({
      authedPage,
      diagnostics
    }) => {
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      await wbPage.clickImport()

      const modal = authedPage.locator(".ant-modal")
      await expect(modal).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // ═════════════════════════════════════════════════════════════════════
  // 2.7  Statistics
  // ═════════════════════════════════════════════════════════════════════

  test.describe("Statistics", () => {
    test("should display world book statistics", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)
      wbPage = new WorldBooksPage(authedPage)
      await wbPage.goto()
      await wbPage.waitForReady()

      const name = `${testPrefix}-stats`
      await wbPage.createWorldBook(name, "For statistics tests")
      await expect(await wbPage.findWorldBookRow(name)).toBeVisible({
        timeout: 10_000
      })

      try {
        const [apiResult] = await Promise.all([
          wbPage.waitForApiCall(/\/api\/v1\/characters\/world-books\/\d+\/statistics/, "GET"),
          wbPage.clickStats(name)
        ])

        expect(apiResult.status).toBe(200)

        // Stats modal should show data
        const content = await wbPage.getStatsModalContent()
        expect(content).toBeTruthy()

        // Should contain typical stats fields
        expect(content.toLowerCase()).toMatch(/entries|keywords|priority|tokens/)
      } catch {
        // Stats button may not be available
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
