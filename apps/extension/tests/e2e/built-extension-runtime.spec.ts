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
  bodyText: string
}

type WorkerProbe = {
  url: string | null
  runtimeId: string | null
  diagnostics: unknown
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
      bodyText: (document.body?.innerText || "").slice(0, 400)
    }
  })
}

const waitForRuntimeSurface = async (page: Page): Promise<RuntimeProbe> => {
  await expect
    .poll(async () => (await inspectRuntime(page)).rootChildren, {
      timeout: 15_000
    })
    .toBeGreaterThan(0)

  return await inspectRuntime(page)
}

test.describe("Built extension runtime", () => {
  test("keeps seeded config and renders packaged options plus sidepanel chat", async () => {
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
        return {
          url: typeof location?.href === "string" ? location.href : null,
          runtimeId: runtime?.id ?? null,
          diagnostics:
            typeof w.__tldwBackgroundDiagnostics === "function"
              ? w.__tldwBackgroundDiagnostics()
              : null
        }
      })

      const optionsProbe = await waitForRuntimeSurface(page)
      const sidepanel = await openSidepanel("/chat")
      const sidepanelProbe = await waitForRuntimeSurface(sidepanel)
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
        "[built-extension-runtime] sidepanel",
        JSON.stringify(sidepanelProbe, null, 2)
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

      // Raw runtime probes executed from Playwright-evaluated worlds are not a
      // reliable oracle for packaged MV3 transport health here. This review
      // only asserts seeded config, service worker presence, and real packaged
      // options/sidepanel rendering. The real background-proxy app path is
      // covered by background-proxy-api.spec.ts.
      expect(workerProbe.runtimeId).toBeTruthy()
      expect(workerProbe.url).toContain("background")
      expect(workerProbe.diagnostics).toBeTruthy()
    } finally {
      await context.close()
    }
  })
})
