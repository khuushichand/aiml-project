import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useTldwAudioStatus } from "@/hooks/useTldwAudioStatus"

const state = vi.hoisted(() => ({
  capabilities: {
    hasAudio: true,
    hasStt: true,
    hasTts: true,
    hasVoiceChat: true
  } as any,
  loading: false,
  apiSend: vi.fn(),
  fetchVoices: vi.fn()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: state.capabilities,
    loading: state.loading
  })
}))

vi.mock("@/services/api-send", () => ({
  apiSend: (...args: unknown[]) =>
    (state.apiSend as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/services/tldw/audio-voices", () => ({
  fetchTldwVoices: (...args: unknown[]) =>
    (state.fetchVoices as (...args: unknown[]) => unknown)(...args)
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

describe("useTldwAudioStatus", () => {
  beforeEach(() => {
    state.capabilities = {
      hasAudio: true,
      hasStt: true,
      hasTts: true,
      hasVoiceChat: true
    }
    state.loading = false
    state.apiSend.mockReset()
    state.fetchVoices.mockReset()
    state.fetchVoices.mockResolvedValue([])
  })

  it("runs split STT/TTS probes when capabilities are available", async () => {
    state.apiSend.mockImplementation(async (payload: { path: string }) => {
      if (payload.path === "/api/v1/audio/transcriptions/health") {
        return { ok: true, status: 200, data: { available: true } }
      }
      if (payload.path === "/api/v1/audio/health") {
        return { ok: true, status: 200 }
      }
      return { ok: false, status: 404 }
    })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthState).toBe("healthy")
      expect(result.current.ttsHealthState).toBe("healthy")
    })

    expect(result.current.hasStt).toBe(true)
    expect(result.current.hasTts).toBe(true)
    expect(result.current.hasVoiceChat).toBe(true)
    expect(result.current.hasAudio).toBe(true)
    expect(result.current.healthState).toBe("healthy")
    expect(state.apiSend).toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/audio/transcriptions/health" })
    )
    expect(state.apiSend).toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/audio/health" })
    )
  })

  it("does not probe audio health until the surface is explicitly enabled", async () => {
    const { result } = renderHook(() => useTldwAudioStatus({ enabled: false }), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthLoading).toBe(false)
      expect(result.current.ttsHealthLoading).toBe(false)
    })

    expect(result.current.sttHealthState).toBe("unknown")
    expect(result.current.ttsHealthState).toBe("unknown")
    expect(state.apiSend).not.toHaveBeenCalled()
  })

  it("treats missing STT health endpoint as unknown instead of unhealthy", async () => {
    state.capabilities = {
      hasAudio: true,
      hasStt: true,
      hasTts: false,
      hasVoiceChat: false
    }
    state.apiSend.mockResolvedValue({ ok: false, status: 404 })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthLoading).toBe(false)
    })

    expect(result.current.sttHealthState).toBe("unknown")
    expect(result.current.ttsHealthState).toBe("unavailable")
  })

  it("marks STT as unhealthy when probe reports unavailable model", async () => {
    state.capabilities = {
      hasAudio: true,
      hasStt: true,
      hasTts: false,
      hasVoiceChat: false
    }
    state.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: { available: false }
    })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthLoading).toBe(false)
    })

    expect(result.current.sttHealthState).toBe("unhealthy")
  })

  it("treats on-demand Whisper models as healthy for first-use downloads", async () => {
    state.capabilities = {
      hasAudio: true,
      hasStt: true,
      hasTts: false,
      hasVoiceChat: false
    }
    state.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: { available: false, provider: "whisper", on_demand: true }
    })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthLoading).toBe(false)
    })

    expect(result.current.sttHealthState).toBe("healthy")
  })

  it("fail-opens STT health for non-whisper providers that report not-ready models", async () => {
    state.capabilities = {
      hasAudio: true,
      hasStt: true,
      hasTts: false,
      hasVoiceChat: false
    }
    state.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: { available: false, provider: "parakeet" }
    })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthLoading).toBe(false)
    })

    expect(result.current.sttHealthState).toBe("healthy")
  })

  it("derives split capability flags from legacy hasAudio-only responses", async () => {
    state.capabilities = {
      hasAudio: true
    }
    state.apiSend.mockImplementation(async (payload: { path: string }) => {
      if (payload.path === "/api/v1/audio/transcriptions/health") {
        return { ok: true, status: 200, data: { available: true } }
      }
      if (payload.path === "/api/v1/audio/health") {
        return { ok: true, status: 200 }
      }
      return { ok: false, status: 404 }
    })

    const { result } = renderHook(() => useTldwAudioStatus(), {
      wrapper: buildWrapper()
    })

    await waitFor(() => {
      expect(result.current.sttHealthState).toBe("healthy")
      expect(result.current.ttsHealthState).toBe("healthy")
    })

    expect(result.current.hasStt).toBe(true)
    expect(result.current.hasTts).toBe(true)
    expect(result.current.hasAudio).toBe(true)
  })
})
