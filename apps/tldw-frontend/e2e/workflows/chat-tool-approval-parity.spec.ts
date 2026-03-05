import { test, expect, type Page } from "@playwright/test"
import http from "node:http"
import type { AddressInfo } from "node:net"

const MODEL_ID = "mock-model"
const MODEL_KEY = `tldw:${MODEL_ID}`

const readBody = (req: http.IncomingMessage) =>
  new Promise<string>((resolve) => {
    let body = ""
    req.on("data", (chunk) => {
      body += chunk
    })
    req.on("end", () => resolve(body))
  })

const startLoopParityMockServer = async () => {
  const stats = {
    chatCompletions: 0,
  }
  const server = http.createServer(async (req, res) => {
    const method = (req.method || "GET").toUpperCase()
    const url = req.url || "/"
    const requestOrigin =
      typeof req.headers.origin === "string" && req.headers.origin.length > 0
        ? req.headers.origin
        : "*"

    const sendJson = (code: number, payload: unknown) => {
      res.writeHead(code, {
        "content-type": "application/json",
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        vary: "origin",
      })
      res.end(JSON.stringify(payload))
    }

    if (method === "OPTIONS") {
      const requestedHeaders =
        typeof req.headers["access-control-request-headers"] === "string"
          ? req.headers["access-control-request-headers"]
          : "content-type, x-api-key, authorization, cache-control, accept"
      const requestedMethod =
        typeof req.headers["access-control-request-method"] === "string"
          ? req.headers["access-control-request-method"]
          : "POST"
      res.writeHead(204, {
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        "access-control-allow-methods": `GET,POST,OPTIONS,${requestedMethod}`,
        "access-control-allow-headers": requestedHeaders,
        vary: "origin",
      })
      return res.end()
    }

    if (url === "/api/v1/health" && method === "GET") {
      return sendJson(200, { status: "ok" })
    }

    if (url === "/openapi.json" && method === "GET") {
      return sendJson(200, {
        openapi: "3.0.0",
        info: { version: "mock" },
        paths: {
          "/api/v1/health": {},
          "/api/v1/chat/completions": {},
          "/api/v1/llm/models": {},
          "/api/v1/llm/models/metadata": {},
          "/api/v1/characters": {},
          "/api/v1/characters/search": {},
          "/api/v1/mcp/health": {},
          "/api/v1/mcp/tools": {},
          "/api/v1/mcp/tools/execute": {},
        },
      })
    }

    if (url.startsWith("/api/v1/llm/models/metadata") && method === "GET") {
      return sendJson(200, [
        {
          id: MODEL_ID,
          name: "Mock Model",
          provider: "mock",
          context_length: 8192,
          capabilities: ["chat", "tools"],
        },
      ])
    }

    if (url === "/api/v1/llm/models" && method === "GET") {
      return sendJson(200, [MODEL_ID])
    }

    if (url.startsWith("/api/v1/characters") && method === "GET") {
      return sendJson(200, [])
    }

    if (url.startsWith("/api/v1/characters") && method === "POST") {
      return sendJson(200, [])
    }

    if (url === "/api/v1/mcp/health" && method === "GET") {
      return sendJson(200, { ok: true })
    }

    if (url.startsWith("/api/v1/mcp/tools") && method === "GET") {
      return sendJson(200, [
        {
          name: "mock_tool",
          description: "Mock tool for parity tests",
          canExecute: true,
        },
      ])
    }

    if (url === "/api/v1/mcp/tools/execute" && method === "POST") {
      const body = await readBody(req)
      let parsed: Record<string, unknown> = {}
      try {
        parsed = JSON.parse(body || "{}")
      } catch {
        parsed = {}
      }
      const toolName = String(parsed.tool_name || "")
      if (toolName === "mcp.tools.list") {
        return sendJson(200, {
          result: {
            tools: [
              {
                name: "mock_tool",
                description: "Mock tool for parity tests",
                canExecute: true,
              },
            ],
          },
        })
      }
      if (toolName === "mcp.modules.list") {
        return sendJson(200, {
          result: {
            modules: [{ module_id: "mock.module" }],
          },
        })
      }
      if (toolName === "mcp.catalogs.list") {
        return sendJson(200, {
          result: {
            catalogs: [],
          },
        })
      }
      return sendJson(200, { result: {} })
    }

    if (url.startsWith("/api/v1/chat/completions") && method === "POST") {
      stats.chatCompletions += 1
      const body = await readBody(req)
      let stream = true
      try {
        const parsed = JSON.parse(body || "{}")
        stream = parsed?.stream !== false
      } catch {
        stream = true
      }

      if (!stream) {
        return sendJson(200, {
          choices: [
            {
              message: {
                role: "assistant",
                content: "Mock non-stream response",
              },
            },
          ],
        })
      }

      res.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        vary: "origin",
      })

      const emit = (payload: unknown) =>
        res.write(`data: ${JSON.stringify(payload)}\n\n`)

      emit({ event: "run_started", data: { run_id: "run_parity", seq: 1 } })
      setTimeout(() => {
        emit({
          event: "approval_required",
          data: {
            run_id: "run_parity",
            seq: 2,
            approval_id: "approval_1",
            tool_call_id: "tool_1",
          },
        })
      }, 400)
      setTimeout(() => {
        emit({ choices: [{ delta: { content: "Mock parity response" } }] })
      }, 650)
      setTimeout(() => {
        emit({
          event: "approval_resolved",
          data: {
            run_id: "run_parity",
            seq: 3,
            approval_id: "approval_1",
          },
        })
      }, 3200)
      setTimeout(() => {
        emit({
          event: "tool_started",
          data: { run_id: "run_parity", seq: 4, tool_call_id: "tool_1" },
        })
      }, 3500)
      setTimeout(() => {
        emit({
          event: "tool_finished",
          data: { run_id: "run_parity", seq: 5, tool_call_id: "tool_1" },
        })
      }, 4200)
      setTimeout(() => {
        emit({ event: "run_complete", data: { run_id: "run_parity", seq: 6 } })
      }, 5000)
      setTimeout(() => {
        res.write("data: [DONE]\n\n")
        res.end()
      }, 5300)
      return
    }

    if (url.startsWith("/api/v1/")) {
      return sendJson(200, {})
    }

    res.writeHead(404, { "content-type": "application/json" })
    res.end(JSON.stringify({ detail: "not found" }))
  })

  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", resolve)
  )
  const addr = server.address() as AddressInfo
  return {
    server,
    baseUrl: `http://127.0.0.1:${addr.port}`,
    getStats: () => ({ ...stats }),
  }
}

const seedChatConfig = async (page: Page, serverUrl: string) => {
  await page.addInitScript(
    ({ url, model }) => {
      try {
        const cfg = {
          serverUrl: url,
          authMode: "single-user",
          apiKey: "test-key",
        }
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify(cfg)
        )
        localStorage.setItem("plasmo-storage-tldwConfig", JSON.stringify(cfg))
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        localStorage.setItem("__tldw_allow_offline", "true")
      } catch {}
      try {
        localStorage.setItem("selectedModel", model)
        localStorage.setItem("plasmo-storage-selectedModel", JSON.stringify(model))
      } catch {}
      try {
        localStorage.setItem(
          "tldw-ui-mode",
          JSON.stringify({
            state: { mode: "pro" },
            version: 0,
          })
        )
      } catch {}
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
    const { server, baseUrl, getStats } = await startLoopParityMockServer()

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
