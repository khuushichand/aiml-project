import React from "react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useTtsProviderData } from "@/hooks/useTtsProviderData"
import { getModels, getVoices } from "@/services/elevenlabs"
import { fetchTldwTtsModels } from "@/services/tldw/audio-models"
import { fetchTtsProviders } from "@/services/tldw/audio-providers"
import { fetchTldwVoiceCatalog } from "@/services/tldw/audio-voices"

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasAudio: true },
    loading: false
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/elevenlabs", () => ({
  getVoices: vi.fn(),
  getModels: vi.fn()
}))

vi.mock("@/services/tldw/audio-providers", () => ({
  fetchTtsProviders: vi.fn()
}))

vi.mock("@/services/tldw/audio-models", () => ({
  fetchTldwTtsModels: vi.fn()
}))

vi.mock("@/services/tldw/audio-voices", () => ({
  fetchTldwVoiceCatalog: vi.fn()
}))

const buildWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useTtsProviderData", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchTtsProviders).mockResolvedValue(null)
    vi.mocked(fetchTldwTtsModels).mockResolvedValue([])
    vi.mocked(fetchTldwVoiceCatalog).mockResolvedValue([])
  })

  it("loads ElevenLabs metadata with a bounded timeout", async () => {
    vi.mocked(getVoices).mockResolvedValue([
      { voice_id: "voice-1", name: "Voice 1" }
    ])
    vi.mocked(getModels).mockResolvedValue([
      { model_id: "model-1", name: "Model 1" }
    ])

    const { result } = renderHook(
      () =>
        useTtsProviderData({
          provider: "elevenlabs",
          elevenLabsApiKey: "test-key"
        }),
      { wrapper: buildWrapper() }
    )

    await waitFor(() => {
      expect(result.current.elevenLabsLoading).toBe(false)
      expect(result.current.elevenLabsData?.voices).toHaveLength(1)
      expect(result.current.elevenLabsData?.models).toHaveLength(1)
    })

    expect(getVoices).toHaveBeenCalledWith("test-key", { timeoutMs: 10_000 })
    expect(getModels).toHaveBeenCalledWith("test-key", { timeoutMs: 10_000 })
    expect(result.current.elevenLabsError).toBeNull()
    expect(typeof result.current.refetchElevenLabs).toBe("function")
  })

  it("surfaces ElevenLabs metadata failures for retry UX", async () => {
    vi.mocked(getVoices).mockRejectedValue(new Error("Request timeout"))
    vi.mocked(getModels).mockResolvedValue([
      { model_id: "model-1", name: "Model 1" }
    ])

    const { result } = renderHook(
      () =>
        useTtsProviderData({
          provider: "elevenlabs",
          elevenLabsApiKey: "test-key"
        }),
      { wrapper: buildWrapper() }
    )

    await waitFor(() => {
      expect(result.current.elevenLabsLoading).toBe(false)
      expect(result.current.elevenLabsError).toBeTruthy()
    })

    expect(getVoices).toHaveBeenCalledWith("test-key", { timeoutMs: 10_000 })
    expect(getModels).toHaveBeenCalledWith("test-key", { timeoutMs: 10_000 })
    expect(result.current.elevenLabsData).toBeUndefined()
  })
})
