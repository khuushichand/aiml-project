import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { SettingsLayout } from "../SettingsOptionLayout"

const IconStub = () => null

const SETTINGS_ITEMS = Array.from({ length: 13 }, (_, index) => ({
  to: `/settings/section-${index + 1}`,
  labelToken: `Section ${index + 1}`,
  icon: IconStub
}))

SETTINGS_ITEMS[4] = {
  ...SETTINGS_ITEMS[4],
  to: "/settings/speech-controls",
  labelToken: "Speech Controls"
}
SETTINGS_ITEMS[8] = {
  ...SETTINGS_ITEMS[8],
  to: "/settings/image-generation",
  labelToken: "Image Generation"
}

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
      items: SETTINGS_ITEMS
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
  const actual =
    await importOriginal<typeof import("@/services/settings/registry")>()
  return {
    ...actual,
    setSetting: vi.fn()
  }
})

vi.mock("@/utils/settings-return", () => ({
  getSettingsReturnTo: () => null
}))

const renderSettingsLayout = () =>
  render(
    <MemoryRouter initialEntries={["/settings/section-1"]}>
      <Routes>
        <Route
          path="*"
          element={
            <SettingsLayout>
              <div>content</div>
            </SettingsLayout>
          }
        />
      </Routes>
    </MemoryRouter>
  )

describe("settings navigation filter", () => {
  it("shows a search input when settings count is high", () => {
    renderSettingsLayout()

    expect(screen.getByTestId("settings-nav-filter")).toBeInTheDocument()
  })

  it("filters visible settings links by query", async () => {
    const user = userEvent.setup()
    renderSettingsLayout()

    const input = screen.getByTestId("settings-nav-filter")
    await user.type(input, "speech")

    expect(screen.getByRole("link", { name: "Speech Controls" })).toBeVisible()
    expect(
      screen.queryByRole("link", { name: "Image Generation" })
    ).not.toBeInTheDocument()
  })

  it("shows an explicit empty state when no setting matches the filter", async () => {
    const user = userEvent.setup()
    renderSettingsLayout()

    const input = screen.getByTestId("settings-nav-filter")
    await user.type(input, "does-not-exist")

    expect(screen.getByTestId("settings-nav-filter-empty")).toHaveTextContent(
      "No settings match this search."
    )
  })
})
