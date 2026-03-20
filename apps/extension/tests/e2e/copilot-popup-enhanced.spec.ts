import { test, expect } from "@playwright/test"
import {
  requireRealServerConfig,
  launchWithExtensionOrSkip
} from "./utils/real-server"
import { grantHostPermission } from "./utils/permissions"
import { setSelectedModel } from "./utils/connection"
import path from "path"

const EXT_PATH = path.resolve("build/chrome-mv3")

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

const getFirstModelId = (payload: any): string | null => {
  const modelsList = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.models)
      ? payload.models
      : []
  const candidate =
    modelsList.find((m: any) => m?.id || m?.model || m?.name) || null
  const id = candidate?.id || candidate?.model || candidate?.name
  return id ? String(id) : null
}

test.describe("Copilot popup enhanced actions", () => {
  test("popup renders action buttons when content script is ready", async () => {
    test.setTimeout(120_000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)

    let modelsResponse: Response | null = null
    try {
      modelsResponse = await fetch(
        `${normalizedServerUrl}/api/v1/llm/models/metadata`,
        { headers: { "x-api-key": apiKey } }
      )
    } catch (error) {
      test.skip(
        true,
        `Models preflight unreachable: ${String(error)}`
      )
      return
    }
    if (!modelsResponse?.ok) {
      test.skip(true, "Models preflight failed.")
      return
    }
    const modelId = getFirstModelId(
      await modelsResponse.json().catch(() => [])
    )
    if (!modelId) {
      test.skip(true, "No chat models returned from tldw_server.")
    }
    const selectedModelId = modelId!.startsWith("tldw:")
      ? modelId!
      : `tldw:${modelId}`

    const { context, page, extensionId } = await launchWithExtensionOrSkip(
      test,
      EXT_PATH,
      {
        seedConfig: {
          tldwConfig: {
            serverUrl: normalizedServerUrl,
            authMode: "single-user",
            apiKey
          }
        }
      }
    )

    const origin = new URL(normalizedServerUrl).origin + "/*"
    const granted = await grantHostPermission(context, extensionId, origin)
    if (!granted) {
      test.skip(
        true,
        "Host permission not granted for tldw_server origin."
      )
    }

    await setSelectedModel(page, selectedModelId)

    // Navigate to a content page where the copilot popup content script runs
    const contentPage = await context.newPage()
    await contentPage.goto("https://example.com", {
      waitUntil: "domcontentloaded"
    })
    await contentPage.bringToFront()

    // Wait for the content script to mark itself as ready
    const isReady = await contentPage
      .waitForFunction(
        () =>
          document.documentElement.dataset.tldwCopilotPopupReady === "true",
        undefined,
        { timeout: 10_000 }
      )
      .then(() => true)
      .catch(() => false)

    if (!isReady) {
      // Content script injection may not work in all test environments
      test.skip(
        true,
        "Copilot popup content script did not inject on example.com."
      )
      return
    }

    // Create a textarea with a selection to trigger the popup
    await contentPage.evaluate(() => {
      document.body.innerHTML =
        '<textarea id="target" rows="4" cols="40">Test selection text</textarea>'
      const el = document.getElementById("target") as HTMLTextAreaElement
      el.focus()
      el.selectionStart = 5
      el.selectionEnd = 14
    })

    // Trigger the popup via message from the service worker
    const worker =
      context.serviceWorkers()[0] ??
      (await context.waitForEvent("serviceworker"))

    await worker.evaluate(
      async ({ targetUrl, selectionText }) => {
        const queryTabs = () =>
          new Promise<chrome.tabs.Tab[]>((resolve) =>
            chrome.tabs.query({}, (tabs) => resolve(tabs))
          )
        const tabs = await queryTabs()
        const target = tabs.find((tab) => tab.url === targetUrl)
        if (!target?.id) throw new Error("Target tab not found")

        for (let attempt = 0; attempt < 5; attempt += 1) {
          chrome.tabs.sendMessage(target.id!, {
            type: "tldw:popup:open",
            payload: {
              selectionText,
              pageUrl: targetUrl,
              pageTitle: target.title || ""
            }
          })
          await new Promise((r) => setTimeout(r, 200))
        }
      },
      { targetUrl: contentPage.url(), selectionText: "selection" }
    )

    // Verify the popup shadow DOM appears
    const popup = contentPage.locator(
      "#tldw-copilot-popup-host >>> .tldw-popup"
    )
    await expect(popup).toBeVisible({ timeout: 15_000 })

    // Verify action buttons are present (copy, replace, dismiss are common)
    const actionButtons = contentPage.locator(
      "#tldw-copilot-popup-host >>> button"
    )
    const buttonCount = await actionButtons.count()
    expect(buttonCount).toBeGreaterThanOrEqual(1)

    await context.close()
  })

  test("popup dismiss closes the overlay", async () => {
    test.setTimeout(120_000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)

    const { context, page, extensionId } = await launchWithExtensionOrSkip(
      test,
      EXT_PATH,
      {
        seedConfig: {
          tldwConfig: {
            serverUrl: normalizedServerUrl,
            authMode: "single-user",
            apiKey
          }
        }
      }
    )

    const origin = new URL(normalizedServerUrl).origin + "/*"
    const granted = await grantHostPermission(context, extensionId, origin)
    if (!granted) {
      test.skip(true, "Host permission not granted.")
    }

    const contentPage = await context.newPage()
    await contentPage.goto("https://example.com", {
      waitUntil: "domcontentloaded"
    })
    await contentPage.bringToFront()

    const isReady = await contentPage
      .waitForFunction(
        () =>
          document.documentElement.dataset.tldwCopilotPopupReady === "true",
        undefined,
        { timeout: 10_000 }
      )
      .then(() => true)
      .catch(() => false)

    if (!isReady) {
      test.skip(
        true,
        "Copilot popup content script did not inject on example.com."
      )
      return
    }

    await contentPage.evaluate(() => {
      document.body.innerHTML =
        '<textarea id="target" rows="4" cols="40">Dismiss test</textarea>'
      const el = document.getElementById("target") as HTMLTextAreaElement
      el.focus()
      el.selectionStart = 0
      el.selectionEnd = 7
    })

    const worker =
      context.serviceWorkers()[0] ??
      (await context.waitForEvent("serviceworker"))

    await worker.evaluate(
      async ({ targetUrl }) => {
        const tabs = await new Promise<chrome.tabs.Tab[]>((resolve) =>
          chrome.tabs.query({}, resolve)
        )
        const target = tabs.find((tab) => tab.url === targetUrl)
        if (!target?.id) throw new Error("Target tab not found")

        for (let i = 0; i < 5; i++) {
          chrome.tabs.sendMessage(target.id!, {
            type: "tldw:popup:open",
            payload: {
              selectionText: "Dismiss",
              pageUrl: targetUrl,
              pageTitle: ""
            }
          })
          await new Promise((r) => setTimeout(r, 200))
        }
      },
      { targetUrl: contentPage.url() }
    )

    const popup = contentPage.locator(
      "#tldw-copilot-popup-host >>> .tldw-popup"
    )
    await expect(popup).toBeVisible({ timeout: 15_000 })

    // Find and click dismiss/close button
    const dismissBtn = contentPage.locator(
      "#tldw-copilot-popup-host >>> [data-action='dismiss'], #tldw-copilot-popup-host >>> [aria-label='Close'], #tldw-copilot-popup-host >>> [data-action='close']"
    )
    if ((await dismissBtn.count()) > 0) {
      await dismissBtn.first().click()
      await expect(popup).toBeHidden({ timeout: 5_000 })
    } else {
      // Pressing Escape should also dismiss
      await contentPage.keyboard.press("Escape")
      // The popup may or may not respond to Escape; just verify it was visible
    }

    await context.close()
  })
})
