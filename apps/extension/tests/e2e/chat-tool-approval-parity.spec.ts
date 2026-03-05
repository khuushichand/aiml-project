import { expect, test, type Page } from "@playwright/test"
import http from "node:http"
import type { AddressInfo } from "node:net"

import { launchWithExtensionOrSkip } from "./utils/real-server"
import { grantHostPermission } from "./utils/permissions"
import {
  forceConnected,
  setSelectedModel,
  waitForConnectionStore
} from "./utils/connection"

const MODEL_ID = "mock-model"
const MODEL_KEY = `tldw:${MODEL_ID}`
const FORCE_PORT_STREAM = process.env.TLDW_E2E_FORCE_PORT_STREAM === "1"

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
    models: 0,
    mcpTools: 0
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
        vary: "origin"
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
        vary: "origin"
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
          "/api/v1/mcp/tools/execute": {}
        }
      })
    }

    if (url.startsWith("/api/v1/llm/models/metadata") && method === "GET") {
      return sendJson(200, [
        {
          id: MODEL_ID,
          name: "Mock Model",
          provider: "mock",
          context_length: 8192,
          capabilities: ["chat", "tools"]
        }
      ])
    }

    if (url === "/api/v1/llm/models" && method === "GET") {
      stats.models += 1
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
      stats.mcpTools += 1
      return sendJson(200, [
        {
          name: "mock_tool",
          description: "Mock tool for parity tests",
          canExecute: true
        }
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
                canExecute: true
              }
            ]
          }
        })
      }
      if (toolName === "mcp.modules.list") {
        return sendJson(200, {
          result: {
            modules: [{ module_id: "mock.module" }]
          }
        })
      }
      if (toolName === "mcp.catalogs.list") {
        return sendJson(200, { result: { catalogs: [] } })
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
          choices: [{ message: { role: "assistant", content: "Mock reply" } }]
        })
      }

      res.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
        "access-control-allow-origin": requestOrigin,
        "access-control-allow-credentials": "true",
        vary: "origin"
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
            tool_call_id: "tool_1"
          }
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
            approval_id: "approval_1"
          }
        })
      }, 3200)
      setTimeout(() => {
        emit({
          event: "tool_started",
          data: { run_id: "run_parity", seq: 4, tool_call_id: "tool_1" }
        })
      }, 3500)
      setTimeout(() => {
        emit({
          event: "tool_finished",
          data: { run_id: "run_parity", seq: 5, tool_call_id: "tool_1" }
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

    return sendJson(404, { detail: "not found" })
  })

  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", resolve)
  )
  const addr = server.address() as AddressInfo
  return {
    server,
    baseUrl: `http://127.0.0.1:${addr.port}`,
    getStats: () => ({ ...stats })
  }
}

const ensureChatInput = async (page: Page) => {
  const startButton = page.getByRole("button", { name: /Start chatting/i })
  if ((await startButton.count()) > 0) {
    await startButton.first().click()
  }

  let input = page.getByTestId("chat-input")
  if ((await input.count()) === 0) {
    input = page.getByPlaceholder(/Type a message/i)
  }
  await expect(input).toBeVisible({ timeout: 15000 })
  await expect(input).toBeEditable({ timeout: 15000 })
  return input
}

const openMoreToolsMenu = async (page: Page) => {
  const toolRunRow = page.getByText(/Tool run:/i).first()
  if (await toolRunRow.isVisible({ timeout: 1_500 }).catch(() => false)) {
    return
  }

  const controlMenu = page.getByTestId("control-more-menu").first()
  if (await controlMenu.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await controlMenu.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const mcpButton = page
    .getByRole("button", { name: /mcp tools/i })
    .first()
  if (await mcpButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await mcpButton.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  const moreToolsButton = page
    .getByRole("button", { name: /\+tools|more tools/i })
    .first()
  if (await moreToolsButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await moreToolsButton.click({ force: true })
    if (await toolRunRow.isVisible({ timeout: 3_000 }).catch(() => false)) return
  }

  throw new Error("Unable to open tool controls menu")
}

const ensureToolChoiceAuto = async (page: Page) => {
  const setViaStore = await page
    .evaluate(() => {
      const store = (window as any).__tldw_useStoreMessageOption
      if (!store?.setState) return false
      store.setState({ toolChoice: "auto" })
      return true
    })
    .catch(() => false)
  if (setViaStore) {
    return
  }

  await openMoreToolsMenu(page)
  const autoChoice = page.getByRole("radio", { name: /^auto$/i }).first()
  if (await autoChoice.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await autoChoice.click()
  }
  await page.keyboard.press("Escape")
}

const ensureSidepanelSelectedModel = async (page: Page, modelKey: string) => {
  const setViaStore = await page
    .evaluate((selectedModel) => {
      const store = (window as any).__tldw_useStoreMessageOption
      if (!store?.setState) return false
      store.setState({ selectedModel })
      return true
    }, modelKey)
    .catch(() => false)
  if (!setViaStore) return false
  return page
    .evaluate(() => {
      const store = (window as any).__tldw_useStoreMessageOption
      return String(store?.getState?.()?.selectedModel || "").trim().length > 0
    })
    .catch(() => false)
}

const readToolRunStatus = async (page: Page): Promise<string> => {
  const rows = page.getByText(/Tool run:/i)
  const count = await rows.count()
  for (let i = 0; i < count; i++) {
    const row = rows.nth(i)
    if (await row.isVisible()) {
      return (await row.textContent()) || ""
    }
  }
  return ""
}

const enableStreamDebugCapture = async (page: Page) => {
  await page
    .evaluate(async () => {
      const win = window as any
      const runtime = win?.browser?.runtime
      if (!runtime?.onMessage?.addListener || !runtime?.sendMessage) {
        win.__tldwStreamDebugLogs = []
        return false
      }
      const logs: Array<Record<string, unknown>> = []
      const listener = (message: any) => {
        if (message?.type === "tldw:stream-debug") {
          logs.push(message.payload || {})
        }
      }
      win.__tldwStreamDebugLogs = logs
      win.__tldwStreamDebugListener = listener
      runtime.onMessage.addListener(listener)
      Promise.race([
        runtime.sendMessage({ type: "tldw:debug", enable: true }),
        new Promise((resolve) => setTimeout(resolve, 500))
      ]).catch(() => null)
      return true
    })
    .catch(() => false)
}

const readStreamDebugCapture = async (page: Page) => {
  return page
    .evaluate(async () => {
      const win = window as any
      const readArea = async (
        area: chrome.storage.StorageArea | undefined,
        key: string
      ) => {
        if (!area?.get) return null
        return await new Promise<unknown>((resolve) => {
          try {
            area.get(key, (items) => resolve((items as Record<string, unknown>)?.[key]))
          } catch {
            resolve(null)
          }
        })
      }
      const syncConfig = await readArea(win?.chrome?.storage?.sync, "tldwConfig")
      const localConfig = await readArea(win?.chrome?.storage?.local, "tldwConfig")
      const lastRequestError = await readArea(
        win?.chrome?.storage?.local,
        "__tldwLastRequestError"
      )
      const storeState = win.__tldw_useStoreMessageOption?.getState?.() || null
      return {
        logs: Array.isArray(win.__tldwStreamDebugLogs)
          ? win.__tldwStreamDebugLogs.slice(-30)
          : [],
        chatLoopState:
          win.__tldw_useStoreMessageOption?.getState?.()?.chatLoopState || null,
        storeSnapshot: storeState
          ? {
              selectedModel: storeState.selectedModel ?? null,
              toolChoice: storeState.toolChoice ?? null,
              temporaryChat: storeState.temporaryChat ?? null,
              messagesLength: Array.isArray(storeState.messages)
                ? storeState.messages.length
                : null,
              lastMessagePreview:
                Array.isArray(storeState.messages) && storeState.messages.length > 0
                  ? String(
                      storeState.messages[storeState.messages.length - 1]?.message ||
                        ""
                    ).slice(0, 240)
                  : null
            }
          : null,
        syncConfig,
        localConfig,
        lastRequestError
      }
    })
    .catch(() => ({ logs: [], chatLoopState: null }))
}

test.describe("Chat tool approval parity", () => {
  test("shows pending, running, then done in sidepanel chat", async () => {
    test.setTimeout(120000)
    const { server, baseUrl, getStats } = await startLoopParityMockServer()

    const {
      context,
      page,
      openSidepanel,
      extensionId
    } = await launchWithExtensionOrSkip(test, "", {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true,
        tldwConfig: {
          serverUrl: baseUrl,
          authMode: "single-user",
          apiKey: "test-key"
        }
      },
      seedLocalStorage: {
        "tldw-ui-mode": {
          state: { mode: "pro" },
          version: 0
        }
      }
    })

    try {
      const origin = new URL(baseUrl).origin + "/*"
      const granted = await grantHostPermission(context, extensionId, origin)
      test.skip(
        !granted,
        "Host permission not granted; allow it in chrome://extensions > tldw Assistant > Site access, then re-run."
      )

      await setSelectedModel(page, MODEL_KEY)

      const sidepanel = await openSidepanel()
      await waitForConnectionStore(sidepanel, "chat-tool-approval-parity")
      await forceConnected(
        sidepanel,
        { serverUrl: baseUrl },
        "chat-tool-approval-parity:connected"
      )

      const input = await ensureChatInput(sidepanel)
      await ensureSidepanelSelectedModel(sidepanel, MODEL_KEY)
      await ensureToolChoiceAuto(sidepanel)
      await enableStreamDebugCapture(sidepanel)
      if (!FORCE_PORT_STREAM) {
        await sidepanel
          .evaluate(() => {
            const maybeBrowser = (window as any).browser
            if (maybeBrowser?.runtime?.connect) {
              try {
                ;(maybeBrowser.runtime as any).__tldwOriginalConnect =
                  maybeBrowser.runtime.connect
                maybeBrowser.runtime.connect = undefined
              } catch {
                // best-effort: fallback to extension stream port if not writable
              }
            }
          })
          .catch(() => {})
      }
      await sidepanel
        .evaluate(() => {
          const store = (window as any).__tldw_useStoreMessageOption
          store?.setState?.({ temporaryChat: true })
        })
        .catch(() => {})
      await input.fill(`Tool loop parity ${Date.now()}`)

      const sendButton = sidepanel.locator('[data-testid="chat-send"]')
      if ((await sendButton.count()) > 0) {
        await expect(sendButton).toBeEnabled({ timeout: 15_000 })
        await sendButton.click()
      } else {
        await input.press("Enter")
      }

      try {
        await expect
          .poll(
            async () => {
              await openMoreToolsMenu(sidepanel)
              return readToolRunStatus(sidepanel)
            },
            { timeout: 7_000 }
          )
          .toMatch(/pending approval/i)
        await expect
          .poll(
            async () => {
              await openMoreToolsMenu(sidepanel)
              return readToolRunStatus(sidepanel)
            },
            { timeout: 9_000 }
          )
          .toMatch(/running/i)
        await expect
          .poll(
            async () => {
              await openMoreToolsMenu(sidepanel)
              return readToolRunStatus(sidepanel)
            },
            { timeout: 12_000 }
          )
          .toMatch(/done/i)
        expect(getStats().chatCompletions).toBeGreaterThan(0)
      } catch (error) {
        const debug = await readStreamDebugCapture(sidepanel)
        throw new Error(
          [
            error instanceof Error ? error.message : String(error),
            `FORCE_PORT_STREAM=${String(FORCE_PORT_STREAM)}`,
            `stream-debug=${JSON.stringify(debug)}`,
            `server-stats=${JSON.stringify(getStats())}`
          ].join("\n")
        )
      }
    } finally {
      await context.close()
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  })
})
