import React from "react"
import { act, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { RouteShell } from "../app-route"
import type { RouteDefinition } from "../route-registry"

type RuntimeListener = (
  message: {
    from?: string
    type?: string
    text?: string
    payload?: unknown
  }
) => void

const runtimeListeners = new Set<RuntimeListener>()

vi.mock("~/hooks/useDarkmode", () => ({
  useDarkMode: () => ({ mode: "light" })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    i18n: {
      language: "en",
      resolvedLanguage: "en"
    }
  })
}))

vi.mock("@/components/Common/PageAssistLoader", () => ({
  PageAssistLoader: () => <div data-testid="route-loader">Loading</div>
}))

vi.mock("@/hooks/useAutoButtonTitles", () => ({
  useAutoButtonTitles: () => {}
}))

vi.mock("@/i18n", () => ({
  ensureI18nNamespaces: vi.fn().mockResolvedValue(undefined)
}))

vi.mock("@/utils/ui-diagnostics", () => ({
  registerUiDiagnostics: vi.fn()
}))

vi.mock("@/store/layout-ui", () => ({
  useLayoutUiStore: (selector: (state: { setChatSidebarCollapsed: () => void }) => unknown) =>
    selector({ setChatSidebarCollapsed: () => {} })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: null,
    loading: false
  })
}))

vi.mock("@/config/platform", () => ({
  platformConfig: { target: "browser" }
}))

vi.mock("@/routes/route-capabilities", () => ({
  isRouteEnabledForCapabilities: () => true
}))

vi.mock("@/services/settings/registry", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/services/settings/registry")>()
  return {
    ...actual,
    setSetting: vi.fn().mockResolvedValue(undefined)
  }
})

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

const ROUTES: Record<"options" | "sidepanel", RouteDefinition[]> = {
  options: [
    {
      kind: "options",
      path: "/",
      element: <div data-testid="home-route">Home</div>
    }
  ],
  sidepanel: [
    {
      kind: "sidepanel",
      path: "/chat",
      element: <div data-testid="sidepanel-chat">Chat</div>
    },
    {
      kind: "sidepanel",
      path: "/companion",
      element: <div data-testid="companion-home-shell">Companion Home</div>
    }
  ]
}

const renderRouteShell = (kind: "options" | "sidepanel", path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="*"
          element={<RouteShell kind={kind} routes={ROUTES[kind]} />}
        />
      </Routes>
    </MemoryRouter>
  )

describe("RouteShell companion capture routing", () => {
  beforeEach(() => {
    runtimeListeners.clear()
    window.sessionStorage.clear()

    Object.defineProperty(globalThis, "browser", {
      configurable: true,
      value: {
        runtime: {
          onMessage: {
            addListener: vi.fn((listener: RuntimeListener) => {
              runtimeListeners.add(listener)
            }),
            removeListener: vi.fn((listener: RuntimeListener) => {
              runtimeListeners.delete(listener)
            })
          }
        }
      }
    })
  })

  afterEach(() => {
    Reflect.deleteProperty(globalThis, "browser")
  })

  it("stores pending companion capture and navigates to the companion route", async () => {
    renderRouteShell("sidepanel", "/chat")

    await waitFor(() => {
      expect(screen.getByTestId("sidepanel-chat")).toBeVisible()
    })
    expect(runtimeListeners.size).toBeGreaterThan(0)

    act(() => {
      for (const listener of runtimeListeners) {
        listener({
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
      }
    })

    await waitFor(() => {
      expect(screen.getByTestId("companion-home-shell")).toBeVisible()
    })

    const stored = window.sessionStorage.getItem("tldw:companion:pendingCapture")
    expect(stored).not.toBeNull()
    expect(JSON.parse(String(stored))).toMatchObject({
      id: "capture-1",
      selectionText: "Remember this paragraph.",
      pageUrl: "https://example.com/article",
      pageTitle: "Example article",
      action: "save_selection"
    })
  })
})
