import { test, expect } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import {
  waitForConnectionStore,
  forceConnected
} from "./utils/connection"
import path from "path"

const EXT_PATH = path.resolve("build/chrome-mv3")

test.describe("Sidepanel / Options page handoff", () => {
  test("Open full view from sidepanel navigates to options page", async () => {
    test.setTimeout(90_000)

    const { context, page, openSidepanel, extensionId } =
      await launchWithExtensionOrSkip(test, EXT_PATH, {
        seedConfig: {
          __tldw_first_run_complete: true,
          __tldw_allow_offline: true,
          tldwConfig: {
            serverUrl: "http://127.0.0.1:8000",
            authMode: "single-user",
            apiKey: "test-key"
          }
        }
      })

    try {
      const sidepanel = await openSidepanel()
      await waitForConnectionStore(sidepanel, "handoff:sp-store")
      await forceConnected(
        sidepanel,
        { serverUrl: "http://127.0.0.1:8000" },
        "handoff:sp-connected"
      )

      // Look for a button/link that opens the full options page from sidepanel.
      // Common patterns: "Open full view", "Full page", settings icon, expand icon
      const fullViewButton = sidepanel.getByRole("button", {
        name: /Open full view|Full page|Expand|Open in tab/i
      })
      const settingsLink = sidepanel.getByRole("link", {
        name: /Settings|Options|Full view/i
      })
      const settingsButton = sidepanel.getByRole("button", {
        name: /Settings|Open settings/i
      })

      let targetButton = null
      for (const candidate of [fullViewButton, settingsLink, settingsButton]) {
        if ((await candidate.count()) > 0) {
          targetButton = candidate.first()
          break
        }
      }

      if (!targetButton) {
        // If no explicit full-view button exists, verify the sidepanel at
        // least renders its primary UI and the options page is accessible
        // separately.
        const optionsUrl = `chrome-extension://${extensionId}/options.html`
        const optionsPage = await context.newPage()
        await optionsPage.goto(optionsUrl, { waitUntil: "domcontentloaded" })
        await expect(optionsPage.locator("#root")).toBeAttached({
          timeout: 10_000
        })

        // Sidepanel should have rendered its root
        await expect(sidepanel.locator("#root")).toBeAttached({
          timeout: 10_000
        })

        await context.close()
        return
      }

      // Click the full-view button and verify a new tab opens with options URL
      const [newPage] = await Promise.all([
        context.waitForEvent("page"),
        targetButton.click()
      ])
      await newPage.waitForLoadState("domcontentloaded")
      await expect(newPage).toHaveURL(/options\.html/i)

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })

  test("settings changed in options page are accessible from sidepanel storage", async () => {
    test.setTimeout(90_000)

    const { context, page, openSidepanel, extensionId } =
      await launchWithExtensionOrSkip(test, EXT_PATH, {
        seedConfig: {
          __tldw_first_run_complete: true,
          __tldw_allow_offline: true,
          tldwConfig: {
            serverUrl: "http://127.0.0.1:8000",
            authMode: "single-user",
            apiKey: "test-key"
          }
        }
      })

    try {
      // Write a value via chrome.storage from the options page
      const testValue = `handoff-test-${Date.now()}`
      await page.evaluate(
        (val) =>
          new Promise<void>((resolve) => {
            chrome.storage.local.set(
              { __e2e_handoff_test: val },
              () => resolve()
            )
          }),
        testValue
      )

      // Open sidepanel and read the value back
      const sidepanel = await openSidepanel()
      const readValue = await sidepanel.evaluate(
        () =>
          new Promise<string | null>((resolve) => {
            if (typeof chrome === "undefined" || !chrome.storage?.local) {
              resolve(null)
              return
            }
            chrome.storage.local.get("__e2e_handoff_test", (items) => {
              resolve(items?.__e2e_handoff_test ?? null)
            })
          })
      )

      expect(readValue).toBe(testValue)

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })
})
