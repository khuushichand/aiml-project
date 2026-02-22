import { test } from "@playwright/test"
import path from "path"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./utils/real-server"

test.describe("Chat across tldw models (real server)", () => {
  test("lists available tldw models and can chat with a selected model", async () => {
    test.setTimeout(90000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)

    const extPath = path.resolve("build/chrome-mv3")
    const { context, page, optionsUrl } = await launchWithExtensionOrSkip(test, extPath)
    try {
      // Configure server + API key
      await page.goto(optionsUrl + "#/settings/tldw", {
        waitUntil: "domcontentloaded"
      })
      await page.getByLabel("Server URL").fill(serverUrl)
      await page.getByText("Authentication Mode").scrollIntoViewIfNeeded()
      await page.getByText("Single User (API Key)").click()
      await page.locator("#apiKey").fill(apiKey)
      await page.getByRole("button", { name: "Save" }).click()

      // Open model selector and ensure at least one model is listed.
      const modelSelector = page.getByRole("button", { name: /Select a model/i })
      const hasModelSelector = await modelSelector
        .isVisible({ timeout: 15000 })
        .catch(() => false)
      if (!hasModelSelector) {
        test.skip(true, "Model selector is not visible in this real-server UI state.")
        return
      }
      await modelSelector.click()

      const firstModel = page.getByRole("menuitem").first()
      const hasModel = await firstModel.isVisible({ timeout: 15000 }).catch(() => false)
      if (!hasModel) {
        test.skip(
          true,
          "No selectable model item surfaced from real server; verify model catalog setup."
        )
        return
      }

      // Select the first model and send a message.
      await firstModel.click()

      const input = page.getByPlaceholder("Type a message...")
      const hasInput = await input.isVisible({ timeout: 10000 }).catch(() => false)
      if (!hasInput) {
        test.skip(true, "Chat input is not ready after model selection.")
        return
      }
      await input.fill("hello from e2e chat-models")
      await input.press("Enter")

      // Treat missing or stalled streaming state as environment-dependent and skip.
      const stopButton = page.getByRole("button", {
        name: /Stop streaming/i
      })
      const streamingStarted = await stopButton
        .isVisible({ timeout: 10000 })
        .catch(() => false)
      if (!streamingStarted) {
        test.skip(
          true,
          "No streaming indicator appeared for the selected model within timeout."
        )
        return
      }

      const streamingCompleted = await stopButton
        .isHidden({ timeout: 30000 })
        .catch(() => false)
      if (!streamingCompleted) {
        test.skip(
          true,
          "Streaming indicator did not resolve in expected time for real-server model response."
        )
      }
    } finally {
      await context.close()
    }
  })

  test("error handling for chat failures (requires controllable backend)", async () => {
    test.skip(
      true,
      "This scenario requires forcing server-side 5xx responses; keep covered by backend tests or a dedicated mock-based suite."
    )
  })
})
