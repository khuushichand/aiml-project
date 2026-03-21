import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { SettingsPage } from "../../utils/page-objects"

// Sections accepted by SettingsPage.gotoSection() (typed union)
const SETTINGS_SECTIONS_VIA_PAGE_OBJECT = [
  "tldw", "model", "chat", "ui", "splash", "quick-ingest",
  "image-generation", "image-gen", "guardian", "prompt", "knowledge",
  "rag", "speech", "evaluations", "characters", "health",
] as const

// Settings pages that exist but are outside the page-object union — use direct URL
const SETTINGS_SECTIONS_DIRECT_NAV = [
  "chatbooks", "world-books", "prompt-studio", "mcp-hub",
  "share", "about", "processed", "family-guardrails",
] as const

test.describe("Settings", () => {
  let settings: SettingsPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    settings = new SettingsPage(authedPage)
  })

  // --- Section-load smoke tests (page-object navigation) ---
  for (const section of SETTINGS_SECTIONS_VIA_PAGE_OBJECT) {
    test(`settings/${section} loads without errors`, async ({ authedPage, diagnostics }) => {
      await settings.gotoSection(section)
      await settings.waitForReady()

      // At least one interactive element should be present
      const interactiveElements = authedPage.locator(
        "button, input, select, textarea, a[href]"
      )
      await expect(interactiveElements.first()).toBeVisible({ timeout: 15_000 })
      expect(await interactiveElements.count()).toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  }

  // --- Section-load smoke tests (direct URL navigation) ---
  for (const section of SETTINGS_SECTIONS_DIRECT_NAV) {
    test(`settings/${section} loads without errors`, async ({ authedPage, diagnostics }) => {
      await authedPage.goto(`/settings/${section}`, { waitUntil: "domcontentloaded" })
      await settings.waitForReady()

      const interactiveElements = authedPage.locator(
        "button, input, select, textarea, a[href]"
      )
      await expect(interactiveElements.first()).toBeVisible({ timeout: 15_000 })
      expect(await interactiveElements.count()).toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  }

  // --- Save button fires an API call ---
  test("save settings fires API", async ({ authedPage, diagnostics }) => {
    await settings.goto()
    await settings.gotoSection("tldw")
    await settings.waitForReady()

    const saveBtn = authedPage.getByRole("button", { name: /save/i }).first()
    if (await saveBtn.isVisible().catch(() => false)) {
      const apiCall = expectApiCall(authedPage, {
        url: "/api/v1/",
      })

      await saveBtn.click()
      const { response } = await apiCall
      expect(response.status()).toBeLessThan(400)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
