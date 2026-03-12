import React from "react"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useDocumentTTS } from "@/hooks/document-workspace/useDocumentTTS"

const mocks = vi.hoisted(() => ({
  fetchTldwVoices: vi.fn(async () => [])
}))

vi.mock("@/services/tldw/audio-voices", () => ({
  fetchTldwVoices: mocks.fetchTldwVoices
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

describe("useDocumentTTS", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("falls back to defaults when localStorage reads throw", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage blocked")
    })

    const { result } = renderHook(() => useDocumentTTS(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.voicesLoading).toBe(false)
    })

    expect(result.current.voice).toBe("af_sky")
    expect(result.current.speed).toBe(1)
    expect(result.current.volume).toBe(1)
  })
})
