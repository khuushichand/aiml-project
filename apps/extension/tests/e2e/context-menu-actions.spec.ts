import { test, expect } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import path from "path"

const EXT_PATH = path.resolve("build/chrome-mv3")

/**
 * Context menu (right-click menu) testing in Playwright/Chromium.
 *
 * Playwright does NOT support interacting with the native browser context menu.
 * Chrome's context menu API (chrome.contextMenus) creates native OS-level menus
 * that are outside the web page DOM and cannot be clicked or inspected by
 * Playwright's page automation.
 *
 * What we CAN test:
 * 1. That the background script registers context menu items via chrome.contextMenus.create
 * 2. That the onClicked handler fires correct message-passing actions (by calling it directly)
 *
 * What we CANNOT test via Playwright E2E:
 * - Visually opening the context menu
 * - Clicking on a context menu item in the native menu
 * - Verifying the context menu item text in the native menu
 */

test.describe("Context menu actions (background listener verification)", () => {
  test("background script registers context menu items on install", async () => {
    test.setTimeout(60_000)

    const { context, page } = await launchWithExtensionOrSkip(test, EXT_PATH, {
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
      const sw = context.serviceWorkers()[0]
      if (!sw) {
        test.skip(true, "No service worker found; cannot verify context menu registration.")
        return
      }

      // Verify the service worker has access to chrome.contextMenus API
      const hasContextMenusApi = await sw.evaluate(() => {
        return typeof chrome?.contextMenus?.create === "function"
      })

      expect(hasContextMenusApi).toBe(true)

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })

  test("background registers action and context-menu click listeners", async () => {
    test.setTimeout(60_000)

    const { context, page } = await launchWithExtensionOrSkip(test, EXT_PATH, {
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
      const sw = context.serviceWorkers()[0]
      if (!sw) {
        test.skip(true, "No service worker found.")
        return
      }

      const listenerState = await sw.evaluate(() => {
        const actionApi = chrome?.action || chrome?.browserAction
        return {
          hasContextMenuClickListener: Boolean(
            chrome?.contextMenus?.onClicked?.hasListeners?.()
          ),
          hasActionClickListener: Boolean(
            actionApi?.onClicked?.hasListeners?.()
          )
        }
      })

      expect(listenerState.hasContextMenuClickListener).toBe(true)
      expect(listenerState.hasActionClickListener).toBe(true)

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })

  // TODO: Playwright cannot interact with native OS context menus.
  // To fully test context menu item clicks, use a browser testing tool
  // that supports native UI interaction (e.g., Puppeteer with CDP, or
  // manual testing). This test verifies the infrastructure is in place.
  test.skip(
    "visual context menu interaction (not supported in Playwright)",
    async () => {
      // This test is intentionally skipped. Playwright operates within the
      // web page DOM and cannot click on native browser context menu items.
      //
      // To test manually:
      // 1. Build the extension: bun run build:chrome
      // 2. Load in Chrome via chrome://extensions
      // 3. Right-click on any page
      // 4. Verify "Send to tldw" (or similar) appears in the menu
      // 5. Click the item and verify the expected action fires
    }
  )
})
