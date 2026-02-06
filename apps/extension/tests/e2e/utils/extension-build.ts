import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

import { resolveExtensionId } from './extension-id'

type LaunchOptions = {
  seedConfig?: Record<string, any>
  allowOffline?: boolean
  seedLocalStorage?: Record<string, any>
}

async function waitForStorageSeed(page: any) {
  await page.waitForFunction(
    () =>
      new Promise<boolean>((resolve) => {
        if (typeof chrome === 'undefined' || !chrome.storage?.local) {
          resolve(false)
          return
        }
        chrome.storage.local.get('__e2eSeeded', (items) => {
          resolve(Boolean(items?.__e2eSeeded))
        })
      }),
    undefined,
    { timeout: 10000 }
  )
}

function makeTempProfileDirs() {
  const root = path.resolve('tmp-playwright-profile')
  fs.mkdirSync(root, { recursive: true })
  const homeDir = fs.mkdtempSync(path.join(root, 'home-'))
  const userDataDir = fs.mkdtempSync(path.join(root, 'user-data-'))
  return { homeDir, userDataDir }
}

const projectRoot = path.resolve(__dirname, '..', '..', '..')

export async function launchWithBuiltExtension(
  { seedConfig, allowOffline, seedLocalStorage }: LaunchOptions = {}
) {
  const candidates = [
    path.resolve(projectRoot, 'build/chrome-mv3'),
    path.resolve(projectRoot, '.output/chrome-mv3')
  ]
  const extensionPath = candidates.find((p) => fs.existsSync(p))
  if (!extensionPath) {
    throw new Error(
      `No built extension found. Tried: ${candidates.join(', ')}. ` +
      `Run "npm run build:chrome" from apps/extension.`
    )
  }
  const { homeDir, userDataDir } = makeTempProfileDirs()
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !!process.env.CI,
    env: {
      ...process.env,
      HOME: homeDir
    },
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--disable-crash-reporter',
      '--crash-dumps-dir=/tmp'
    ]
  })

  // Enable E2E debug logs in extension pages.
  await context.addInitScript(() => {
    try {
      ;(globalThis as any).__tldw_e2e_debug = true
    } catch {
      // ignore flag set failures
    }
  })

  // Test-only: redirect sync storage writes to local to avoid sync quota limits.
  await context.addInitScript(() => {
    const patchStorage = (storage: any) => {
      if (!storage?.sync || !storage?.local) return
      const local = storage.local
      const sync = storage.sync
      const methods = ["get", "set", "remove", "clear", "getBytesInUse"]
      for (const method of methods) {
        if (typeof local?.[method] === "function") {
          sync[method] = local[method].bind(local)
        }
      }
    }
    try {
      if (typeof chrome !== "undefined") {
        patchStorage(chrome.storage)
      }
      if (typeof browser !== "undefined") {
        patchStorage((browser as any).storage)
      }
    } catch {
      // ignore patch failures
    }
  })

  // Seed storage before any extension pages load to bypass connection checks
  await context.addInitScript(
    (cfg, allowOfflineFlag) => {
      try {
        if (typeof chrome === 'undefined' || !chrome.storage?.local) return
        const baseSeed = {
          __tldw_first_run_complete: true,
          tldw_skip_landing_hub: true,
          quickIngestInspectorIntroDismissed: true,
          quickIngestOnboardingDismissed: true,
          "tldw:workflow:landing-config": {
            showOnFirstRun: true,
            dismissedAt: Date.now(),
            completedWorkflows: [],
          },
        }
        const seededConfig =
          cfg && typeof cfg === "object"
            ? { ...baseSeed, tldwConfig: cfg, ...cfg }
            : baseSeed
        const setLocal = (data: Record<string, any>, done?: () => void) => {
          // @ts-ignore
          const setter = chrome?.storage?.local?.set
          if (typeof setter === 'function') {
            setter(data, () => done?.())
          } else {
            done?.()
          }
        }
        const setSync = (data: Record<string, any>, done?: () => void) => {
          // @ts-ignore
          const setter = chrome?.storage?.sync?.set
          if (typeof setter === 'function') {
            setter(data, () => done?.())
          } else {
            done?.()
          }
        }
        const finalize = () => {
          setLocal({ __e2eSeeded: true })
          setSync({ __e2eSeeded: true })
        }

        chrome.storage.local.get('__e2eSeeded', (items) => {
          if (items?.__e2eSeeded) return
          let pending = 0
          const done = () => {
            pending -= 1
            if (pending <= 0) finalize()
          }

          if (allowOfflineFlag) {
            pending += 1
            setLocal({ __tldw_allow_offline: true }, done)
          }

          if (seededConfig) {
            pending += 1
            setLocal(seededConfig, done)
            pending += 1
            setSync(seededConfig, done)
          }

          if (pending === 0) finalize()
        })
      } catch {
        // ignore storage write failures in isolated contexts
      }
    },
    seedConfig || null,
    allowOffline || false
  )

  // Wait for SW/background
  const waitForTargets = async () => {
    if (context.serviceWorkers().length || context.backgroundPages().length) return
    await Promise.race([
      context.waitForEvent('serviceworker').catch(() => null),
      context.waitForEvent('backgroundpage').catch(() => null),
      new Promise((r) => setTimeout(r, 7000))
    ])
  }
  await waitForTargets()

  // Seed storage via service worker before any extension pages load.
  // This avoids a race where the options UI checks connection before storage is ready.
  const sw = context.serviceWorkers()[0]
  if (sw) {
    await sw.evaluate(() => {
      try {
        const patchStorage = (storage: any) => {
          if (!storage?.sync || !storage?.local) return
          const local = storage.local
          const sync = storage.sync
          const methods = ["get", "set", "remove", "clear", "getBytesInUse"]
          for (const method of methods) {
            if (typeof local?.[method] === "function") {
              sync[method] = local[method].bind(local)
            }
          }
        }
        if (typeof chrome !== "undefined") {
          patchStorage(chrome.storage)
        }
        if (typeof browser !== "undefined") {
          patchStorage((browser as any).storage)
        }
      } catch {
        // ignore patch failures
      }
    })

    if (seedConfig) {
      await sw.evaluate(({ cfg, allowOfflineFlag }) => {
        return new Promise<void>((resolve) => {
          const baseSeed = {
            __tldw_first_run_complete: true,
            tldw_skip_landing_hub: true,
            quickIngestInspectorIntroDismissed: true,
            quickIngestOnboardingDismissed: true,
            "tldw:workflow:landing-config": {
              showOnFirstRun: true,
              dismissedAt: Date.now(),
              completedWorkflows: [],
            },
          }
          const seededConfig =
            cfg && typeof cfg === "object"
              ? { ...baseSeed, tldwConfig: cfg, ...cfg }
              : baseSeed
          const setLocal = (data: Record<string, any>, done?: () => void) => {
            try {
              chrome.storage.local.set(data, () => done?.())
            } catch {
              done?.()
            }
          }
          const setSync = (data: Record<string, any>, done?: () => void) => {
            try {
              chrome.storage.sync.set(data, () => done?.())
            } catch {
              done?.()
            }
          }
          chrome.storage.local.clear(() => {
            chrome.storage.sync.clear(() => {
              let pending = 0
              const done = () => {
                pending -= 1
                if (pending <= 0) resolve()
              }
              if (allowOfflineFlag) {
                pending += 1
                setLocal({ __tldw_allow_offline: true }, done)
              }
              pending += 1
              setSync(seededConfig, done)
              pending += 1
              setLocal(seededConfig, done)
              pending += 1
              setSync({ __e2eSeeded: true }, done)
              pending += 1
              setLocal({ __e2eSeeded: true }, done)
            })
          })
        })
      }, { cfg: seedConfig, allowOfflineFlag: allowOffline || false })
    } else {
      await sw.evaluate(() => {
        return new Promise<void>((resolve) => {
          chrome.storage.local.clear(() => {
            chrome.storage.sync.clear(() => {
              chrome.storage.local.set({ __e2eSeeded: true }, () => {
                chrome.storage.sync.set({ __e2eSeeded: true }, () => {
                  resolve()
                })
              })
            })
          })
        })
      })
    }
  }

  // Seed localStorage for tutorials and other non-extension storage
  if (seedLocalStorage) {
    await context.addInitScript((localStorageData) => {
      if (typeof localStorage === 'undefined') return
      for (const [key, value] of Object.entries(localStorageData)) {
        localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value))
      }
    }, seedLocalStorage)
  }

  const extensionId = await resolveExtensionId(context)
  const optionsUrl = `chrome-extension://${extensionId}/options.html`
  const sidepanelUrl = `chrome-extension://${extensionId}/sidepanel.html`

  const page = await context.newPage()
  await page.goto(optionsUrl)
  await waitForStorageSeed(page)

  // When seeding config, proactively hydrate the connection store so tests do
  // not race first-run onboarding checks on initial mount.
  if (seedConfig) {
    await page
      .waitForFunction(
        () =>
          typeof (window as any).__tldw_useConnectionStore?.getState ===
          "function",
        undefined,
        { timeout: 15_000 }
      )
      .catch(() => undefined)

    await page
      .evaluate(async (cfg) => {
        const store = (window as any).__tldw_useConnectionStore
        if (!store?.getState) return
        const actions = store.getState()

        try {
          if (cfg && typeof cfg === "object" && typeof actions.setConfigPartial === "function") {
            await actions.setConfigPartial(cfg)
          }
        } catch {
          // ignore config hydration failures in test contexts
        }

        try {
          if (typeof actions.markFirstRunComplete === "function") {
            await actions.markFirstRunComplete()
          }
        } catch {
          // ignore flag write failures in test contexts
        }

        try {
          if (typeof actions.checkOnce === "function") {
            await actions.checkOnce()
          }
        } catch {
          // ignore connection check failures in test contexts
        }
      }, seedConfig)
      .catch(() => undefined)
  }

  async function openSidepanel() {
    const p = await context.newPage()
    await p.goto(sidepanelUrl)
    return p
  }

  return { context, page, openSidepanel, extensionId, optionsUrl, sidepanelUrl }
}
