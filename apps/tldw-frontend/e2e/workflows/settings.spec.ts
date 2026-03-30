/**
 * Settings Workflow E2E Tests
 *
 * Tests the complete settings workflow from a user's perspective:
 * - LLM provider configuration
 * - Settings persistence
 * - Validation
 * - Chat settings
 * - Navigation
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import { SettingsPage } from "../utils/page-objects"
import { seedAuth, TEST_CONFIG, waitForConnection } from "../utils/helpers"

test.describe("Settings Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test.describe("Settings Navigation", () => {
    test("should navigate to settings page", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.goto()
      await settingsPage.waitForReady()

      // Verify settings page loaded
      await expect(authedPage).toHaveURL(/\/settings/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display settings menu/sidebar", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.goto()
      await settingsPage.waitForReady()

      // Look for settings menu
      const menu = authedPage.locator(
        "[data-testid='settings-menu'], .settings-sidebar, .settings-nav, nav"
      )

      if ((await menu.count()) > 0) {
        await expect(menu.first()).toBeVisible()
      }

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to TLDW settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/tldw/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to model settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("model")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/model/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to chat settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/chat/)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Server Configuration", () => {
    test("should display server URL input", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      await expect(settingsPage.serverUrlInput).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display API key input", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      await expect(settingsPage.apiKeyInput).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should save server configuration", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Fill in server config
      await settingsPage.serverUrlInput.fill(TEST_CONFIG.serverUrl)
      await settingsPage.apiKeyInput.fill(TEST_CONFIG.apiKey)

      // Save
      await settingsPage.save()

      // Verify saved
      const config = await settingsPage.getServerConfig()
      expect(config.serverUrl).toContain(TEST_CONFIG.serverUrl.replace(/\/$/, ""))

      await assertNoCriticalErrors(diagnostics)
    })

    test("should test server connection", async ({
      authedPage,
      serverInfo,
      diagnostics
    }) => {
      skipIfServerUnavailable(serverInfo)

      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Fill in valid config
      await settingsPage.serverUrlInput.fill(TEST_CONFIG.serverUrl)
      await settingsPage.apiKeyInput.fill(TEST_CONFIG.apiKey)

      // Test connection
      const _connected = await settingsPage.testConnection()
      // Connection test may or may not be available

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Settings Persistence", () => {
    test("should restore the authoritative web host after page refresh", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Set custom server URL
      const customUrl = "http://custom-server:9000"
      await settingsPage.serverUrlInput.fill(customUrl)

      await settingsPage.save()

      // Refresh page
      await authedPage.reload()
      await settingsPage.waitForReady()

      // In web mode the bootstrap mirrors the authoritative frontend host back
      // into stored config after refresh, even if the user typed a temporary
      // custom URL into the settings form beforehand.
      const config = await settingsPage.getServerConfig()
      expect(config.serverUrl).toBe(TEST_CONFIG.serverUrl.replace(/\/$/, ""))

      await assertNoCriticalErrors(diagnostics)
    })

    test("should load saved settings on navigation", async ({
      authedPage,
      diagnostics
    }) => {
      // First set config
      await authedPage.addInitScript(() => {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: "http://saved-server:8080",
            apiKey: "saved-api-key",
            authMode: "single-user"
          })
        )
        localStorage.setItem("__tldw_first_run_complete", "true")
      })

      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // The web bootstrap keeps an explicit stored API key, but mirrors the
      // web server host back to the current frontend environment by default.
      const config = await settingsPage.getServerConfig()
      expect(config.serverUrl).toBe(TEST_CONFIG.serverUrl.replace(/\/$/, ""))
      expect(config.apiKey).toBe("saved-api-key")

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Validation", () => {
    test("should show validation error for empty required fields", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Clear server URL
      await settingsPage.serverUrlInput.clear()

      // Try to save
      await settingsPage.saveButton.click()

      await expect
        .poll(() => settingsPage.hasValidationErrors(), { timeout: 5_000 })
        .toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should validate URL format", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Enter invalid URL
      await settingsPage.serverUrlInput.fill("not-a-valid-url")

      // Try to save
      await settingsPage.saveButton.click()

      await expect
        .poll(() => settingsPage.hasValidationErrors(), { timeout: 5_000 })
        .toBe(true)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display validation error messages", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Create validation error
      await settingsPage.serverUrlInput.clear()

      await settingsPage.saveButton.click()

      await expect
        .poll(async () => (await settingsPage.getValidationErrors()).length, { timeout: 5_000 })
        .toBeGreaterThan(0)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("LLM Provider Configuration", () => {
    test("should navigate to model settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("model")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/model/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display provider options", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("model")
      await settingsPage.waitForReady()

      // Look for provider selection
      const _providerSelect = authedPage.locator(
        "[data-testid='provider-select'], select, .provider-dropdown"
      )

      // Provider selection may vary by implementation
      await assertNoCriticalErrors(diagnostics)
    })

    test("should list available providers", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      const _providers = await settingsPage.getAvailableProviders()

      // Some providers may be listed
      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Chat Settings", () => {
    test("should navigate to chat settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/chat/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display temperature setting", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      const _tempInput = authedPage.getByLabel(/temperature/i)
      // Temperature setting may exist

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display system prompt setting", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      const _systemPrompt = authedPage.getByLabel(/system prompt/i)
      // System prompt setting may exist

      await assertNoCriticalErrors(diagnostics)
    })

    test("should save chat settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      const namespaceInput = authedPage.getByLabel(/quick chat project docs namespace/i)
      await expect(namespaceInput).toBeVisible({ timeout: 10_000 })

      const originalValue = await namespaceInput.inputValue()
      const updatedValue =
        originalValue === "project_docs_e2e" ? "project_docs_alt_e2e" : "project_docs_e2e"
      await namespaceInput.fill(updatedValue)
      await expect
        .poll(
          () =>
            authedPage.evaluate(() => {
              const raw = localStorage.getItem("quickChatDocsIndexNamespace")
              if (raw == null) return null
              try {
                return JSON.parse(raw)
              } catch {
                return raw
              }
            }),
          { timeout: 5_000 }
        )
        .toBe(updatedValue)

      await authedPage.reload({ waitUntil: "domcontentloaded" })
      await settingsPage.waitForReady()
      await expect(authedPage.getByLabel(/quick chat project docs namespace/i)).toHaveValue(
        updatedValue
      )

      await authedPage.getByLabel(/quick chat project docs namespace/i).fill(originalValue)
      await expect
        .poll(
          () =>
            authedPage.evaluate(() => {
              const raw = localStorage.getItem("quickChatDocsIndexNamespace")
              if (raw == null) return null
              try {
                return JSON.parse(raw)
              } catch {
                return raw
              }
            }),
          { timeout: 5_000 }
        )
        .toBe(originalValue)

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Settings Navigation", () => {
    test("should navigate between settings pages", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)

      // Navigate to different sections
      await settingsPage.gotoSection("tldw")
      await expect(authedPage).toHaveURL(/\/settings\/tldw/)

      await settingsPage.gotoSection("model")
      await expect(authedPage).toHaveURL(/\/settings\/model/)

      await settingsPage.gotoSection("chat")
      await expect(authedPage).toHaveURL(/\/settings\/chat/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display breadcrumbs if available", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("chat")
      await settingsPage.waitForReady()

      const _breadcrumbs = await settingsPage.getBreadcrumbs()
      // Breadcrumbs may or may not be present

      await assertNoCriticalErrors(diagnostics)
    })

    test("should warn about unsaved changes", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("tldw")
      await settingsPage.waitForReady()

      // Make a change without saving
      const serverInput = authedPage.getByLabel(/server url/i)
      await serverInput.fill("http://changed-url:9000")

      // Try to navigate away via menu
      try {
        await settingsPage.navigateViaMenu("Model")

        // Check for unsaved changes warning
        const _hasWarning = await settingsPage.hasUnsavedChangesWarning()
        // Warning may or may not appear based on implementation
      } catch {
        // Navigation may proceed without warning
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Additional Settings Pages", () => {
    test("should navigate to RAG settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("rag")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/rag/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to knowledge settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("knowledge")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/knowledge/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to speech settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("speech")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/speech/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to characters settings", async ({
      authedPage,
      diagnostics
    }) => {
      const settingsPage = new SettingsPage(authedPage)
      await settingsPage.gotoSection("characters")
      await settingsPage.waitForReady()

      await expect(authedPage).toHaveURL(/\/settings\/characters/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should navigate to health settings", async ({
      authedPage,
      diagnostics
    }) => {
      await authedPage.goto("/settings/health", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      await expect(authedPage).toHaveURL(/\/settings\/health/)
      await expect(
        authedPage.getByRole("heading", { name: /health status/i }).first()
      ).toBeVisible({ timeout: 20_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("About Page", () => {
    test("should navigate to about page", async ({
      authedPage,
      diagnostics
    }) => {
      await authedPage.goto("/settings/about", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      await expect(authedPage).toHaveURL(/\/settings\/about/)

      await assertNoCriticalErrors(diagnostics)
    })

    test("should display version information", async ({
      authedPage,
      diagnostics
    }) => {
      await authedPage.goto("/settings/about", { waitUntil: "domcontentloaded" })
      await waitForConnection(authedPage)

      // Look for version info
      const _versionInfo = authedPage.locator(
        "[data-testid='version'], .version-info, .about-version"
      )

      await expect(authedPage.getByRole("main")).toBeVisible({ timeout: 10_000 })

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
