import { expect, test, type Page } from "@playwright/test"

import { launchWithBuiltExtensionOrSkip } from "./utils/real-server"

const SEED_CONFIG = {
  __tldw_first_run_complete: true,
  tldwConfig: {
    serverUrl: "http://127.0.0.1:8000",
    authMode: "single-user" as const,
    apiKey: "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"
  },
  quickIngestInspectorIntroDismissed: true,
  quickIngestOnboardingDismissed: true,
  tldw_skip_landing_hub: true,
  "tldw:workflow:landing-config": {
    showOnFirstRun: true,
    dismissedAt: Date.now(),
    completedWorkflows: []
  }
}

type RuntimeProbe = {
  href: string
  hash: string
  readyState: string
  rootChildren: number
  hasConnectionStore: boolean
  localConfig: unknown
  syncConfig: unknown
  callbackPing: unknown
  promisePing: unknown
  bodyText: string
}

type WorkerProbe = {
  url: string | null
  runtimeId: string | null
  hasChromeOnMessageListeners: boolean
  listenerAdded: boolean
  selfPing: unknown
}

const normalizeMaybeSerializedObject = (value: unknown) => {
  if (typeof value !== "string") return value
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

const inspectRuntime = async (page: Page): Promise<RuntimeProbe> => {
  return await page.evaluate(async () => {
    const readArea = async (
      area: typeof chrome.storage.local | typeof chrome.storage.sync,
      key: string
    ) =>
      await new Promise<unknown>((resolve) => {
        try {
          area.get(key, (items) => resolve(items?.[key] ?? null))
        } catch {
          resolve(null)
        }
      })

    const callbackPing = async () =>
      await new Promise<unknown>((resolve) => {
        try {
          const timeoutId = setTimeout(
            () => resolve({ ok: false, error: "timeout" }),
            3000
          )
          chrome.runtime.sendMessage({ type: "tldw:ping" }, (response) => {
            clearTimeout(timeoutId)
            if (chrome.runtime.lastError) {
              resolve({
                ok: false,
                error: chrome.runtime.lastError.message || "lastError"
              })
              return
            }
            resolve(response || { ok: false, error: "no response" })
          })
        } catch (error) {
          resolve({ ok: false, error: String(error) })
        }
      })

    const promisePing = async () => {
      try {
        const runtime = (globalThis as any).browser?.runtime || chrome.runtime
        return await Promise.race([
          runtime.sendMessage({ type: "tldw:ping", _mode: "promise" }),
          new Promise((resolve) =>
            setTimeout(
              () => resolve({ ok: false, error: "promise-timeout" }),
              3000
            )
          )
        ])
      } catch (error) {
        return { ok: false, error: String(error) }
      }
    }

    return {
      href: window.location.href,
      hash: window.location.hash,
      readyState: document.readyState,
      rootChildren: document.querySelector("#root")?.children.length || 0,
      hasConnectionStore: Boolean(
        (window as any).__tldw_useConnectionStore?.getState
      ),
      localConfig: await readArea(chrome.storage.local, "tldwConfig"),
      syncConfig: await readArea(chrome.storage.sync, "tldwConfig"),
      callbackPing: await callbackPing(),
      promisePing: await promisePing(),
      bodyText: (document.body?.innerText || "").slice(0, 400)
    }
  })
}

test.describe("Built extension runtime", () => {
  test("keeps seeded config and a working background message bus across options and sidepanel chat", async () => {
    test.setTimeout(90000)

    const { context, page, openSidepanel } =
      await launchWithBuiltExtensionOrSkip(test, {
        seedConfig: SEED_CONFIG
      })

    try {
      const sw =
        context.serviceWorkers()[0] ??
        (await context.waitForEvent("serviceworker", { timeout: 15000 }))

      const workerProbe = await sw.evaluate(async () => {
        const w = globalThis as any
        const runtime = w.chrome?.runtime
        const addTestListener = () => {
          if (!runtime?.onMessage?.addListener) return false
          runtime.onMessage.addListener(
            (message: any, _sender: any, sendResponse: any) => {
              if (message?.type !== "e2e:test-listener") return false
              sendResponse({
                ok: true,
                source: "e2e:test-listener",
                timestamp: Date.now()
              })
              return true
            }
          )
          return true
        }

        const listenerAdded = addTestListener()

        const selfPing = await new Promise<unknown>((resolve) => {
          if (!runtime?.sendMessage) {
            resolve({ ok: false, error: "no-runtime-sendMessage" })
            return
          }
          const timeoutId = setTimeout(
            () => resolve({ ok: false, error: "self-timeout" }),
            3000
          )
          try {
            runtime.sendMessage({ type: "e2e:test-listener" }, (response: any) => {
              clearTimeout(timeoutId)
              if (runtime.lastError) {
                resolve({
                  ok: false,
                  error: runtime.lastError.message || "lastError"
                })
                return
              }
              resolve(response || { ok: false, error: "no-response" })
            })
          } catch (error) {
            clearTimeout(timeoutId)
            resolve({ ok: false, error: String(error) })
          }
        })

        return {
          url: typeof location?.href === "string" ? location.href : null,
          runtimeId: runtime?.id ?? null,
          hasChromeOnMessageListeners: Boolean(
            runtime?.onMessage?.hasListeners?.()
          ),
          listenerAdded,
          selfPing
        }
      })

      await page.waitForTimeout(1500)
      const optionsProbe = await inspectRuntime(page)
      const optionsTestListenerProbe = await page.evaluate(async () => {
        return await new Promise<unknown>((resolve) => {
          const timeoutId = setTimeout(
            () => resolve({ ok: false, error: "timeout" }),
            3000
          )
          try {
            chrome.runtime.sendMessage({ type: "e2e:test-listener" }, (response) => {
              clearTimeout(timeoutId)
              if (chrome.runtime.lastError) {
                resolve({
                  ok: false,
                  error: chrome.runtime.lastError.message || "lastError"
                })
                return
              }
              resolve(response || { ok: false, error: "no-response" })
            })
          } catch (error) {
            clearTimeout(timeoutId)
            resolve({ ok: false, error: String(error) })
          }
        })
      })

      const sidepanel = await openSidepanel("/chat")
      await sidepanel.waitForTimeout(3000)
      const sidepanelProbe = await inspectRuntime(sidepanel)
      const sidepanelTestListenerProbe = await sidepanel.evaluate(async () => {
        return await new Promise<unknown>((resolve) => {
          const timeoutId = setTimeout(
            () => resolve({ ok: false, error: "timeout" }),
            3000
          )
          try {
            chrome.runtime.sendMessage({ type: "e2e:test-listener" }, (response) => {
              clearTimeout(timeoutId)
              if (chrome.runtime.lastError) {
                resolve({
                  ok: false,
                  error: chrome.runtime.lastError.message || "lastError"
                })
                return
              }
              resolve(response || { ok: false, error: "no-response" })
            })
          } catch (error) {
            clearTimeout(timeoutId)
            resolve({ ok: false, error: String(error) })
          }
        })
      })
      const normalizedOptionsLocalConfig = normalizeMaybeSerializedObject(
        optionsProbe.localConfig
      )
      const normalizedOptionsSyncConfig = normalizeMaybeSerializedObject(
        optionsProbe.syncConfig
      )
      const normalizedSidepanelLocalConfig = normalizeMaybeSerializedObject(
        sidepanelProbe.localConfig
      )
      const normalizedSidepanelSyncConfig = normalizeMaybeSerializedObject(
        sidepanelProbe.syncConfig
      )

      console.log(
        "[built-extension-runtime] worker",
        JSON.stringify(workerProbe, null, 2)
      )
      console.log(
        "[built-extension-runtime] options",
        JSON.stringify(optionsProbe, null, 2)
      )
      console.log(
        "[built-extension-runtime] options test-listener",
        JSON.stringify(optionsTestListenerProbe, null, 2)
      )
      console.log(
        "[built-extension-runtime] sidepanel",
        JSON.stringify(sidepanelProbe, null, 2)
      )
      console.log(
        "[built-extension-runtime] sidepanel test-listener",
        JSON.stringify(sidepanelTestListenerProbe, null, 2)
      )

      expect(normalizedOptionsLocalConfig).toMatchObject({
        serverUrl: "http://127.0.0.1:8000"
      })
      expect(normalizedOptionsSyncConfig).toMatchObject({
        serverUrl: "http://127.0.0.1:8000"
      })
      expect(normalizedSidepanelLocalConfig).toMatchObject({
        serverUrl: "http://127.0.0.1:8000"
      })
      expect(normalizedSidepanelSyncConfig).toMatchObject({
        serverUrl: "http://127.0.0.1:8000"
      })

      expect(optionsProbe.rootChildren).toBeGreaterThan(0)
      expect(sidepanelProbe.rootChildren).toBeGreaterThan(0)
      expect(sidepanelProbe.hasConnectionStore).toBe(true)
      expect(sidepanelProbe.hash).toContain("/chat")
      expect(sidepanelProbe.bodyText).toMatch(/chat|assistant|server/i)

      expect(workerProbe.runtimeId).toBeTruthy()
      expect(workerProbe.hasChromeOnMessageListeners).toBe(true)
      expect(workerProbe.selfPing).toMatchObject({ ok: true })
      expect(optionsTestListenerProbe).toMatchObject({ ok: true })
      expect(sidepanelTestListenerProbe).toMatchObject({ ok: true })

      expect(optionsProbe.callbackPing).toMatchObject({ ok: true })
      expect(optionsProbe.promisePing).toMatchObject({ ok: true })
      expect(sidepanelProbe.callbackPing).toMatchObject({ ok: true })
      expect(sidepanelProbe.promisePing).toMatchObject({ ok: true })
    } finally {
      await context.close()
    }
  })
})
