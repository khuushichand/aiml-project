// @vitest-environment jsdom
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

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

describe("Playground request budget", () => {
  afterEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  it("keeps optional request classes idle before the chat surface engages them", async () => {
    const state = {
      apiSend: vi.fn(),
      fetchMcpTools: vi.fn(),
      fetchMcpToolCatalogs: vi.fn(),
      fetchMcpToolCatalogsViaDiscovery: vi.fn(),
      fetchMcpModulesViaDiscovery: vi.fn(),
      fetchMcpToolsViaDiscovery: vi.fn(),
      listChatsWithMeta: vi.fn(),
      searchConversationsWithMeta: vi.fn(),
      initialize: vi.fn(async () => undefined)
    }

    vi.doMock("react-i18next", () => ({
      useTranslation: () => ({
        t: (key: string, defaultValue?: string) => defaultValue || key
      })
    }))

    vi.doMock("@/hooks/useServerCapabilities", () => ({
      useServerCapabilities: () => ({
        capabilities: {
          hasMcp: true,
          hasAudio: true,
          hasStt: true,
          hasTts: true,
          hasVoiceChat: true
        },
        loading: false
      })
    }))

    vi.doMock("@/hooks/useConnectionState", () => ({
      useConnectionState: () => ({
        isConnected: true
      })
    }))

    vi.doMock("@/store/connection", () => ({
      useConnectionStore: (
        selector: (state: { checkOnce: ReturnType<typeof vi.fn> }) => unknown
      ) => selector({ checkOnce: vi.fn(async () => undefined) })
    }))

    vi.doMock("@/hooks/useSetting", () => ({
      useSetting: () => [null, vi.fn()]
    }))

    vi.doMock("@/services/api-send", () => ({
      apiSend: (...args: unknown[]) =>
        (state.apiSend as (...args: unknown[]) => unknown)(...args)
    }))

    vi.doMock("@/services/tldw/mcp", () => ({
      fetchMcpTools: (...args: unknown[]) =>
        (state.fetchMcpTools as (...args: unknown[]) => unknown)(...args),
      fetchMcpToolCatalogs: (...args: unknown[]) =>
        (state.fetchMcpToolCatalogs as (...args: unknown[]) => unknown)(...args),
      fetchMcpToolCatalogsViaDiscovery: (...args: unknown[]) =>
        (state.fetchMcpToolCatalogsViaDiscovery as (...args: unknown[]) => unknown)(
          ...args
        ),
      fetchMcpModulesViaDiscovery: (...args: unknown[]) =>
        (state.fetchMcpModulesViaDiscovery as (...args: unknown[]) => unknown)(
          ...args
        ),
      fetchMcpToolsViaDiscovery: (...args: unknown[]) =>
        (state.fetchMcpToolsViaDiscovery as (...args: unknown[]) => unknown)(
          ...args
        )
    }))

    vi.doMock("@/services/tldw/TldwApiClient", () => ({
      tldwClient: {
        initialize: state.initialize,
        listChatsWithMeta: (...args: unknown[]) =>
          (state.listChatsWithMeta as (...args: unknown[]) => unknown)(...args),
        searchConversationsWithMeta: (...args: unknown[]) =>
          (state.searchConversationsWithMeta as (...args: unknown[]) => unknown)(
            ...args
          )
      }
    }))

    const { useMcpTools } = await import("@/hooks/useMcpTools")
    const { useTldwAudioStatus } = await import("@/hooks/useTldwAudioStatus")
    const { useServerChatHistory } = await import("@/hooks/useServerChatHistory")

    function BudgetHarness() {
      useMcpTools({ enabled: false })
      useTldwAudioStatus({ enabled: false })
      useServerChatHistory("", {
        enabled: false,
        mode: "overview"
      })
      return null
    }

    render(<BudgetHarness />, {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(state.apiSend).not.toHaveBeenCalledWith(
        expect.objectContaining({ path: "/api/v1/mcp/health" })
      )
      expect(state.apiSend).not.toHaveBeenCalledWith(
        expect.objectContaining({ path: "/api/v1/audio/health" })
      )
      expect(state.apiSend).not.toHaveBeenCalledWith(
        expect.objectContaining({ path: "/api/v1/audio/transcriptions/health" })
      )
      expect(state.fetchMcpTools).not.toHaveBeenCalled()
      expect(state.fetchMcpToolCatalogs).not.toHaveBeenCalled()
      expect(state.fetchMcpToolCatalogsViaDiscovery).not.toHaveBeenCalled()
      expect(state.fetchMcpModulesViaDiscovery).not.toHaveBeenCalled()
      expect(state.fetchMcpToolsViaDiscovery).not.toHaveBeenCalled()
      expect(state.listChatsWithMeta).not.toHaveBeenCalled()
      expect(state.searchConversationsWithMeta).not.toHaveBeenCalled()
    })
  })
})
