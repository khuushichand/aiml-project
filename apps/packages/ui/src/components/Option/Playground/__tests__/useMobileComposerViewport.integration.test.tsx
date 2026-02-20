// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useMobileComposerViewport } from "../useMobileComposerViewport"

class MockVisualViewport {
  height: number
  offsetTop: number
  private listeners = new Map<string, Set<EventListener>>()

  constructor(height: number, offsetTop = 0) {
    this.height = height
    this.offsetTop = offsetTop
  }

  addEventListener(type: string, listener: EventListener) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(listener)
  }

  removeEventListener(type: string, listener: EventListener) {
    this.listeners.get(type)?.delete(listener)
  }

  emit(type: string) {
    const event = new Event(type)
    this.listeners.get(type)?.forEach((listener) => listener(event))
  }
}

const originalVisualViewport = Object.getOwnPropertyDescriptor(
  window,
  "visualViewport"
)

afterEach(() => {
  vi.restoreAllMocks()
  if (originalVisualViewport) {
    Object.defineProperty(window, "visualViewport", originalVisualViewport)
  } else {
    delete (window as any).visualViewport
  }
})

describe("useMobileComposerViewport integration", () => {
  it("tracks keyboard-open state from visual viewport resize events", () => {
    Object.defineProperty(window, "innerHeight", {
      value: 844,
      writable: true,
      configurable: true
    })
    const viewport = new MockVisualViewport(812, 0)
    Object.defineProperty(window, "visualViewport", {
      value: viewport,
      configurable: true
    })

    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0)
      return 1
    })
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {})

    const { result } = renderHook(() => useMobileComposerViewport(true))
    expect(result.current.keyboardOpen).toBe(false)
    expect(result.current.keyboardInsetPx).toBe(32)

    act(() => {
      viewport.height = 520
      viewport.emit("resize")
    })

    expect(result.current.keyboardOpen).toBe(true)
    expect(result.current.keyboardInsetPx).toBe(324)

    act(() => {
      viewport.height = 830
      viewport.emit("resize")
    })

    expect(result.current.keyboardOpen).toBe(false)
    expect(result.current.keyboardInsetPx).toBe(14)
  })

  it("resets to closed state when disabled", () => {
    Object.defineProperty(window, "innerHeight", {
      value: 844,
      writable: true,
      configurable: true
    })
    const viewport = new MockVisualViewport(500, 0)
    Object.defineProperty(window, "visualViewport", {
      value: viewport,
      configurable: true
    })

    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0)
      return 1
    })
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {})

    const { result, rerender } = renderHook(
      ({ enabled }) => useMobileComposerViewport(enabled),
      {
        initialProps: { enabled: true }
      }
    )

    expect(result.current.keyboardOpen).toBe(true)
    expect(result.current.keyboardInsetPx).toBe(344)

    rerender({ enabled: false })
    expect(result.current.keyboardOpen).toBe(false)
    expect(result.current.keyboardInsetPx).toBe(0)
  })
})
