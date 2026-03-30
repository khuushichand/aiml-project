import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { SettingsPage } from "../../utils/page-objects"

const SETTINGS_SHELL_SECTIONS = [
  "tldw",
  "model",
  "chat",
  "ui",
  "splash",
  "quick-ingest",
  "image-generation",
  "image-gen",
  "guardian",
  "prompt",
  "knowledge",
  "rag",
  "speech",
  "evaluations",
  "characters",
  "chatbooks",
  "world-books",
  "prompt-studio",
  "share",
  "about",
  "family-guardrails",
  "chat-dictionaries",
] as const

const SETTINGS_STANDALONE_PAGES = [
  {
    section: "health",
    heading: /health status/i,
  },
  {
    section: "mcp-hub",
    heading: /^mcp hub$/i,
  },
  {
    section: "processed",
    heading: /processed items \(local\)/i,
  },
] as const

test.describe("Settings Full — All Subsections", () => {
  test.beforeEach(async ({ serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  for (const section of SETTINGS_SHELL_SECTIONS) {
    test(`settings/${section} loads and renders interactive elements`, async ({
      authedPage,
      diagnostics,
    }) => {
      const settings = new SettingsPage(authedPage)
      await authedPage.goto(`/settings/${section}`, { waitUntil: "domcontentloaded" })
      await settings.waitForReady()

      // Every settings subsection should render at least one interactive element
      const interactiveElements = authedPage.locator(
        "button, input, select, textarea, a[href]"
      )
      await expect(interactiveElements.first()).toBeVisible({ timeout: 15_000 })
      expect(await interactiveElements.count()).toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  }

  for (const page of SETTINGS_STANDALONE_PAGES) {
    test(`settings/${page.section} loads and renders interactive elements`, async ({
      authedPage,
      diagnostics,
    }) => {
      await authedPage.goto(`/settings/${page.section}`, {
        waitUntil: "domcontentloaded",
      })

      await expect(
        authedPage.getByRole("heading", { name: page.heading }).first()
      ).toBeVisible({ timeout: 20_000 })

      const interactiveElements = authedPage.locator(
        "button, input, select, textarea, a[href]"
      )
      await expect(interactiveElements.first()).toBeVisible({ timeout: 15_000 })
      expect(await interactiveElements.count()).toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  }

  test("settings index page loads with navigation sidebar", async ({
    authedPage,
    diagnostics,
  }) => {
    const settings = new SettingsPage(authedPage)
    await settings.goto()
    await settings.waitForReady()

    // Verify settings navigation is present
    const settingsNav = authedPage.getByTestId("settings-navigation")
    await expect(settingsNav).toBeVisible()

    // Verify at least one nav link is visible
    const navLinks = authedPage.locator("[data-testid^='settings-nav-link-']")
    await expect(navLinks.first()).toBeVisible()
    const navCount = await navLinks.count()
    expect(navCount).toBeGreaterThan(3)

    await assertNoCriticalErrors(diagnostics)
  })

  test("settings tldw section has save button that fires API", async ({
    authedPage,
    diagnostics,
  }) => {
    const settings = new SettingsPage(authedPage)
    await settings.gotoSection("tldw")
    await settings.waitForReady()

    const saveBtn = authedPage.getByRole("button", { name: /save/i }).first()
    if (await saveBtn.isVisible().catch(() => false)) {
      const apiCall = expectApiCall(authedPage, { url: "/api/v1/" })
      await saveBtn.click()
      const { response } = await apiCall
      expect(response.status()).toBeLessThan(400)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("settings model section loads provider controls", async ({
    authedPage,
    diagnostics,
  }) => {
    const settings = new SettingsPage(authedPage)
    await settings.gotoSection("model")
    await settings.waitForReady()

    // Model section should have inputs for provider configuration
    const inputs = await authedPage.locator("input, select, textarea").count()
    expect(inputs).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })

  test("settings chat section loads chat configuration", async ({
    authedPage,
    diagnostics,
  }) => {
    const settings = new SettingsPage(authedPage)
    await settings.gotoSection("chat")
    await settings.waitForReady()

    const inputs = await authedPage.locator("input, select, textarea").count()
    expect(inputs).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })
})
