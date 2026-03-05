import { test, expect, type Page } from "@playwright/test"
import { startLoopParityMockServer } from "../../../../tests/e2e-utils/chat-tool-parity-mock-server"

const MODEL_ID = "mock-model"
const MODEL_KEY = `tldw:${MODEL_ID}`

const seedChatConfig = async (page: Page, serverUrl: string) => {
  await page.addInitScript(
    ({ url, model }) => {
      const cfg = {
        serverUrl: url,
        authMode: "single-user",
        apiKey: "test-key",
      }
      localStorage.setItem("tldwConfig", JSON.stringify(cfg))
      localStorage.setItem("plasmo-storage-tldwConfig", JSON.stringify(cfg))
      localStorage.setItem("__tldw_first_run_complete", "true")
      localStorage.setItem("__tldw_allow_offline", "true")
      localStorage.setItem("selectedModel", model)
      localStorage.setItem("plasmo-storage-selectedModel", JSON.stringify(model))
      localStorage.setItem(
        "tldw-ui-mode",
        JSON.stringify({
          state: { mode: "pro" },
          version: 0,
        })
      )
    },
    { url: serverUrl, model: MODEL_KEY }
  )
}

const openToolRunPanel = async (page: Page) => {
  const toolRunRow = page.getByText(/Tool run:/i).first()
  if (await toolRunRow.isVisible({ timeout: 1_500 }).catch(() => false)) {
    return
  }

  const controlMenu = page.getByTestId("control-more-menu").first()
  if (await controlMenu.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await controlMenu.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const mcpToggle = page.getByTestId("mcp-tools-toggle").first()
  const mcpToggleVisible = await mcpToggle
    .isVisible({ timeout: 3_000 })
    .catch(() => false)
  if (mcpToggleVisible) {
    if (await mcpToggle.isDisabled().catch(() => false)) {
      await expect(mcpToggle).toBeEnabled({ timeout: 10_000 })
    }
    await mcpToggle.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const mcpAriaButton = page
    .getByRole("button", { name: /mcp tools/i })
    .first()
  if (await mcpAriaButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await mcpAriaButton.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const moreToolsButton = page
    .getByRole("button", { name: /\+tools|more tools/i })
    .first()
  if (await moreToolsButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await moreToolsButton.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const casualAdvancedToggle = page.getByTestId("composer-casual-advanced-toggle").first()
  const casualToggleVisible = await casualAdvancedToggle
    .isVisible({ timeout: 3_000 })
    .catch(() => false)
  if (casualToggleVisible) {
    await casualAdvancedToggle.click({ force: true })
    await expect(mcpToggle).toBeVisible({ timeout: 10_000 })
    await mcpToggle.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  throw new Error("Unable to open MCP tool run panel for status assertions")
}

const readToolRunStatus = async (page: Page): Promise<string> => {
  const rows = page.locator("text=/Tool run:/i")
  const count = await rows.count()
  for (let i = 0; i < count; i++) {
    const row = rows.nth(i)
    if (await row.isVisible()) {
      return (await row.textContent()) || ""
    }
  }
  return ""
}

test.describe("Chat tool approval parity", () => {
  test("shows pending, running, then done in /chat", async ({ page }) => {
    test.setTimeout(90_000)
    const { server, baseUrl, getStats } = await startLoopParityMockServer(MODEL_ID)

    try {
      await seedChatConfig(page, baseUrl)
      await page.goto("/chat", { waitUntil: "domcontentloaded" })

      const input = page.getByTestId("chat-input")
      await expect(input).toBeVisible({ timeout: 20_000 })
      await expect
        .poll(
          () =>
            page.evaluate(() => {
              return Boolean((window as any).__tldw_useStoreMessageOption?.setState)
            }),
          { timeout: 10_000 }
        )
        .toBe(true)
      await page.evaluate(() => {
        ;(window as any).__tldw_useStoreMessageOption?.setState({
          toolChoice: "auto",
          temporaryChat: true,
        })
      })

      await input.fill(`Loop parity check ${Date.now()}`)

      const sendButton = page.getByRole("button", { name: /^send$/i }).first()
      if ((await sendButton.count()) > 0 && (await sendButton.isVisible())) {
        await sendButton.click()
      } else {
        await input.press("Enter")
      }

      await expect
        .poll(
          async () => {
            await openToolRunPanel(page)
            return readToolRunStatus(page)
          },
          { timeout: 7_000 }
        )
        .toMatch(/pending approval/i)
      await expect
        .poll(
          async () => {
            await openToolRunPanel(page)
            return readToolRunStatus(page)
          },
          { timeout: 9_000 }
        )
        .toMatch(/running/i)
      await expect
        .poll(
          async () => {
            await openToolRunPanel(page)
            return readToolRunStatus(page)
          },
          { timeout: 12_000 }
        )
        .toMatch(/done/i)
      expect(getStats().chatCompletions).toBeGreaterThan(0)
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  })
})
