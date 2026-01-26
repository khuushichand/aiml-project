/**
 * Page Object for Chat functionality
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { waitForConnection } from "../helpers"

export class ChatPage {
  readonly page: Page
  readonly header: Locator
  readonly messageInput: Locator
  readonly sendButton: Locator
  readonly messageList: Locator
  readonly sidebar: Locator
  readonly newChatButton: Locator
  readonly modelSelector: Locator

  constructor(page: Page) {
    this.page = page
    this.header = page.getByTestId("chat-header")
    this.messageInput = page.locator("#textarea-message, [data-testid='chat-input']")
    this.sendButton = page.getByRole("button", { name: /send/i })
    this.messageList = page.getByTestId("chat-messages")
    this.sidebar = page.getByTestId("chat-sidebar")
    this.newChatButton = page.getByRole("button", { name: /new chat|start chat/i })
    this.modelSelector = page.getByTestId("model-selector")
  }

  /**
   * Navigate to the chat page
   */
  async goto(): Promise<void> {
    await this.page.goto("/chat", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  /**
   * Wait for the chat page to be ready
   */
  async waitForReady(): Promise<void> {
    await expect(this.header).toBeVisible({ timeout: 20000 })
  }

  /**
   * Get the chat input (handles multiple possible selectors)
   */
  async getChatInput(): Promise<Locator> {
    // Try primary selector
    let input = this.page.locator("#textarea-message")
    if ((await input.count()) > 0) return input

    // Try testid selector
    input = this.page.getByTestId("chat-input")
    if ((await input.count()) > 0) return input

    // Try placeholder-based selector
    return this.page.getByPlaceholder(/Ask anything|Type a message/i)
  }

  /**
   * Send a message in the chat
   */
  async sendMessage(message: string): Promise<void> {
    const input = await this.getChatInput()
    await expect(input).toBeVisible({ timeout: 15000 })

    // Click "Start chatting" if visible
    const startChat = this.page.getByRole("button", { name: /Start chatting/i })
    if ((await startChat.count()) > 0 && (await startChat.isVisible())) {
      await startChat.click()
    }

    await input.fill(message)

    // Find and click send button
    const sendButton =
      this.page.getByTestId("send-button") ||
      this.page.getByRole("button", { name: /send/i })

    if ((await sendButton.count()) > 0 && (await sendButton.isVisible())) {
      await sendButton.click()
    } else {
      // Fallback to keyboard submit
      await input.press("Enter")
    }
  }

  /**
   * Wait for a response to appear
   */
  async waitForResponse(timeoutMs = 60000): Promise<void> {
    // Wait for assistant message to appear
    const assistantMessage = this.page.locator(
      "[data-role='assistant'], [data-message-role='assistant'], .assistant-message"
    )
    await expect(assistantMessage.first()).toBeVisible({ timeout: timeoutMs })
  }

  /**
   * Wait for streaming to complete
   */
  async waitForStreamingComplete(timeoutMs = 60000): Promise<void> {
    // Wait for streaming indicator to disappear
    const streamingIndicator = this.page.locator(
      "[data-streaming='true'], .streaming, .typing-indicator"
    )

    // First wait for streaming to start (or skip if message already complete)
    const streamingStarted = await streamingIndicator.isVisible().catch(() => false)

    if (streamingStarted) {
      // Wait for streaming to complete
      await expect(streamingIndicator).not.toBeVisible({ timeout: timeoutMs })
    }
  }

  /**
   * Get all messages in the conversation
   */
  async getMessages(): Promise<Array<{ role: string; content: string }>> {
    const messages: Array<{ role: string; content: string }> = []

    const messageElements = this.page.locator(
      "[data-role], [data-message-role], .message"
    )
    const count = await messageElements.count()

    for (let i = 0; i < count; i++) {
      const el = messageElements.nth(i)
      const role =
        (await el.getAttribute("data-role")) ||
        (await el.getAttribute("data-message-role")) ||
        "unknown"
      const content = (await el.textContent()) || ""
      messages.push({ role, content })
    }

    return messages
  }

  /**
   * Start a new conversation
   */
  async startNewConversation(): Promise<void> {
    const newChatBtn = this.page.getByRole("button", {
      name: /new chat|new conversation/i
    })

    if ((await newChatBtn.count()) > 0) {
      await newChatBtn.first().click()
    } else {
      // Try keyboard shortcut
      await this.page.keyboard.press("Meta+n")
    }
  }

  /**
   * Open the command palette
   */
  async openCommandPalette(): Promise<void> {
    await this.page.keyboard.press("Meta+k")
    const palette = this.page.getByRole("dialog", { name: /command/i })
    await expect(palette).toBeVisible({ timeout: 5000 })
  }

  /**
   * Close the command palette
   */
  async closeCommandPalette(): Promise<void> {
    await this.page.keyboard.press("Escape")
  }

  /**
   * Select a model from the model selector
   */
  async selectModel(modelId: string): Promise<void> {
    // Click model selector to open dropdown
    const selector =
      this.modelSelector || this.page.getByTestId("model-select-trigger")

    if ((await selector.count()) > 0) {
      await selector.click()

      // Find and click the model option
      const modelOption = this.page.getByRole("option", { name: new RegExp(modelId, "i") })
      if ((await modelOption.count()) > 0) {
        await modelOption.click()
      }
    }
  }

  /**
   * Toggle chat history persistence
   */
  async togglePersistence(enabled: boolean): Promise<void> {
    const toggle = this.page.getByRole("switch", {
      name: /Save chat to history|Temporary chat/i
    })

    if ((await toggle.count()) === 0) return

    const isChecked =
      (await toggle.getAttribute("aria-checked")) === "true"

    if ((enabled && !isChecked) || (!enabled && isChecked)) {
      await toggle.click()
    }
  }

  /**
   * Get conversation history from sidebar
   */
  async getConversationHistory(): Promise<string[]> {
    const sidebarItems = this.page.locator(
      "[data-testid='chat-history-item'], .conversation-item"
    )
    const count = await sidebarItems.count()
    const titles: string[] = []

    for (let i = 0; i < count; i++) {
      const title = await sidebarItems.nth(i).textContent()
      if (title) titles.push(title.trim())
    }

    return titles
  }

  /**
   * Copy the last message to clipboard
   */
  async copyLastMessage(): Promise<void> {
    const copyButtons = this.page.locator(
      "[data-testid='copy-message'], button[aria-label*='copy' i]"
    )
    const lastCopy = copyButtons.last()

    if ((await lastCopy.count()) > 0) {
      await lastCopy.click()
    }
  }

  /**
   * Check if code block is rendered properly
   */
  async hasCodeBlock(): Promise<boolean> {
    const codeBlock = this.page.locator("pre code, .code-block, [data-code-block]")
    return (await codeBlock.count()) > 0
  }

  /**
   * Check if markdown is rendered properly
   */
  async hasRenderedMarkdown(): Promise<boolean> {
    // Check for common rendered markdown elements
    const markdownElements = this.page.locator(
      ".prose h1, .prose h2, .prose ul, .prose ol, .markdown-content"
    )
    return (await markdownElements.count()) > 0
  }
}
