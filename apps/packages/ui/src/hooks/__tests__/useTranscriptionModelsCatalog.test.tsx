import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { getTranscriptionModelsMock, tMock } = vi.hoisted(() => ({
  getTranscriptionModelsMock: vi.fn(),
  tMock: vi.fn((_key: string, fallback?: string) => fallback || _key)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: tMock
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getTranscriptionModels: getTranscriptionModelsMock
  }
}))

vi.mock("@/utils/request-timeout", () => ({
  isTimeoutLikeError: vi.fn((error: unknown) =>
    error instanceof Error && error.message.includes("timeout")
  )
}))

import { useTranscriptionModelsCatalog } from "../useTranscriptionModelsCatalog"

describe("useTranscriptionModelsCatalog", () => {
  beforeEach(() => {
    getTranscriptionModelsMock.mockReset()
    tMock.mockClear()
  })

  it("retries model loading through the shared retry callback", async () => {
    getTranscriptionModelsMock
      .mockRejectedValueOnce(new Error("timeout while loading transcription models"))
      .mockResolvedValueOnce({ all_models: ["whisper-1", "parakeet-tdt"] })

    const { result } = renderHook(() => useTranscriptionModelsCatalog())

    await waitFor(() => {
      expect(result.current.serverModelsError).toBe(
        "Model list took longer than 10 seconds. Check server health and retry."
      )
    })
    expect(getTranscriptionModelsMock).toHaveBeenCalledTimes(1)

    act(() => {
      result.current.retryServerModels()
    })

    await waitFor(() => {
      expect(getTranscriptionModelsMock).toHaveBeenCalledTimes(2)
      expect(result.current.serverModels).toEqual(["parakeet-tdt", "whisper-1"])
      expect(result.current.serverModelsError).toBeNull()
    })
  })

  it("supports one automatic retry before surfacing the inline error", async () => {
    getTranscriptionModelsMock
      .mockRejectedValueOnce(new Error("timeout-1"))
      .mockRejectedValueOnce(new Error("timeout-2"))
      .mockResolvedValueOnce({ all_models: ["whisper-1", "parakeet-tdt"] })

    const { result } = renderHook(() =>
      useTranscriptionModelsCatalog({
        autoRetryOnFailureCount: 1
      })
    )

    await waitFor(() => {
      expect(getTranscriptionModelsMock).toHaveBeenCalledTimes(2)
      expect(result.current.serverModelsError).toBe(
        "Model list took longer than 10 seconds. Check server health and retry."
      )
    })

    act(() => {
      result.current.retryServerModels()
    })

    await waitFor(() => {
      expect(getTranscriptionModelsMock).toHaveBeenCalledTimes(3)
      expect(result.current.serverModels).toEqual(["parakeet-tdt", "whisper-1"])
      expect(result.current.serverModelsError).toBeNull()
    })
  })

  it("sets an initial model when provided a setter callback", async () => {
    getTranscriptionModelsMock.mockResolvedValue({
      all_models: ["whisper-1", "parakeet-tdt"]
    })
    const setInitialModel = vi.fn()

    renderHook(() =>
      useTranscriptionModelsCatalog({
        activeModel: undefined,
        defaultModel: "parakeet-tdt",
        onInitialModel: setInitialModel
      })
    )

    await waitFor(() => {
      expect(setInitialModel).toHaveBeenCalledWith("parakeet-tdt")
    })
  })
})
