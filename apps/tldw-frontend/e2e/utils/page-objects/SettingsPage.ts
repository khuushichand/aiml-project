/**
 * Page Object for Settings functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection, waitForNetworkIdle } from "../helpers"

export class SettingsPage {
  readonly page: Page
  readonly sidebar: Locator
  readonly saveButton: Locator
  readonly serverUrlInput: Locator
  readonly apiKeyInput: Locator

  constructor(page: Page) {
    this.page = page
    this.sidebar = page.getByRole("navigation", { name: /settings/i })
    this.saveButton = page.getByRole("button", { name: /save/i })
    this.serverUrlInput = page.getByLabel(/server url/i)
    this.apiKeyInput = page.getByLabel(/api key/i)
  }

  /**
   * Navigate to main settings page
   */
  async goto(): Promise<void> {
    await this.page.goto("/settings", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Navigate to specific settings section
   */
  async gotoSection(
    section:
      | "tldw"
      | "model"
      | "chat"
      | "ui"
      | "splash"
      | "quick-ingest"
      | "image-generation"
      | "image-gen"
      | "guardian"
      | "prompt"
      | "knowledge"
      | "rag"
      | "speech"
      | "evaluations"
      | "characters"
      | "health"
  ): Promise<void> {
    await this.page.goto(`/settings/${section}`, { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Wait for settings page to be ready
   */
  async waitForReady(): Promise<void> {
    await waitForNetworkIdle(this.page, 10000)
    // Settings pages are no longer guaranteed to render a form wrapper.
    await expect(this.page.getByTestId("settings-navigation")).toBeVisible({
      timeout: 20000
    })
    const settingsLinks = this.page.locator("[data-testid^='settings-nav-link-']")
    await expect(settingsLinks.first()).toBeVisible({ timeout: 20000 })
  }

  /**
   * Configure server connection
   */
  async configureServer(serverUrl: string, apiKey: string): Promise<void> {
    await this.gotoSection("tldw")
    await this.waitForReady()

    const serverInput = this.page.getByLabel(/server url/i)
    await serverInput.waitFor({ state: "visible" })
    await serverInput.fill(serverUrl)

    const apiKeyInput = this.page.getByLabel(/api key/i)
    await apiKeyInput.fill(apiKey)

    await this.save()
  }

  /**
   * Save settings
   */
  async save(): Promise<void> {
    const saveBtn = this.page.getByRole("button", { name: /save/i })
    await saveBtn.click()

    // Wait for save to complete
    await this.page.waitForFunction(
      () => Boolean(localStorage.getItem("tldwConfig")),
      null,
      { timeout: 10000 }
    )
  }

  /**
   * Test server connection
   */
  async testConnection(): Promise<boolean> {
    const testBtn = this.page.getByRole("button", {
      name: /test|check|verify/i
    })

    if ((await testBtn.count()) === 0) {
      return false
    }

    await testBtn.click()

    // Wait for result
    const success = this.page.locator(
      ".ant-message-success, [data-testid='connection-success'], .connection-success"
    )
    const error = this.page.locator(
      ".ant-message-error, [data-testid='connection-error'], .connection-error"
    )

    try {
      await expect(success.or(error).first()).toBeVisible({ timeout: 15000 })
      return (await success.count()) > 0
    } catch {
      return false
    }
  }

  /**
   * Get current server configuration
   */
  async getServerConfig(): Promise<{
    serverUrl: string
    apiKey: string
    authMode: string
  }> {
    const stored = await this.page.evaluate(() =>
      localStorage.getItem("tldwConfig")
    )

    if (!stored) {
      return { serverUrl: "", apiKey: "", authMode: "single-user" }
    }

    const parsed = JSON.parse(stored)
    return {
      serverUrl: parsed.serverUrl || "",
      apiKey: parsed.apiKey || "",
      authMode: parsed.authMode || "single-user"
    }
  }

  /**
   * Navigate to a settings page via sidebar
   */
  async navigateViaMenu(menuItem: string): Promise<void> {
    const menuLink = this.page.getByRole("link", {
      name: new RegExp(menuItem, "i")
    })

    if ((await menuLink.count()) > 0) {
      await menuLink.first().click()
    } else {
      // Try menu item button
      const menuBtn = this.page.getByRole("menuitem", {
        name: new RegExp(menuItem, "i")
      })
      if ((await menuBtn.count()) > 0) {
        await menuBtn.click()
      }
    }
  }

  // ============ Model Settings ============

  /**
   * Add/configure an LLM provider
   */
  async configureProvider(
    provider: string,
    config: {
      apiKey?: string
      baseUrl?: string
      model?: string
    }
  ): Promise<void> {
    await this.gotoSection("model")
    await this.waitForReady()

    // Select or add provider
    const providerSelect = this.page.getByLabel(/provider/i)
    if ((await providerSelect.count()) > 0) {
      await providerSelect.click()
      const option = this.page.getByRole("option", {
        name: new RegExp(provider, "i")
      })
      if ((await option.count()) > 0) {
        await option.click()
      }
    }

    // Fill in configuration
    if (config.apiKey) {
      const keyInput = this.page.getByLabel(/api key/i).last()
      await keyInput.fill(config.apiKey)
    }

    if (config.baseUrl) {
      const urlInput = this.page.getByLabel(/base url|endpoint/i)
      await urlInput.fill(config.baseUrl)
    }

    if (config.model) {
      const modelInput = this.page.getByLabel(/model/i)
      await modelInput.fill(config.model)
    }

    await this.save()
  }

  /**
   * Get available providers
   */
  async getAvailableProviders(): Promise<string[]> {
    await this.gotoSection("model")
    await this.waitForReady()

    const providers: string[] = []
    const providerElements = this.page.locator(
      "[data-testid='provider-item'], .provider-card, .provider-option"
    )
    const count = await providerElements.count()

    for (let i = 0; i < count; i++) {
      const name = await providerElements.nth(i).textContent()
      if (name) providers.push(name.trim())
    }

    return providers
  }

  // ============ Chat Settings ============

  /**
   * Configure chat settings
   */
  async configureChatSettings(settings: {
    temperature?: number
    maxTokens?: number
    systemPrompt?: string
  }): Promise<void> {
    await this.gotoSection("chat")
    await this.waitForReady()

    if (settings.temperature !== undefined) {
      const tempInput = this.page.getByLabel(/temperature/i)
      if ((await tempInput.count()) > 0) {
        await tempInput.fill(String(settings.temperature))
      }
    }

    if (settings.maxTokens !== undefined) {
      const tokensInput = this.page.getByLabel(/max tokens|maximum tokens/i)
      if ((await tokensInput.count()) > 0) {
        await tokensInput.fill(String(settings.maxTokens))
      }
    }

    if (settings.systemPrompt) {
      const promptInput = this.page.getByLabel(/system prompt/i)
      if ((await promptInput.count()) > 0) {
        await promptInput.fill(settings.systemPrompt)
      }
    }

    await this.save()
  }

  /**
   * Get current chat settings
   */
  async getChatSettings(): Promise<{
    temperature?: number
    maxTokens?: number
    systemPrompt?: string
  }> {
    await this.gotoSection("chat")
    await this.waitForReady()

    const settings: {
      temperature?: number
      maxTokens?: number
      systemPrompt?: string
    } = {}

    const tempInput = this.page.getByLabel(/temperature/i)
    if ((await tempInput.count()) > 0) {
      const value = await tempInput.inputValue()
      settings.temperature = value ? parseFloat(value) : undefined
    }

    const tokensInput = this.page.getByLabel(/max tokens|maximum tokens/i)
    if ((await tokensInput.count()) > 0) {
      const value = await tokensInput.inputValue()
      settings.maxTokens = value ? parseInt(value, 10) : undefined
    }

    const promptInput = this.page.getByLabel(/system prompt/i)
    if ((await promptInput.count()) > 0) {
      settings.systemPrompt = (await promptInput.inputValue()) || undefined
    }

    return settings
  }

  // ============ Validation ============

  /**
   * Check for validation errors on form
   */
  async hasValidationErrors(): Promise<boolean> {
    const errors = this.page.locator(
      ".ant-form-item-explain-error, [data-error], .error-message, .validation-error"
    )
    return (await errors.count()) > 0
  }

  /**
   * Get validation error messages
   */
  async getValidationErrors(): Promise<string[]> {
    const errors = this.page.locator(
      ".ant-form-item-explain-error, [data-error], .error-message, .validation-error"
    )
    const messages: string[] = []

    const count = await errors.count()
    for (let i = 0; i < count; i++) {
      const text = await errors.nth(i).textContent()
      if (text) messages.push(text.trim())
    }

    return messages
  }

  // ============ Navigation ============

  /**
   * Get current settings section from URL
   */
  async getCurrentSection(): Promise<string> {
    const url = this.page.url()
    const match = url.match(/\/settings\/(\w+)/)
    return match ? match[1] : "main"
  }

  /**
   * Check for unsaved changes warning
   */
  async hasUnsavedChangesWarning(): Promise<boolean> {
    const warning = this.page.locator(
      "[data-testid='unsaved-warning'], .unsaved-changes, .ant-modal:has-text('unsaved')"
    )
    return (await warning.count()) > 0
  }

  /**
   * Confirm navigation with unsaved changes
   */
  async confirmNavigation(): Promise<void> {
    const confirmBtn = this.page.getByRole("button", {
      name: /confirm|leave|discard/i
    })
    if ((await confirmBtn.count()) > 0) {
      await confirmBtn.click()
    }
  }

  /**
   * Cancel navigation with unsaved changes
   */
  async cancelNavigation(): Promise<void> {
    const cancelBtn = this.page.getByRole("button", { name: /cancel|stay/i })
    if ((await cancelBtn.count()) > 0) {
      await cancelBtn.click()
    }
  }

  /**
   * Get breadcrumb items
   */
  async getBreadcrumbs(): Promise<string[]> {
    const breadcrumbs = this.page.locator(
      ".ant-breadcrumb-link, [data-testid='breadcrumb-item'], .breadcrumb-item"
    )
    const items: string[] = []

    const count = await breadcrumbs.count()
    for (let i = 0; i < count; i++) {
      const text = await breadcrumbs.nth(i).textContent()
      if (text) items.push(text.trim())
    }

    return items
  }
}
