import { test, expect, type Page } from "@playwright/test"
import path from "path"
import { grantHostPermission } from "./utils/permissions"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./utils/real-server"
import { waitForConnectionStore } from "./utils/connection"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value.replace(/\/$/, "") : `http://${value}`

const fetchWritingCapabilities = async (serverUrl: string, apiKey: string) => {
  const res = await fetch(
    `${serverUrl}/api/v1/writing/capabilities?include_providers=false`,
    {
      headers: { "x-api-key": apiKey }
    }
  ).catch(() => null)
  if (!res || !res.ok) return null
  return await res.json().catch(() => null)
}

const waitForConnected = async (page: Page, label: string) => {
  await waitForConnectionStore(page, label)
  await page.evaluate(() => {
    const store = (window as any).__tldw_useConnectionStore
    try {
      store?.getState?.().markFirstRunComplete?.()
      store?.getState?.().checkOnce?.()
    } catch {
      // ignore connection triggers
    }
    window.dispatchEvent(new CustomEvent("tldw:check-connection"))
  })
  await page.waitForFunction(
    () => {
      const store = (window as any).__tldw_useConnectionStore
      const state = store?.getState?.().state
      return state?.isConnected === true && state?.phase === "connected"
    },
    undefined,
    { timeout: 20000 }
  )
}

const ensurePageVisible = async (page: Page) => {
  try {
    await page.bringToFront()
  } catch {
    // ignore bringToFront failures in headless contexts
  }
  try {
    await page.waitForFunction(
      () => document.visibilityState === "visible",
      undefined,
      { timeout: 5000 }
    )
  } catch {
    // ignore visibility polling failures
  }
}

const openWritingPlayground = async (page: Page, optionsUrl: string) => {
  await ensurePageVisible(page)
  await page.goto(optionsUrl + "#/writing-playground", {
    waitUntil: "domcontentloaded"
  })
  await page.waitForFunction(() => !!document.querySelector("#root"), undefined, {
    timeout: 10000
  })
  await page.evaluate(() => {
    const navigate = (window as any).__tldwNavigate
    if (typeof navigate === "function") {
      navigate("/writing-playground")
    }
  })
}

const createSession = async (page: Page, name: string) => {
  await page.getByRole("button", { name: /New session/i }).click()
  const modal = page.getByRole("dialog", { name: /New session/i })
  await expect(modal).toBeVisible()
  const input = modal.getByRole("textbox")
  await input.fill(name)
  const okButton = modal.getByRole("button", { name: /OK|Create/i })
  await okButton.click()
  await expect(modal).toBeHidden()
  const row = page.locator(".ant-list-item").filter({ hasText: name }).first()
  await expect(row).toBeVisible({ timeout: 15000 })
  await row.click()
}

test.describe("Writing Playground mode parity", () => {
  test("switches modes with keyboard support and preserves draft input", async () => {
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)
    const caps = await fetchWritingCapabilities(normalizedServerUrl, apiKey)
    if (!caps?.server?.sessions) {
      test.skip(true, "Writing sessions not available on the configured server.")
    }

    const extPath = path.resolve("build/chrome-mv3")
    const { context, page, extensionId, optionsUrl } = await launchWithExtensionOrSkip(
      test,
      extPath,
      {
        seedConfig: {
          __tldw_first_run_complete: true,
          __tldw_allow_offline: true,
          tldwConfig: {
            serverUrl: normalizedServerUrl,
            authMode: "single-user",
            apiKey
          }
        }
      }
    )

    try {
      const origin = new URL(normalizedServerUrl).origin + "/*"
      const granted = await grantHostPermission(context, extensionId, origin)
      if (!granted) {
        test.skip(
          true,
          "Host permission not granted for tldw_server origin; allow it in chrome://extensions > tldw Assistant > Site access, then re-run"
        )
      }

      await openWritingPlayground(page, optionsUrl)
      await waitForConnected(page, "writing-playground-mode-parity")
      await expect(
        page.getByRole("heading", { name: /Writing Playground/i })
      ).toBeVisible()

      const unique = `${Date.now()}-${test.info().workerIndex}-${Math.random()
        .toString(36)
        .slice(2, 6)}`
      const sessionName = `E2E Writing Mode ${unique}`
      await createSession(page, sessionName)

      const modeSwitch = page.getByTestId("writing-workspace-mode-switch")
      await expect(modeSwitch).toBeVisible()
      await expect(page.getByTestId("writing-section-draft-editor")).toBeVisible()
      await expect(page.getByTestId("writing-section-manage-generation")).toBeHidden()

      const editor = page.getByPlaceholder(/Start writing your prompt/i)
      const draftText = "Draft text that must survive mode toggle"
      await editor.fill(draftText)

      await modeSwitch.click()
      await page.keyboard.press("ArrowRight")
      await expect(page.getByTestId("writing-section-manage-generation")).toBeVisible()
      await expect(page.getByTestId("writing-mode-live-region")).toContainText(/Manage/i)
      await expect(page.getByTestId("writing-section-draft-editor")).toBeHidden()

      await page.getByTestId("writing-mode-draft").click()
      await expect(page.getByTestId("writing-section-draft-editor")).toBeVisible()
      await expect(page.getByTestId("writing-mode-live-region")).toContainText(/Draft/i)
      await expect(editor).toHaveValue(draftText)
    } finally {
      await context.close()
    }
  })
})
