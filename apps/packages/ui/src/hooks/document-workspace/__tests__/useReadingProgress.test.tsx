import React from "react"
import { act, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useReadingProgressAutoSave } from "@/hooks/document-workspace/useReadingProgress"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

const mocks = vi.hoisted(() => ({
  updateReadingProgress: vi.fn(),
}))

vi.mock("@/services/tldw", () => ({
  tldwClient: {
    updateReadingProgress: mocks.updateReadingProgress,
  },
}))

const buildWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useReadingProgressAutoSave", () => {
  let initialConnectionStore: ReturnType<typeof useConnectionStore.getState>
  let initialWorkspaceStore: ReturnType<typeof useDocumentWorkspaceStore.getState>

  beforeEach(() => {
    vi.useFakeTimers()
    initialConnectionStore = useConnectionStore.getState()
    initialWorkspaceStore = useDocumentWorkspaceStore.getState()

    useConnectionStore.setState({
      state: {
        ...initialConnectionStore.state,
        isConnected: true,
        mode: "normal",
      },
    })

    useDocumentWorkspaceStore.setState({
      currentPage: 1,
      totalPages: 10,
      zoomLevel: 100,
      viewMode: "single",
      currentCfi: null,
      currentPercentage: 0,
    })

    mocks.updateReadingProgress.mockReset()
  })

  afterEach(() => {
    useConnectionStore.setState(initialConnectionStore, true)
    useDocumentWorkspaceStore.setState(initialWorkspaceStore, true)
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("stops autosave retries for a media id after a 404 response", async () => {
    mocks.updateReadingProgress.mockRejectedValue({ status: 404 })

    renderHook(() => useReadingProgressAutoSave(152, 50), {
      wrapper: buildWrapper(),
    })

    await act(async () => {
      vi.advanceTimersByTime(50)
      await Promise.resolve()
    })

    expect(mocks.updateReadingProgress).toHaveBeenCalledTimes(1)

    act(() => {
      useDocumentWorkspaceStore.setState({ currentPage: 2 })
    })

    await act(async () => {
      vi.advanceTimersByTime(50)
      await Promise.resolve()
    })

    expect(mocks.updateReadingProgress).toHaveBeenCalledTimes(1)
  })

  it("keeps attempting autosave for non-404 failures", async () => {
    mocks.updateReadingProgress.mockRejectedValue({ status: 500 })

    renderHook(() => useReadingProgressAutoSave(152, 50), {
      wrapper: buildWrapper(),
    })

    await act(async () => {
      vi.advanceTimersByTime(50)
      await Promise.resolve()
    })

    expect(mocks.updateReadingProgress).toHaveBeenCalledTimes(1)

    act(() => {
      useDocumentWorkspaceStore.setState({ currentPage: 3 })
    })

    await act(async () => {
      vi.advanceTimersByTime(50)
      await Promise.resolve()
    })

    expect(mocks.updateReadingProgress).toHaveBeenCalledTimes(2)
  })
})
