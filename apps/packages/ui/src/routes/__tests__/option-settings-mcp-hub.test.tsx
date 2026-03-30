// @vitest-environment jsdom
import React from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }

      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue ?? ""
      }

      return ""
    },
    i18n: {
      language: "en",
      resolvedLanguage: "en"
    }
  })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: false,
    capabilities: {
      hasMcpHub: true
    }
  })
}))

vi.mock("@/components/Option/MCPHub", () => ({
  McpHubPage: () => <h1>MCP Hub</h1>
}))
vi.mock("~/components/Layouts/Layout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

import { OptionSettingsMcpHub } from "../option-settings-mcp-hub"

describe("OptionSettingsMcpHub", () => {
  it("renders the MCP Hub page inside the shared settings shell", () => {
    render(
      <MemoryRouter initialEntries={["/settings/mcp-hub"]}>
        <Routes>
          <Route path="*" element={<OptionSettingsMcpHub />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId("settings-navigation")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: /mcp hub/i })).toBeInTheDocument()
  })
})
