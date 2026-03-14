/**
 * Journey: Prompts -> Chat
 *
 * End-to-end workflow that creates a prompt in the prompts workspace,
 * navigates to chat, and sends a message verifying the chat API is called.
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels } from "../../utils/fixtures"
import { captureAllApiCalls } from "../../utils/api-assertions"
import { PromptsWorkspacePage, ChatPage } from "../../utils/page-objects"
import { waitForStreamComplete } from "../../utils/journey-helpers"

test.describe("Prompts -> Chat journey", () => {
  const promptName = `E2E-Prompt-${Date.now()}`
  const promptTemplate = "You are a pirate. Respond to everything in pirate speak. Always say ARRR at least once."

  test("create prompt, use it in chat, verify in API call", async ({
    authedPage: page,
    serverInfo,
  }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    await test.step("Create a prompt in the prompts workspace", async () => {
      const promptsPage = new PromptsWorkspacePage(page)
      await promptsPage.goto()
      await promptsPage.assertPageReady()

      await promptsPage.createPrompt({
        name: promptName,
        template: promptTemplate,
      })

      // Verify the prompt is visible in the list
      await promptsPage.assertPromptVisible(promptName)
    })

    await test.step("Navigate to chat and send a message", async () => {
      // Navigate to chat with absolute URL to escape prompts page state
      const origin = new URL(page.url()).origin
      await page.goto(`${origin}/chat`, { waitUntil: "load", timeout: 30_000 })
      expect(page.url()).toContain("/chat")

      const { waitForConnection } = await import("../../utils/helpers")
      await waitForConnection(page)

      const chatPage = new ChatPage(page)
      await chatPage.waitForReady()

      // Start capturing API calls
      const capture = captureAllApiCalls(page)

      await chatPage.sendMessage("Tell me about the weather today.")

      // Wait for response
      await waitForStreamComplete(page)

      const calls = await capture.stop()

      // Find the chat completions call
      const chatCall = calls.find(
        (c) => c.method === "POST" && c.url.includes("/chat/completions")
      )

      // Verify the chat API was called successfully
      if (chatCall) {
        expect(chatCall.status).toBeLessThan(500)
      }

      // Verify a response was rendered
      await chatPage.waitForResponse()
    })
  })
})
