// @vitest-environment jsdom
import React, { Suspense } from "react"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const routeMocks = vi.hoisted(() => ({
  standaloneMcpHub: vi.fn(() => (
    <div data-testid="standalone-mcp-hub">Standalone MCP Hub</div>
  )),
  settingsMcpHub: vi.fn(() => (
    <div data-testid="settings-mcp-hub">Settings MCP Hub</div>
  ))
}))

vi.mock("../option-mcp-hub", () => ({
  __esModule: true,
  default: routeMocks.standaloneMcpHub
}))

vi.mock("../option-settings-mcp-hub", () => ({
  __esModule: true,
  default: routeMocks.settingsMcpHub
}))

vi.mock("../option-index", () => ({
  __esModule: true,
  default: () => <div data-testid="option-index" />
}))

vi.mock("../settings-route", () => ({
  __esModule: true,
  createSettingsRoute: () => () => <div data-testid="settings-route-stub" />,
  SettingsRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

import { ROUTE_DEFINITIONS } from "../route-registry"
import { optionSettingsRoutes } from "../option-settings-route-registry"

const renderRoute = (element: React.ReactElement, path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Suspense fallback={<div data-testid="route-fallback" />}>
        <Routes>
          <Route path="*" element={element} />
        </Routes>
      </Suspense>
    </MemoryRouter>
  )

describe("mcp hub route wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders the standalone MCP hub route from the main registry", async () => {
    const route = ROUTE_DEFINITIONS.find((candidate) => candidate.path === "/mcp-hub")

    expect(route).toBeDefined()
    renderRoute(route!.element, "/mcp-hub")

    expect(await screen.findByTestId("standalone-mcp-hub")).toBeVisible()
    expect(screen.queryByTestId("settings-mcp-hub")).not.toBeInTheDocument()
  })

  it("renders the settings MCP hub route from the main registry", async () => {
    const mainRoute = ROUTE_DEFINITIONS.find(
      (candidate) => candidate.path === "/settings/mcp-hub"
    )

    expect(mainRoute).toBeDefined()
    renderRoute(mainRoute!.element, "/settings/mcp-hub")

    expect(await screen.findByTestId("settings-mcp-hub")).toBeVisible()
    expect(routeMocks.settingsMcpHub).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId("standalone-mcp-hub")).not.toBeInTheDocument()
  })

  it("renders the settings MCP hub route from the settings registry", async () => {
    const settingsRoute = optionSettingsRoutes.find(
      (candidate) => candidate.path === "/settings/mcp-hub"
    )

    expect(settingsRoute).toBeDefined()
    renderRoute(settingsRoute!.element, "/settings/mcp-hub")

    expect(await screen.findByTestId("settings-mcp-hub")).toBeVisible()
    expect(routeMocks.settingsMcpHub).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId("standalone-mcp-hub")).not.toBeInTheDocument()
  })
})
