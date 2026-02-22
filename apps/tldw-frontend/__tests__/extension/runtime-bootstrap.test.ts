import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  HEADER_SHORTCUT_SELECTION_SETTING
} from "@/services/settings/ui-settings"

type GlobalWithExtensionRuntime = typeof globalThis & {
  browser?: Record<string, unknown>
  chrome?: Record<string, unknown>
}

const chromeDescriptor = Object.getOwnPropertyDescriptor(globalThis, "chrome")
const browserDescriptor = Object.getOwnPropertyDescriptor(globalThis, "browser")

const setGlobal = (key: "chrome" | "browser", value: unknown) => {
  Object.defineProperty(globalThis, key, {
    value,
    writable: true,
    configurable: true
  })
}

const restoreGlobal = (
  key: "chrome" | "browser",
  descriptor?: PropertyDescriptor
) => {
  if (descriptor) {
    Object.defineProperty(globalThis, key, descriptor)
    return
  }
  // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
  delete (globalThis as Record<string, unknown>)[key]
}

describe("runtime-bootstrap chrome shim", () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  afterEach(() => {
    restoreGlobal("chrome", chromeDescriptor)
    restoreGlobal("browser", browserDescriptor)
    localStorage.clear()
  })

  it("creates browser/chrome shims when globals are absent", async () => {
    restoreGlobal("chrome", undefined)
    restoreGlobal("browser", undefined)

    await import("@web/extension/shims/runtime-bootstrap")

    const globalScope = globalThis as GlobalWithExtensionRuntime
    expect(typeof globalScope.browser?.storage).toBe("object")
    expect(typeof globalScope.chrome?.storage).toBe("object")
    expect(typeof globalScope.chrome?.runtime).toBe("object")
    expect(typeof globalScope.chrome?.storage?.local).toBe("object")
  })

  it("augments pre-existing chrome objects with missing extension APIs", async () => {
    const existingChromeGet = vi.fn()
    setGlobal("chrome", {
      app: { isInstalled: true },
      storage: {
        local: {
          get: existingChromeGet
        }
      }
    })
    restoreGlobal("browser", undefined)

    await import("@web/extension/shims/runtime-bootstrap")

    const globalScope = globalThis as GlobalWithExtensionRuntime
    const chromeGlobal = globalScope.chrome

    expect(chromeGlobal?.app).toEqual({ isInstalled: true })
    expect(chromeGlobal?.storage?.local?.get).toBe(existingChromeGet)
    expect(typeof chromeGlobal?.storage?.local?.set).toBe("function")
    expect(typeof chromeGlobal?.runtime?.getURL).toBe("function")
    expect(typeof globalScope.browser?.storage?.local?.get).toBe("function")
  })

  it("backfills document workspace into persisted web header shortcuts", async () => {
    localStorage.setItem(
      HEADER_SHORTCUT_SELECTION_SETTING.key,
      JSON.stringify(["chat", "media"])
    )

    await import("@web/extension/shims/runtime-bootstrap")

    const nextRaw = localStorage.getItem(HEADER_SHORTCUT_SELECTION_SETTING.key)
    expect(nextRaw).toBeTruthy()
    const nextSelection = JSON.parse(String(nextRaw))
    expect(Array.isArray(nextSelection)).toBe(true)
    expect(nextSelection).toContain("chat")
    expect(nextSelection).toContain("media")
    expect(nextSelection).toContain("document-workspace")
    expect(
      localStorage.getItem(
        "tldw:web-defaults:header-shortcuts-document-workspace:v1"
      )
    ).toBe("true")
  })
})
