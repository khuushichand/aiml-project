import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  serverCapabilities: {
    capabilities: { hasMcp: true },
    loading: false
  },
  fetchMcpToolCatalogs: vi.fn(),
  fetchMcpTools: vi.fn(),
  fetchMcpToolCatalogsViaDiscovery: vi.fn(),
  fetchMcpModulesViaDiscovery: vi.fn(),
  fetchMcpToolsViaDiscovery: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => mocks.serverCapabilities
}))

vi.mock("@/services/tldw/mcp", () => ({
  fetchMcpToolCatalogs: (...args: unknown[]) =>
    (mocks.fetchMcpToolCatalogs as (...args: unknown[]) => unknown)(...args),
  fetchMcpTools: (...args: unknown[]) =>
    (mocks.fetchMcpTools as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolCatalogsViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpToolCatalogsViaDiscovery as (...args: unknown[]) => unknown)(...args),
  fetchMcpModulesViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpModulesViaDiscovery as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolsViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpToolsViaDiscovery as (...args: unknown[]) => unknown)(...args)
}))

import { McpToolPicker } from "../McpToolPicker"

const renderWithQueryClient = (ui: React.ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  })

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

describe("McpToolPicker", () => {
  beforeEach(() => {
    mocks.serverCapabilities = {
      capabilities: { hasMcp: true },
      loading: false
    }
    mocks.fetchMcpToolCatalogs.mockReset()
    mocks.fetchMcpTools.mockReset()
    mocks.fetchMcpToolCatalogsViaDiscovery.mockReset()
    mocks.fetchMcpModulesViaDiscovery.mockReset()
    mocks.fetchMcpToolsViaDiscovery.mockReset()

    mocks.fetchMcpToolCatalogsViaDiscovery.mockResolvedValue([
      { id: 1, name: "Global Notes" },
      { id: 2, name: "Team Alerts", team_id: 7 }
    ])
    mocks.fetchMcpModulesViaDiscovery.mockResolvedValue(["alerts", "media", "notes"])
    mocks.fetchMcpToolsViaDiscovery.mockResolvedValue([
      { name: "notes.search", module: "notes", canExecute: true },
      { name: "notes.create", module: "notes", canExecute: true },
      { name: "alerts.send", module: "alerts", canExecute: true }
    ])
    mocks.fetchMcpToolCatalogs.mockResolvedValue([])
    mocks.fetchMcpTools.mockResolvedValue([])
  })

  it("shows a loading state while MCP options are loading", () => {
    mocks.fetchMcpToolCatalogsViaDiscovery.mockImplementation(
      () => new Promise(() => undefined)
    )
    mocks.fetchMcpModulesViaDiscovery.mockImplementation(
      () => new Promise(() => undefined)
    )
    mocks.fetchMcpToolsViaDiscovery.mockImplementation(
      () => new Promise(() => undefined)
    )

    renderWithQueryClient(<McpToolPicker value="" onChange={vi.fn()} />)

    expect(screen.getByText("Loading MCP tools...")).toBeInTheDocument()
  })

  it("lets the user choose a module-scoped MCP tool", async () => {
    const onChange = vi.fn()

    renderWithQueryClient(<McpToolPicker value="" onChange={onChange} />)

    await screen.findByTestId("persona-mcp-tool-picker-module-select")

    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-module-select"), {
      target: { value: "notes" }
    })
    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-tool-select"), {
      target: { value: "notes.search" }
    })

    expect(onChange).toHaveBeenCalledWith("notes.search")
    expect(screen.getByTestId("persona-mcp-tool-picker-tool-select")).toHaveValue(
      "notes.search"
    )
  })

  it("falls back to manual entry when MCP is unavailable", async () => {
    mocks.serverCapabilities = {
      capabilities: { hasMcp: false },
      loading: false
    }
    const onChange = vi.fn()

    renderWithQueryClient(
      <McpToolPicker value="notes.search" onChange={onChange} />
    )

    expect(
      screen.getByText("MCP discovery is unavailable for this server. Enter a tool name manually.")
    ).toBeInTheDocument()

    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-manual-input"), {
      target: { value: "media.search" }
    })

    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith("media.search")
    )
  })

  it("keeps the committed value and shows a warning when the selected module no longer contains it", async () => {
    mocks.fetchMcpToolsViaDiscovery.mockImplementation(
      async (params?: { module?: string }) => {
        if (params?.module === "alerts") {
          return [{ name: "alerts.send", module: "alerts", canExecute: true }]
        }
        if (params?.module === "notes") {
          return [{ name: "notes.search", module: "notes", canExecute: true }]
        }
        return [
          { name: "alerts.send", module: "alerts", canExecute: true },
          { name: "notes.search", module: "notes", canExecute: true }
        ]
      }
    )
    const onChange = vi.fn()

    renderWithQueryClient(
      <McpToolPicker value="alerts.send" onChange={onChange} />
    )

    await screen.findByTestId("persona-mcp-tool-picker-module-select")

    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-module-select"), {
      target: { value: "notes" }
    })

    await waitFor(() =>
      expect(
        screen.getByText("Selected tool is no longer available in this module.")
      ).toBeInTheDocument()
    )
    expect(onChange).not.toHaveBeenCalled()
  })

  it("can auto-clear stale values when explicitly enabled", async () => {
    mocks.fetchMcpToolsViaDiscovery.mockImplementation(
      async (params?: { module?: string }) => {
        if (params?.module === "alerts") {
          return [{ name: "alerts.send", module: "alerts", canExecute: true }]
        }
        if (params?.module === "notes") {
          return [{ name: "notes.search", module: "notes", canExecute: true }]
        }
        return [
          { name: "alerts.send", module: "alerts", canExecute: true },
          { name: "notes.search", module: "notes", canExecute: true }
        ]
      }
    )
    const onChange = vi.fn()

    renderWithQueryClient(
      React.createElement(McpToolPicker as React.ComponentType<any>, {
        value: "alerts.send",
        onChange,
        autoClearStaleTool: true
      })
    )

    await screen.findByTestId("persona-mcp-tool-picker-module-select")

    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-module-select"), {
      target: { value: "notes" }
    })

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(""))
  })

  it("does not emit duplicate-key warnings when tools share a name", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {})
    mocks.fetchMcpToolsViaDiscovery.mockResolvedValue([
      { id: "tool-a", name: "shared.lookup", module: "notes", canExecute: true },
      { id: "tool-b", name: "shared.lookup", module: "alerts", canExecute: true }
    ])

    renderWithQueryClient(<McpToolPicker value="" onChange={vi.fn()} />)

    await screen.findByTestId("persona-mcp-tool-picker-tool-select")

    const duplicateKeyWarning = consoleError.mock.calls.some((call) =>
      call.some(
        (entry) =>
          typeof entry === "string" &&
          entry.includes("Encountered two children with the same key")
      )
    )

    expect(duplicateKeyWarning).toBe(false)

    consoleError.mockRestore()
  })
})
