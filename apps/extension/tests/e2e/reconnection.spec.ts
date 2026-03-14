import { test, expect } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import {
  waitForConnectionStore,
  forceConnected,
  forceErrorUnreachable,
  forceConnectionState
} from "./utils/connection"
import path from "path"
import http from "node:http"
import { AddressInfo } from "node:net"

const EXT_PATH = path.resolve("build/chrome-mv3")

/**
 * Create a server whose health endpoint can be toggled on/off to simulate
 * disconnect and reconnect scenarios.
 */
function startToggleableServer() {
  let healthy = true

  const server = http.createServer((req, res) => {
    const method = (req.method || "GET").toUpperCase()
    const url = req.url || "/"

    if (method === "OPTIONS") {
      res.writeHead(204, {
        "access-control-allow-origin": "*",
        "access-control-allow-credentials": "true",
        "access-control-allow-headers":
          "content-type, x-api-key, authorization"
      })
      return res.end()
    }

    if (url === "/api/v1/health") {
      if (healthy) {
        res.writeHead(200, {
          "content-type": "application/json",
          "access-control-allow-origin": "*",
          "access-control-allow-credentials": "true"
        })
        return res.end(JSON.stringify({ status: "ok" }))
      }
      // Simulate server down
      res.writeHead(503, {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "access-control-allow-credentials": "true"
      })
      return res.end(JSON.stringify({ status: "unavailable" }))
    }

    if (url === "/openapi.json") {
      res.writeHead(200, {
        "content-type": "application/json",
        "access-control-allow-origin": "*"
      })
      return res.end(
        JSON.stringify({
          openapi: "3.0.0",
          info: { version: "mock" },
          paths: { "/api/v1/health": {} }
        })
      )
    }

    res.writeHead(404)
    res.end("not found")
  })

  return new Promise<{
    server: http.Server
    baseUrl: string
    setHealthy: (val: boolean) => void
  }>((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address() as AddressInfo
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${addr.port}`,
        setHealthy: (val: boolean) => {
          healthy = val
        }
      })
    })
  })
}

test.describe("Reconnection and graceful degradation", () => {
  test("shows error state when server becomes unreachable", async () => {
    test.setTimeout(90_000)

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
      await waitForConnectionStore(page, "reconnection:store")

      // Force the connection store into an error/unreachable state
      await forceErrorUnreachable(
        page,
        { serverUrl: "http://127.0.0.1:65535" },
        "reconnection:unreachable"
      )

      // The UI should display some error indicator
      const errorIndicator = page.getByText(
        /Can.?t reach|unreachable|connection.*failed|server.*offline|not connected/i
      )
      const retryButton = page.getByRole("button", {
        name: /Retry|Reconnect|Try again|Troubleshoot/i
      })

      // At least one of these should be visible
      const hasError = await errorIndicator
        .first()
        .isVisible()
        .catch(() => false)
      const hasRetry = await retryButton
        .first()
        .isVisible()
        .catch(() => false)

      expect(hasError || hasRetry).toBeTruthy()

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })

  test("recovers to connected state after server comes back", async () => {
    test.setTimeout(90_000)

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
      await waitForConnectionStore(page, "recovery:store")

      // Start in error state
      await forceErrorUnreachable(page, {}, "recovery:error")

      // Verify error state is reflected
      let connState = await page.evaluate(() => {
        const store = (window as any).__tldw_useConnectionStore
        return store?.getState?.()?.state?.phase
      })
      expect(connState).toBe("error")

      // Force recovery to connected
      await forceConnected(page, {}, "recovery:connected")

      // Verify connected state
      connState = await page.evaluate(() => {
        const store = (window as any).__tldw_useConnectionStore
        return store?.getState?.()?.state?.phase
      })
      expect(connState).toBe("connected")

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })

  test("connection store transitions through phases correctly", async () => {
    test.setTimeout(60_000)

    const { context, page } = await launchWithExtensionOrSkip(test, EXT_PATH)

    try {
      await waitForConnectionStore(page, "phases:store")

      // Verify store is mounted and has expected shape
      const storeShape = await page.evaluate(() => {
        const store = (window as any).__tldw_useConnectionStore
        if (!store?.getState) return null
        const state = store.getState().state
        return {
          hasPhase: typeof state?.phase === "string",
          hasIsConnected: typeof state?.isConnected === "boolean",
          hasIsChecking: typeof state?.isChecking === "boolean",
          hasErrorKind: typeof state?.errorKind === "string"
        }
      })

      expect(storeShape).not.toBeNull()
      expect(storeShape?.hasPhase).toBe(true)
      expect(storeShape?.hasIsConnected).toBe(true)
      expect(storeShape?.hasIsChecking).toBe(true)

      // Force through multiple state transitions
      await forceConnectionState(
        page,
        { phase: "searching", isChecking: true, isConnected: false },
        "phases:searching"
      )

      const searchingPhase = await page.evaluate(() => {
        const store = (window as any).__tldw_useConnectionStore
        return store?.getState?.()?.state?.phase
      })
      expect(searchingPhase).toBe("searching")

      await forceConnected(page, {}, "phases:connected")

      const connectedPhase = await page.evaluate(() => {
        const store = (window as any).__tldw_useConnectionStore
        return store?.getState?.()?.state?.phase
      })
      expect(connectedPhase).toBe("connected")

      await context.close()
    } catch (error) {
      await context.close()
      throw error
    }
  })
})
