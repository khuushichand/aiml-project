import path from "path"
import { expect, test } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import { forceConnected, waitForConnectionStore } from "./utils/connection"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

test.describe("ACP Playground route", () => {
  test("renders ACP playground page in options routes", async () => {
    const extPath = path.resolve("build/chrome-mv3")
    const serverBaseUrl = normalizeServerUrl("127.0.0.1:8000")

    const seed = {
      __tldw_first_run_complete: true,
      tldwConfig: {
        serverUrl: serverBaseUrl,
        authMode: "single-user",
        apiKey: "THIS-IS-A-SECURE-KEY-123-FAKE-KEY",
      },
    }

    const { context, page, extensionId } = await launchWithExtensionOrSkip(test, extPath, {
      seedConfig: seed,
    })

    const optionsUrl = `chrome-extension://${extensionId}/options.html#/acp-playground`
    await page.goto(optionsUrl, { waitUntil: "domcontentloaded" })
    await waitForConnectionStore(page, "acp-playground-route")
    await forceConnected(page, { serverUrl: serverBaseUrl }, "acp-playground-route")

    await expect(page.getByText(/Agent Playground/i)).toBeVisible({ timeout: 15000 })
    await expect(page.getByText(/^Sessions$/i)).toBeVisible({ timeout: 15000 })

    await context.close()
  })
})
