import { expect, test } from "@playwright/test"

import { launchWithBuiltExtension } from "./utils/extension-build"

const installCompanionApiMock = async (
  context: Awaited<ReturnType<typeof launchWithBuiltExtension>>["context"]
) => {
  await context.addInitScript(() => {
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
      const activityItems: any[] = []
      let checkInCounter = 0

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

        if (method === "GET" && path.startsWith("/api/v1/companion/activity")) {
          return {
            ok: true,
            status: 200,
            data: {
              items: [...activityItems],
              total: activityItems.length,
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
              items: [],
              total: 0
            }
          }
        }

        if (method === "GET" && path.startsWith("/api/v1/notifications")) {
          return {
            ok: true,
            status: 200,
            data: {
              items: [],
              total: 0
            }
          }
        }

        if (method === "POST" && path === "/api/v1/companion/activity") {
          const body = payload.body || {}
          activityItems.unshift({
            id: "activity-1",
            event_type: body.event_type,
            source_type: body.source_type,
            source_id: body.source_id,
            surface: body.surface,
            tags: Array.isArray(body.tags) ? body.tags : [],
            provenance: body.provenance || {},
            metadata: body.metadata || {},
            created_at: "2026-03-10T12:00:00Z"
          })
          return {
            ok: true,
            status: 201,
            data: activityItems[0]
          }
        }

        if (method === "POST" && path === "/api/v1/companion/check-ins") {
          const body = payload.body || {}
          checkInCounter += 1
          activityItems.unshift({
            id: `activity-checkin-${checkInCounter}`,
            event_type: "companion_check_in_recorded",
            source_type: "companion_check_in",
            source_id: `checkin-${checkInCounter}`,
            surface: "companion.workspace",
            tags: Array.isArray(body.tags) ? body.tags : [],
            provenance: {
              capture_mode: "explicit",
              route: "/api/v1/companion/check-ins",
              action: "manual_check_in"
            },
            metadata: {
              title: body.title || null,
              summary: body.summary || null
            },
            created_at: "2026-03-10T12:30:00Z"
          })
          return {
            ok: true,
            status: 201,
            data: activityItems[0]
          }
        }

        return {
          ok: false,
          status: 404,
          error: `Unhandled request ${method} ${path}`
        }
      }

      ;(window as any).__emitCompanionCapture = (message: any) => {
        for (const listener of [...listeners]) {
          try {
            listener(message, {}, () => undefined)
          } catch {
            // best-effort test emitter
          }
        }
      }

      ;(window as any).__restoreCompanionPatch = () => {
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
  })
}

test.describe("Extension companion capture", () => {
  test("routes a background companion capture into sidepanel activity", async () => {
    const { context, openSidepanel } = await launchWithBuiltExtension({
      allowOffline: true,
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true
      }
    })

    await installCompanionApiMock(context)

    const sidepanel = await openSidepanel()

    try {
      await sidepanel.waitForFunction(
        () =>
          typeof (window as any).__emitCompanionCapture === "function" &&
          typeof (window as any).__tldwNavigate === "function"
      )

      await sidepanel.evaluate(() => {
        ;(window as any).__emitCompanionCapture({
          from: "background",
          type: "save-to-companion",
          text: "Remember this paragraph.",
          payload: {
            captureId: "capture-1",
            selectionText: "Remember this paragraph.",
            pageUrl: "https://example.com/article",
            pageTitle: "Example article",
            action: "save_selection"
          }
        })
      })

      await expect(sidepanel.getByTestId("sidepanel-companion-root")).toBeVisible()
      await expect(
        sidepanel.getByText("Saved selection to companion.", { exact: false })
      ).toBeVisible()
      await expect(
        sidepanel.getByRole("heading", { name: "Extension Selection Saved" })
      ).toBeVisible()
      await expect(
        sidepanel.getByText("browser_selection #capture-1", { exact: false })
      ).toBeVisible()
    } finally {
      try {
        await sidepanel.evaluate(() => {
          ;(window as any).__restoreCompanionPatch?.()
        })
      } catch {
        // ignore cleanup failures if page already closed
      }
      await context.close()
    }
  })

  test("records a manual check-in from the sidepanel companion workspace", async () => {
    const { context, openSidepanel } = await launchWithBuiltExtension({
      allowOffline: true,
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true
      }
    })

    await installCompanionApiMock(context)

    const sidepanel = await openSidepanel()

    try {
      await sidepanel.waitForFunction(
        () => typeof (window as any).__tldwNavigate === "function"
      )
      await sidepanel.evaluate(() => {
        ;(window as any).__tldwNavigate?.("/companion")
      })
      await expect(sidepanel.getByTestId("sidepanel-companion-root")).toBeVisible()
      await sidepanel.getByLabel("Check-in title").fill("Morning reset")
      await sidepanel
        .getByLabel("Summary")
        .fill("Re-focused on the companion capture backlog before lunch.")
      await sidepanel.getByLabel("Tags").fill("planning, focus")
      await sidepanel.getByRole("button", { name: "Save check-in" }).click()

      await expect(
        sidepanel.getByRole("heading", { name: "Morning reset" })
      ).toBeVisible()
      await expect(
        sidepanel.getByText("companion_check_in #checkin-1", { exact: false })
      ).toBeVisible()
    } finally {
      try {
        await sidepanel.evaluate(() => {
          ;(window as any).__restoreCompanionPatch?.()
        })
      } catch {
        // ignore cleanup failures if page already closed
      }
      await context.close()
    }
  })
})
