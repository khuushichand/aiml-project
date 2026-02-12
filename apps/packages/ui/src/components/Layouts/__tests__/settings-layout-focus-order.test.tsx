import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { SettingsLayout } from "../SettingsOptionLayout"

const IconStub = () => null

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (token: string, fallback?: string) => fallback ?? token
  })
}))

vi.mock("../settings-nav", () => ({
  getSettingsNavGroups: () => [
    {
      key: "server",
      titleToken: "settings:navigation.serverAndAuth",
      items: [
        {
          to: "/settings/tldw",
          labelToken: "settings:tldw.serverNav",
          icon: IconStub
        },
        {
          to: "/settings/chat",
          labelToken: "settings:chatSettingsNav",
          icon: IconStub
        }
      ]
    }
  ]
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: null,
    loading: false
  })
}))

vi.mock("@/utils/sidepanel", () => ({
  isSidepanelSupported: () => false,
  openSidepanel: vi.fn()
}))

vi.mock("@/services/settings/registry", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/settings/registry")>()
  return {
    ...actual,
    setSetting: vi.fn()
  }
})

vi.mock("@/utils/settings-return", () => ({
  getSettingsReturnTo: () => null
}))

const LocationEcho = () => {
  const location = useLocation()
  return <div data-testid="settings-layout-location">{location.pathname}</div>
}

const renderSettingsLayout = (path = "/settings/tldw") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="*"
          element={
            <SettingsLayout>
              <LocationEcho />
            </SettingsLayout>
          }
        />
      </Routes>
    </MemoryRouter>
  )

describe("settings navigation wayfinding", () => {
  it("marks the active route and exposes a current-section summary", () => {
    renderSettingsLayout("/settings/tldw")

    const activeLink = screen.getByRole("link", {
      name: "settings:tldw.serverNav"
    })
    expect(activeLink).toHaveAttribute("aria-current", "page")
    expect(screen.getByTestId("settings-current-section")).toHaveTextContent(
      "Current section"
    )
  })

  it("supports keyboard traversal and activation for settings links", async () => {
    const user = userEvent.setup()
    renderSettingsLayout("/settings/tldw")

    const activeLink = screen.getByRole("link", {
      name: "settings:tldw.serverNav"
    })
    const chatLink = screen.getByRole("link", {
      name: "settings:chatSettingsNav"
    })

    await user.tab()
    expect(activeLink).toHaveFocus()

    await user.tab()
    expect(chatLink).toHaveFocus()

    await user.keyboard("{Enter}")
    expect(screen.getByTestId("settings-layout-location")).toHaveTextContent(
      "/settings/chat"
    )
  })
})
