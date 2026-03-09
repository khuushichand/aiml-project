import { expect, test } from "@playwright/test"
import path from "path"

import { launchWithExtensionOrSkip } from "./utils/real-server"

const seededSourcesConfig = {
  __tldw_first_run_complete: true,
  __tldw_allow_offline: true,
  tldwConfig: {
    serverUrl: "http://127.0.0.1:8000",
    authMode: "single-user",
    apiKey: "test-key"
  }
}

test.describe("Ingestion Sources options", () => {
  test("opens the full-page workspace and follows create and detail flows", async () => {
    test.setTimeout(120_000)

    const extPath = path.resolve("build/chrome-mv3")
    const { context, page: basePage, optionsUrl } = await launchWithExtensionOrSkip(
      test,
      extPath,
      {
        seedConfig: seededSourcesConfig
      }
    )

    await context.addInitScript(() => {
      const now = () => new Date().toISOString()
      let syncCalls = 0

      const sourceSummary = {
        id: 12,
        user_id: 1,
        source_type: "archive_snapshot",
        sink_type: "notes",
        policy: "canonical",
        enabled: true,
        schedule_enabled: false,
        schedule_config: {},
        config: {
          label: "Server exports"
        },
        last_sync_status: "completed",
        last_sync_completed_at: now(),
        last_successful_snapshot_id: 7,
        last_successful_sync_summary: {
          changed_count: 2,
          degraded_count: 1,
          conflict_count: 1,
          sink_failure_count: 0,
          ingestion_failure_count: 0,
          created_count: 1,
          updated_count: 1,
          deleted_count: 0,
          unchanged_count: 3
        }
      }

      const sourceDetail = {
        ...sourceSummary,
        last_error: null
      }

      const sourceItems = [
        {
          id: 501,
          source_id: 12,
          normalized_relative_path: "notes/a.md",
          sync_status: "conflict_detached"
        },
        {
          id: 502,
          source_id: 12,
          normalized_relative_path: "docs/report.pdf",
          sync_status: "degraded_ingestion_error"
        }
      ]

      const handleRequest = (payload) => {
        const method = String(payload?.method || "GET").toUpperCase()
        const path = String(payload?.path || "")
        const [pathname] = path.split("?")

        if (pathname === "/api/v1/health/live" && method === "GET") {
          return { status: "ok" }
        }

        if (pathname === "/api/v1/rag/health" && method === "GET") {
          return { components: { search_index: { status: "healthy" } } }
        }

        if (pathname === "/openapi.json" && method === "GET") {
          return {
            openapi: "3.0.0",
            info: { version: "2026.03" },
            paths: {
              "/api/v1/ingestion-sources": {},
              "/api/v1/ingestion-sources/{source_id}": {},
              "/api/v1/ingestion-sources/{source_id}/items": {},
              "/api/v1/ingestion-sources/{source_id}/sync": {}
            }
          }
        }

        if (pathname === "/api/v1/ingestion-sources" && method === "GET") {
          return {
            sources: [sourceSummary],
            total: 1
          }
        }

        if (pathname === "/api/v1/ingestion-sources/12" && method === "GET") {
          return sourceDetail
        }

        if (pathname === "/api/v1/ingestion-sources/12/items" && method === "GET") {
          return {
            items: sourceItems,
            total: sourceItems.length
          }
        }

        if (pathname === "/api/v1/ingestion-sources/12/sync" && method === "POST") {
          syncCalls += 1
          ;(window as typeof window & { __sourcesSyncCalls?: number }).__sourcesSyncCalls =
            syncCalls
          return { status: "queued" }
        }

        return {}
      }

      const patchRuntime = (runtime) => {
        if (!runtime?.sendMessage) return
        const original = runtime.sendMessage.bind(runtime)
        const handler = (message, options, callback) => {
          const cb = typeof options === "function" ? options : callback
          const respond = (payload) => {
            if (cb) {
              cb(payload)
              return undefined
            }
            return Promise.resolve(payload)
          }

          if (message?.type === "tldw:request") {
            try {
              const result = handleRequest(message.payload || {})
              return respond({ ok: true, status: 200, data: result })
            } catch (error) {
              return respond({ ok: false, status: 500, error: String(error || "") })
            }
          }

          if (original) {
            return original(message, options, callback)
          }

          return respond({ ok: true, status: 200, data: {} })
        }

        try {
          runtime.sendMessage = handler
          return
        } catch {}

        try {
          Object.defineProperty(runtime, "sendMessage", {
            value: handler,
            configurable: true,
            writable: true
          })
        } catch {}
      }

      if (window.chrome?.runtime) {
        patchRuntime(window.chrome.runtime)
      }

      if (window.browser?.runtime) {
        patchRuntime(window.browser.runtime)
      }

      ;(window as typeof window & {
        __sourcesStubbed?: boolean
        __sourcesSyncCalls?: number
      }).__sourcesStubbed = true
      ;(window as typeof window & {
        __sourcesStubbed?: boolean
        __sourcesSyncCalls?: number
      }).__sourcesSyncCalls = 0
    })

    const page = await context.newPage()
    await page.goto(`${optionsUrl}?e2e=1#/sources`, {
      waitUntil: "domcontentloaded"
    })
    await page.waitForFunction(
      () => (window as typeof window & { __sourcesStubbed?: boolean }).__sourcesStubbed === true
    )
    await basePage.close().catch(() => {})

    await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible()
    await expect(page.getByRole("button", { name: "New source" })).toBeVisible()
    await expect(page.getByText("Server exports")).toBeVisible()

    await page.getByRole("button", { name: "New source" }).click()
    await expect(page).toHaveURL(/#\/sources\/new$/)
    await expect(page.getByRole("textbox", { name: "Server directory path" })).toBeVisible()

    await page.goto(`${optionsUrl}?e2e=1#/sources`, {
      waitUntil: "domcontentloaded"
    })
    await expect(page.getByRole("button", { name: "Open detail" })).toBeVisible()

    await page.getByRole("button", { name: "Open detail" }).click()
    await expect(page).toHaveURL(/#\/sources\/12$/)
    await expect(page.getByRole("button", { name: "Sync now" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Upload archive" })).toBeVisible()
    await expect(page.getByText("notes/a.md")).toBeVisible()

    await page.getByRole("button", { name: "Sync now" }).click()
    await page.waitForFunction(
      () => (window as typeof window & { __sourcesSyncCalls?: number }).__sourcesSyncCalls === 1
    )
  })
})
