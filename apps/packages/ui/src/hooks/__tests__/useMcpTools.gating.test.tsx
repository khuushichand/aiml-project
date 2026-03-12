import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useMcpTools } from "@/hooks/useMcpTools"
import { useMcpToolsStore } from "@/store/mcp-tools"

const state = vi.hoisted(() => ({
  capabilities: {
    hasMcp: true
  } as any,
  loading: false,
  apiSend: vi.fn(),
  fetchMcpTools: vi.fn(),
  fetchMcpToolCatalogs: vi.fn(),
  fetchMcpToolCatalogsViaDiscovery: vi.fn(),
  fetchMcpModulesViaDiscovery: vi.fn(),
  fetchMcpToolsViaDiscovery: vi.fn()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: state.capabilities,
    loading: state.loading
  })
}))

vi.mock("@/hooks/useSetting", () => ({
  useSetting: () => [null, vi.fn()]
}))

vi.mock("@/services/api-send", () => ({
  apiSend: (...args: unknown[]) =>
    (state.apiSend as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/services/tldw/mcp", () => ({
  fetchMcpTools: (...args: unknown[]) =>
    (state.fetchMcpTools as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolCatalogs: (...args: unknown[]) =>
    (state.fetchMcpToolCatalogs as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolCatalogsViaDiscovery: (...args: unknown[]) =>
    (state.fetchMcpToolCatalogsViaDiscovery as (...args: unknown[]) => unknown)(
      ...args
    ),
  fetchMcpModulesViaDiscovery: (...args: unknown[]) =>
    (state.fetchMcpModulesViaDiscovery as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolsViaDiscovery: (...args: unknown[]) =>
    (state.fetchMcpToolsViaDiscovery as (...args: unknown[]) => unknown)(...args)
}))

const buildWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useMcpTools gating", () => {
  beforeEach(() => {
    state.capabilities = { hasMcp: true }
    state.loading = false
    state.apiSend.mockReset()
    state.fetchMcpTools.mockReset()
    state.fetchMcpToolCatalogs.mockReset()
    state.fetchMcpToolCatalogsViaDiscovery.mockReset()
    state.fetchMcpModulesViaDiscovery.mockReset()
    state.fetchMcpToolsViaDiscovery.mockReset()
    useMcpToolsStore.setState({
      tools: [],
      healthState: "unknown",
      toolsLoading: false,
      toolCatalog: "",
      toolCatalogId: null,
      toolModules: [],
      toolCatalogStrict: false
    })
  })

  it("does not query MCP endpoints until the tools surface is enabled", async () => {
    const { result } = renderHook(() => useMcpTools({ enabled: false }), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.healthLoading).toBe(false)
      expect(result.current.toolsLoading).toBe(false)
      expect(result.current.catalogsLoading).toBe(false)
    })

    expect(result.current.healthState).toBe("unknown")
    expect(result.current.tools).toEqual([])
    expect(state.apiSend).not.toHaveBeenCalled()
    expect(state.fetchMcpTools).not.toHaveBeenCalled()
    expect(state.fetchMcpToolCatalogs).not.toHaveBeenCalled()
    expect(state.fetchMcpToolCatalogsViaDiscovery).not.toHaveBeenCalled()
    expect(state.fetchMcpModulesViaDiscovery).not.toHaveBeenCalled()
    expect(state.fetchMcpToolsViaDiscovery).not.toHaveBeenCalled()
  })
})
