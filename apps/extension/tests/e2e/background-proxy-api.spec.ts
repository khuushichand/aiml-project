import { test, expect } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import {
  waitForConnectionStore,
  forceConnected,
  setSelectedModel
} from "./utils/connection"
import { grantHostPermission } from "./utils/permissions"
import path from "path"
import http from "node:http"
import { AddressInfo } from "node:net"

const EXT_PATH = path.resolve("build/chrome-mv3")

/**
 * Start a minimal mock server that records incoming requests and returns
 * canned chat completions so we can verify the background proxy routes
 * messages correctly.
 */
function startProxyVerificationServer() {
  const receivedRequests: Array<{ url: string; method: string; body: string }> = []

  const server = http.createServer(async (req, res) => {
    const method = (req.method || "GET").toUpperCase()
    const url = req.url || "/"

    const sendJson = (code: number, payload: unknown) => {
      res.writeHead(code, {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "access-control-allow-credentials": "true"
      })
      res.end(JSON.stringify(payload))
    }

    if (method === "OPTIONS") {
      res.writeHead(204, {
        "access-control-allow-origin": "*",
        "access-control-allow-credentials": "true",
        "access-control-allow-headers":
          "content-type, x-api-key, authorization"
      })
      return res.end()
    }

    // Collect body for POST requests
    let body = ""
    if (method === "POST" || method === "PUT") {
      body = await new Promise<string>((resolve) => {
        let data = ""
        req.on("data", (chunk) => (data += chunk))
        req.on("end", () => resolve(data))
      })
    }

    receivedRequests.push({ url, method, body })

    if (url === "/api/v1/health" && method === "GET") {
      return sendJson(200, { status: "ok" })
    }

    if (url === "/api/v1/llm/models/metadata" && method === "GET") {
      return sendJson(200, [
        {
          id: "proxy-test-model",
          name: "Proxy Test Model",
          provider: "mock",
          context_length: 4096,
          capabilities: ["chat"]
        }
      ])
    }

    if (url === "/api/v1/llm/models" && method === "GET") {
      return sendJson(200, ["proxy-test-model"])
    }

    if (url === "/openapi.json" && method === "GET") {
      return sendJson(200, {
        openapi: "3.0.0",
        info: { version: "mock" },
        paths: {
          "/api/v1/health": {},
          "/api/v1/chat/completions": {},
          "/api/v1/llm/models": {},
          "/api/v1/llm/models/metadata": {}
        }
      })
    }

    if (url === "/api/v1/chat/completions" && method === "POST") {
      // Non-streaming reply for simplicity
      return sendJson(200, {
        choices: [
          {
            message: {
              role: "assistant",
              content: "Background proxy reply"
            }
          }
        ]
      })
    }

    return sendJson(404, { detail: "not found" })
  })

  return new Promise<{
    server: http.Server
    baseUrl: string
    receivedRequests: typeof receivedRequests
  }>((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address() as AddressInfo
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${addr.port}`,
        receivedRequests
      })
    })
  })
}

test.describe("Background proxy API routing", () => {
  test("chat message routes through background service worker to backend", async () => {
    test.setTimeout(90_000)

    const { server, baseUrl, receivedRequests } =
      await startProxyVerificationServer()

    try {
      const { context, page, openSidepanel, extensionId } =
        await launchWithExtensionOrSkip(test, EXT_PATH, {
          seedConfig: {
            __tldw_first_run_complete: true,
            __tldw_allow_offline: true,
            tldwConfig: {
              serverUrl: baseUrl,
              authMode: "single-user",
              apiKey: "test-proxy-key"
            }
          }
        })

      const origin = new URL(baseUrl).origin + "/*"
      const granted = await grantHostPermission(context, extensionId, origin)
      if (!granted) {
        test.skip(true, "Host permission not granted for mock server origin.")
      }

      await setSelectedModel(page, "tldw:proxy-test-model")

      const sidepanel = await openSidepanel("/chat")
      await waitForConnectionStore(sidepanel, "proxy-api:store")
      await forceConnected(
        sidepanel,
        { serverUrl: baseUrl },
        "proxy-api:connected"
      )

      // Find or create the chat input
      const startButton = sidepanel.getByRole("button", {
        name: /Start chatting/i
      })
      if ((await startButton.count()) > 0) {
        await startButton.first().click()
      }

      let input = sidepanel.getByTestId("chat-input")
      if ((await input.count()) === 0) {
        input = sidepanel.getByPlaceholder(/Type a message/i)
      }
      await expect(input).toBeVisible({ timeout: 15_000 })

      // Send a test message
      const testMessage = `proxy-smoke-${Date.now()}`
      await input.fill(testMessage)

      const sendButton = sidepanel.locator('[data-testid="chat-send"]')
      if ((await sendButton.count()) > 0) {
        await expect(sendButton).toBeEnabled({ timeout: 15_000 })
        await sendButton.click()
      } else {
        await input.press("Enter")
      }

      // Wait for the assistant reply to appear
      const assistantMessage = sidepanel
        .locator(
          '[data-testid="chat-message"][data-role="assistant"]'
        )
        .filter({ hasText: "Background proxy reply" })
        .first()
      await expect(assistantMessage).toBeVisible({ timeout: 30_000 })

      // Verify the mock server received the chat completions request
      const chatRequests = receivedRequests.filter(
        (r) => r.url === "/api/v1/chat/completions" && r.method === "POST"
      )
      expect(chatRequests.length).toBeGreaterThanOrEqual(1)

      // Verify the request body contains our message
      const lastChatRequest = chatRequests[chatRequests.length - 1]
      expect(lastChatRequest.body).toContain(testMessage)

      await context.close()
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  })

  test("service worker is present after extension launch", async () => {
    test.setTimeout(60_000)

    const { context, page } = await launchWithExtensionOrSkip(test, EXT_PATH)

    // Verify the service worker is alive
    const sw = context.serviceWorkers()[0]
    expect(sw).toBeTruthy()

    const swUrl = sw.url()
    expect(swUrl).toContain("background")

    await context.close()
  })
})
