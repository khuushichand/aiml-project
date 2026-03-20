import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { RouteShell } from "../app-route"

vi.mock("~/hooks/useDarkmode", () => ({
  useDarkMode: () => ({ mode: "light" })
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

vi.mock("@/routes/route-registry", () => ({
  optionRoutes: [
    { path: "/", element: <div data-testid="home-route">Home</div> },
    { path: "/research", element: <div data-testid="research-route">Research</div> },
    { path: "/knowledge", element: <div data-testid="knowledge-route">Knowledge</div> },
    { path: "/media", element: <div data-testid="media-route">Media</div> },
    { path: "/settings", element: <div data-testid="settings-route">Settings</div> }
  ],
  sidepanelRoutes: [{ path: "/chat", element: <div data-testid="sidepanel-chat">Chat</div> }]
}))

const renderRouteShell = (kind: "options" | "sidepanel", path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<RouteShell kind={kind} />} />
      </Routes>
    </MemoryRouter>
  )

describe("RouteShell unknown-route recovery", () => {
  it("renders a not-found recovery panel instead of blank content", () => {
    renderRouteShell("options", "/missing-route?foo=bar")

    expect(screen.getByRole("heading", { name: "We could not find that route" })).toBeVisible()
    expect(screen.getByTestId("not-found-recovery-panel")).toBeVisible()
    expect(screen.getByText("/missing-route?foo=bar")).toBeVisible()
    expect(screen.getByTestId("not-found-open-research")).toBeVisible()
  })

  it("supports primary recovery navigation from the fallback panel", async () => {
    const user = userEvent.setup()
    renderRouteShell("options", "/missing-route")

    await user.click(screen.getByTestId("not-found-go-chat"))
    expect(screen.getByTestId("home-route")).toBeVisible()
  })
})
