import { expect, test } from "@playwright/test"

import { runCompanionHomeParityContract } from "../../../test-utils/companion-home.contract"
import {
  COMPANION_HOME_PARITY_DOCS_INFO,
  COMPANION_HOME_PARITY_NOTES,
  COMPANION_HOME_PARITY_OPENAPI_SPEC,
  COMPANION_HOME_PARITY_PROFILE,
  COMPANION_HOME_PARITY_READING_LIST,
  COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT
} from "../../../test-utils/companion-home.fixtures"
import { launchWithBuiltExtensionOrSkip } from "./utils/real-server"

const DEFAULT_SERVER_CONFIG = {
  serverUrl: "http://dummy-tldw",
  apiKey: "test-key"
}

const BENIGN_PAGE_ERROR_PATTERNS = [/AbortError/i]
const BENIGN_CONSOLE_ERROR_PATTERNS = [
  /Failed to fetch models from tldw:\s+AbortError/i,
  /Failed to load resource: net::ERR_NAME_NOT_RESOLVED/i,
  /Failed to load resource: net::ERR_FILE_NOT_FOUND/i
]
const BENIGN_REQUEST_FAILURE_PATTERNS = [/ERR_NAME_NOT_RESOLVED/i, /ERR_FILE_NOT_FOUND/i]

const isBenignByPattern = (value: string, patterns: RegExp[]): boolean =>
  patterns.some((pattern) => pattern.test(value))

const isBenignRequestFailure = (url: string, errorText: string): boolean => {
  if (
    url.startsWith(DEFAULT_SERVER_CONFIG.serverUrl) &&
    isBenignByPattern(errorText, BENIGN_REQUEST_FAILURE_PATTERNS)
  ) {
    return true
  }

  if (
    url.startsWith("chrome-extension://") &&
    /\/fonts\/.+\.(ttf|woff|woff2)$/i.test(url) &&
    /ERR_FILE_NOT_FOUND/i.test(errorText)
  ) {
    return true
  }

  return false
}

const installCompanionHomeExtensionMocks = async (
  context: Awaited<ReturnType<typeof launchWithBuiltExtensionOrSkip>>["context"]
) => {
  await context.addInitScript(
    (fixture) => {
      try {
        const runtime =
          (globalThis as any)?.browser?.runtime ||
          (globalThis as any)?.chrome?.runtime
        const onMessage = runtime?.onMessage
        const originalSendMessage =
          typeof runtime?.sendMessage === "function"
            ? runtime.sendMessage.bind(runtime)
            : null
        const originalAddListener =
          typeof onMessage?.addListener === "function"
            ? onMessage.addListener.bind(onMessage)
            : null
        const originalRemoveListener =
          typeof onMessage?.removeListener === "function"
            ? onMessage.removeListener.bind(onMessage)
            : null

        if (!runtime || !onMessage || !originalSendMessage) {
          return
        }

        const listeners = new Set<
          (message: any, sender?: any, sendResponse?: any) => void
        >()

        onMessage.addListener = (listener: any) => {
          listeners.add(listener)
          return originalAddListener?.(listener)
        }
        onMessage.removeListener = (listener: any) => {
          listeners.delete(listener)
          return originalRemoveListener?.(listener)
        }

        runtime.sendMessage = async (message: any) => {
          if (message?.type !== "tldw:request") {
            return originalSendMessage(message)
          }

          const payload = message.payload || {}
          const path = String(payload.path || "")
          const method = String(payload.method || "GET").toUpperCase()

          if (method === "GET" && path.endsWith("/openapi.json")) {
            return {
              ok: true,
              status: 200,
              data: fixture.openapi
            }
          }

          if (method === "GET" && path === "/api/v1/config/docs-info") {
            return {
              ok: true,
              status: 200,
              data: fixture.docsInfo
            }
          }

          if (method === "GET" && path === "/api/v1/personalization/profile") {
            return {
              ok: true,
              status: 200,
              data: fixture.profile
            }
          }

          if (method === "GET" && path.startsWith("/api/v1/companion/activity")) {
            return {
              ok: true,
              status: 200,
              data: {
                items: fixture.workspace.activity,
                total: fixture.workspace.activityTotal,
                limit: 25,
                offset: 0
              }
            }
          }

          if (method === "GET" && path.startsWith("/api/v1/companion/knowledge")) {
            return {
              ok: true,
              status: 200,
              data: {
                items: [],
                total: 0
              }
            }
          }

          if (method === "GET" && path === "/api/v1/companion/goals") {
            return {
              ok: true,
              status: 200,
              data: {
                items: fixture.workspace.goals,
                total: fixture.workspace.goals.length
              }
            }
          }

          if (method === "GET" && path.startsWith("/api/v1/notifications")) {
            return {
              ok: true,
              status: 200,
              data: {
                items: fixture.workspace.inbox,
                total: fixture.workspace.inbox.length
              }
            }
          }

          if (method === "GET" && path.startsWith("/api/v1/reading/items")) {
            return {
              ok: true,
              status: 200,
              data: fixture.readingList
            }
          }

          if (method === "GET" && path.startsWith("/api/v1/notes/")) {
            return {
              ok: true,
              status: 200,
              data: fixture.notes
            }
          }

          return {
            ok: false,
            status: 404,
            error: `Unhandled request ${method} ${path}`
          }
        }

        ;(window as any).__restoreCompanionHomePatch = () => {
          runtime.sendMessage = originalSendMessage
          if (originalAddListener) {
            onMessage.addListener = originalAddListener
          }
          if (originalRemoveListener) {
            onMessage.removeListener = originalRemoveListener
          }
          listeners.clear()
        }
      } catch {
        // ignore init-script patch failures
      }
    },
    {
      openapi: COMPANION_HOME_PARITY_OPENAPI_SPEC,
      docsInfo: COMPANION_HOME_PARITY_DOCS_INFO,
      profile: COMPANION_HOME_PARITY_PROFILE,
      workspace: COMPANION_HOME_PARITY_WORKSPACE_SNAPSHOT,
      readingList: COMPANION_HOME_PARITY_READING_LIST,
      notes: COMPANION_HOME_PARITY_NOTES
    }
  )
}

test.describe("Companion Home parity (extension)", () => {
  test("passes baseline + deterministic home dashboard parity contract", async () => {
    const pageErrors: string[] = []
    const consoleErrors: string[] = []
    const requestFailures: string[] = []

    const { context, page, optionsUrl } = await launchWithBuiltExtensionOrSkip(test, {
      allowOffline: true,
      seedConfig: {
        __tldw_first_run_complete: true,
        tldwConfig: {
          serverUrl: DEFAULT_SERVER_CONFIG.serverUrl,
          authMode: "single-user",
          apiKey: DEFAULT_SERVER_CONFIG.apiKey
        }
      }
    })

    await installCompanionHomeExtensionMocks(context)

    page.on("pageerror", (error) => {
      if (isBenignByPattern(error.message, BENIGN_PAGE_ERROR_PATTERNS)) return
      pageErrors.push(error.message)
    })
    page.on("console", (message) => {
      if (message.type() !== "error") return
      const text = message.text()
      if (isBenignByPattern(text, BENIGN_CONSOLE_ERROR_PATTERNS)) return
      consoleErrors.push(text)
    })
    page.on("requestfailed", (request) => {
      const url = request.url()
      const errorText = request.failure()?.errorText || "request failed"
      if (isBenignRequestFailure(url, errorText)) return
      requestFailures.push(`${errorText} :: ${url}`)
    })

    try {
      await runCompanionHomeParityContract({
        platform: "extension",
        page,
        optionsUrl
      })

      expect(pageErrors).toEqual([])
      expect(consoleErrors).toEqual([])
      expect(requestFailures).toEqual([])
    } finally {
      try {
        await page.evaluate(() => {
          ;(window as any).__restoreCompanionHomePatch?.()
        })
      } catch {
        // ignore cleanup failures if page already closed
      }
      await context.close()
    }
  })
})
