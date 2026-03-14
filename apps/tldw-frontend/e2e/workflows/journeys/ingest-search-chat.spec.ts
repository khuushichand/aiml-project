/**
 * Journey: Ingest -> Search -> Chat
 *
 * End-to-end workflow that ingests content via URL, searches for it,
 * then chats about it with RAG context.
 */
import { test, expect, skipIfServerUnavailable, skipIfNoModels } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { ChatPage, SearchPage } from "../../utils/page-objects"
import { ingestAndWaitForReady, waitForStreamComplete } from "../../utils/journey-helpers"

test.describe("Ingest -> Search -> Chat journey", () => {
  test("ingest content, search for it, then chat with RAG context", async ({
    authedPage: page,
    serverInfo,
  }) => {
    skipIfServerUnavailable(serverInfo)
    skipIfNoModels(serverInfo)

    const testUrl = "https://en.wikipedia.org/wiki/Playwright_(software)"
    let mediaId: string

    await test.step("Ingest content via URL", async () => {
      mediaId = await ingestAndWaitForReady(page, { url: testUrl })
      expect(mediaId).toBeTruthy()
    })

    await test.step("Search for the ingested content", async () => {
      const searchPage = new SearchPage(page)
      await searchPage.goto()
      await searchPage.waitForReady()

      await searchPage.search("Playwright")
      await searchPage.waitForResults()

      const results = await searchPage.getResults()
      // We expect at least one result related to the ingested content
      expect(results.length).toBeGreaterThan(0)
    })

    await test.step("Chat about ingested content with RAG context", async () => {
      const chatPage = new ChatPage(page)
      await chatPage.goto()
      await chatPage.waitForReady()

      // Set up API call expectation for chat completions
      const chatApiCall = expectApiCall(page, {
        method: "POST",
        url: "/api/v1/chat/completions",
      }, 60_000)

      await chatPage.sendMessage("What is Playwright? Use the ingested content to answer.")

      const { response } = await chatApiCall
      expect(response.status()).toBeLessThan(500)

      // Wait for the response to stream in
      await waitForStreamComplete(page)

      // Verify an assistant message appeared
      await chatPage.waitForResponse()
    })
  })
})
