import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"
import { renderHook, act } from "@testing-library/react"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockTrackStop = vi.fn()
const mockGetUserMedia = vi.fn().mockResolvedValue({
  getTracks: () => [{ stop: mockTrackStop }]
})

class MockMediaRecorder {
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: ((e: unknown) => void) | null = null
  mimeType = "audio/webm"
  state = "inactive" as "inactive" | "recording"

  start = vi.fn(() => {
    this.state = "recording"
  })

  stop = vi.fn(() => {
    this.state = "inactive"
    if (this.ondataavailable) {
      this.ondataavailable({
        data: new Blob(["audio-data"], { type: "audio/webm" })
      })
    }
    if (this.onstop) {
      this.onstop()
    }
  })
}

vi.stubGlobal("MediaRecorder", MockMediaRecorder)
vi.stubGlobal("navigator", {
  mediaDevices: { getUserMedia: mockGetUserMedia }
})

// Import after mocks are in place
import { useAudioRecorder } from "../useAudioRecorder"

describe("useAudioRecorder", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("starts in idle state with no blob and zero duration", () => {
    const { result } = renderHook(() => useAudioRecorder())

    expect(result.current.status).toBe("idle")
    expect(result.current.blob).toBeNull()
    expect(result.current.durationMs).toBe(0)
  })

  it("transitions to recording state after startRecording", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.status).toBe("recording")
    expect(mockGetUserMedia).toHaveBeenCalledWith({ audio: true })
  })

  it("passes the selected deviceId to getUserMedia when recording starts", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording({ deviceId: "usb-1" })
    })

    expect(mockGetUserMedia).toHaveBeenCalledWith({
      audio: { deviceId: { exact: "usb-1" } }
    })
  })

  it("falls back to the default microphone when no deviceId is provided", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording({})
    })

    expect(mockGetUserMedia).toHaveBeenCalledWith({ audio: true })
  })

  it("increments durationMs while recording", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.durationMs).toBe(0)

    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current.durationMs).toBe(200)

    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current.durationMs).toBe(400)
  })

  it("produces a blob on stop and returns to idle", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })

    act(() => {
      vi.advanceTimersByTime(600)
    })

    act(() => {
      result.current.stopRecording()
    })

    expect(result.current.status).toBe("idle")
    expect(result.current.blob).toBeInstanceOf(Blob)
    expect(result.current.durationMs).toBe(600)
  })

  it("stops media tracks on stop", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })

    act(() => {
      result.current.stopRecording()
    })

    expect(mockTrackStop).toHaveBeenCalled()
  })

  it("clears blob and duration with clearRecording", async () => {
    const { result } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })
    act(() => {
      vi.advanceTimersByTime(400)
    })
    act(() => {
      result.current.stopRecording()
    })

    expect(result.current.blob).not.toBeNull()

    act(() => {
      result.current.clearRecording()
    })

    expect(result.current.blob).toBeNull()
    expect(result.current.durationMs).toBe(0)
  })

  it("accepts a blob via loadBlob", () => {
    const { result } = renderHook(() => useAudioRecorder())
    const externalBlob = new Blob(["external"], { type: "audio/webm" })

    act(() => {
      result.current.loadBlob(externalBlob, 5000)
    })

    expect(result.current.blob).toBe(externalBlob)
    expect(result.current.durationMs).toBe(5000)
    expect(result.current.status).toBe("idle")
  })

  it("does nothing if stopRecording is called while idle", () => {
    const { result } = renderHook(() => useAudioRecorder())

    // Should not throw
    act(() => {
      result.current.stopRecording()
    })

    expect(result.current.status).toBe("idle")
  })

  it("cleans up on unmount during recording", async () => {
    const { result, unmount } = renderHook(() => useAudioRecorder())

    await act(async () => {
      await result.current.startRecording()
    })

    unmount()

    expect(mockTrackStop).toHaveBeenCalled()
  })
})
