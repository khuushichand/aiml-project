import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useSpeechRecognition } from "../useSpeechRecognition"

type MockRecognitionOptions = {
  startImpl?: () => void
  stopImpl?: (instance: MockSpeechRecognition) => void
}

class MockSpeechRecognition {
  lang = ""
  interimResults = false
  continuous = false
  maxAlternatives = 1
  grammars: any
  onresult: ((event: any) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onend: (() => void) | null = null
  start: ReturnType<typeof vi.fn>
  stop: ReturnType<typeof vi.fn>

  constructor(options: MockRecognitionOptions = {}) {
    this.start = vi.fn(() => {
      options.startImpl?.()
    })
    this.stop = vi.fn(() => {
      options.stopImpl?.(this)
    })
  }
}

let recognitionInstance: MockSpeechRecognition | null = null

const installSpeechRecognition = (options: MockRecognitionOptions = {}) => {
  class SpeechRecognitionCtor extends MockSpeechRecognition {
    constructor() {
      super(options)
      recognitionInstance = this
    }
  }
  ;(window as any).SpeechRecognition = SpeechRecognitionCtor
  ;(window as any).webkitSpeechRecognition = undefined
}

const makeResultEvent = (transcript: string) =>
  ({
    resultIndex: 0,
    results: [[{ transcript }]]
  }) as any

describe("useSpeechRecognition", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    recognitionInstance = null
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    ;(window as any).SpeechRecognition = undefined
    ;(window as any).webkitSpeechRecognition = undefined
    vi.restoreAllMocks()
  })

  it("reports unsupported when no SpeechRecognition API is available", () => {
    const { result } = renderHook(() => useSpeechRecognition())

    expect(result.current.supported).toBe(false)
    act(() => {
      result.current.start()
    })
    expect(result.current.isListening).toBe(false)
  })

  it("handles start() failures without leaving listening stuck", () => {
    installSpeechRecognition({
      startImpl: () => {
        throw new Error("start failed")
      }
    })
    const onError = vi.fn()
    const { result } = renderHook(() => useSpeechRecognition({ onError }))

    act(() => {
      result.current.start({ lang: "en-US" })
    })

    expect(result.current.supported).toBe(true)
    expect(result.current.isListening).toBe(false)
    expect(onError).toHaveBeenCalledTimes(1)
    const startFailureEvent = onError.mock.calls[0]?.[0] as any
    expect(startFailureEvent?.error).toBe("start-failed")
  })

  it("handles stop() failures and still ends the session", () => {
    installSpeechRecognition({
      stopImpl: () => {
        throw new Error("stop failed")
      }
    })
    const onError = vi.fn()
    const onEnd = vi.fn()
    const { result } = renderHook(() => useSpeechRecognition({ onError, onEnd }))

    act(() => {
      result.current.start({ lang: "en-US" })
    })
    expect(result.current.isListening).toBe(true)

    act(() => {
      result.current.stop()
    })

    expect(result.current.isListening).toBe(false)
    expect(onEnd).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(1)
    const stopFailureEvent = onError.mock.calls[0]?.[0] as any
    expect(stopFailureEvent?.error).toBe("stop-failed")
  })

  it("handles permission denial as a terminal event", () => {
    installSpeechRecognition()
    const onError = vi.fn()
    const onEnd = vi.fn()
    const { result } = renderHook(() => useSpeechRecognition({ onError, onEnd }))

    act(() => {
      result.current.start({ lang: "en-US" })
    })
    expect(result.current.isListening).toBe(true)

    act(() => {
      const event = new Event("error") as Event & { error?: string }
      event.error = "not-allowed"
      recognitionInstance?.onerror?.(event)
    })

    expect(result.current.isListening).toBe(false)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onEnd).toHaveBeenCalledTimes(1)
    expect((recognitionInstance as any)?.onend).toBeNull()
  })

  it("cleans up recognition listeners and stops capture on unmount", () => {
    installSpeechRecognition()
    const { result, unmount } = renderHook(() => useSpeechRecognition())

    act(() => {
      result.current.start({ lang: "en-US" })
    })

    const activeInstance = recognitionInstance
    expect(activeInstance).not.toBeNull()

    unmount()

    expect(activeInstance?.stop).toHaveBeenCalledTimes(1)
    expect((activeInstance as any)?.onresult).toBeNull()
    expect((activeInstance as any)?.onerror).toBeNull()
    expect((activeInstance as any)?.onend).toBeNull()
  })

  it("uses per-call autoStopTimeout override and avoids duplicate terminal callbacks", () => {
    installSpeechRecognition({
      stopImpl: (instance) => {
        instance.onend?.()
      }
    })
    const onEnd = vi.fn()
    const { result } = renderHook(() => useSpeechRecognition({ onEnd }))

    act(() => {
      result.current.start({
        lang: "en-US",
        autoStop: true,
        autoStopTimeout: 321,
        autoSubmit: false
      })
    })

    act(() => {
      recognitionInstance?.onresult?.(makeResultEvent("hello"))
    })

    act(() => {
      vi.advanceTimersByTime(320)
    })
    expect(onEnd).toHaveBeenCalledTimes(0)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(onEnd).toHaveBeenCalledTimes(1)
  })
})
