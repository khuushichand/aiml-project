import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { useSplashScreen } from "../useSplashScreen"

describe("useSplashScreen", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("does not auto-show on mount", () => {
    const { result } = renderHook(() => useSplashScreen())

    expect(result.current.visible).toBe(false)
    expect(result.current.card).toBeNull()
  })

  it("shows a splash only when explicitly triggered", () => {
    const { result } = renderHook(() => useSplashScreen())

    act(() => {
      result.current.show()
    })

    expect(result.current.visible).toBe(true)
    expect(result.current.card).not.toBeNull()
    expect(result.current.message.length).toBeGreaterThan(0)
  })

  it("respects disabled preference from localStorage", async () => {
    localStorage.setItem("tldw_splash_disabled", "true")
    const { result } = renderHook(() => useSplashScreen())

    await waitFor(() => {
      expect(result.current.disabled).toBe(true)
    })

    act(() => {
      result.current.show()
    })

    expect(result.current.visible).toBe(false)
    expect(result.current.card).toBeNull()
  })

  it("persists disable toggle and hides an active splash", () => {
    const { result } = renderHook(() => useSplashScreen())

    act(() => {
      result.current.show()
    })
    expect(result.current.visible).toBe(true)

    act(() => {
      result.current.setDisabled(true)
    })

    expect(result.current.disabled).toBe(true)
    expect(result.current.visible).toBe(false)
    expect(localStorage.getItem("tldw_splash_disabled")).toBe("true")
  })

  it("still shows splash in reduced-motion mode (static overlay path)", () => {
    const originalMatchMedia = window.matchMedia
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: ((query: string) => ({
        matches: query === "(prefers-reduced-motion: reduce)",
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      })) as typeof window.matchMedia,
    })

    try {
      const { result } = renderHook(() => useSplashScreen())

      act(() => {
        result.current.show()
      })

      expect(result.current.visible).toBe(true)
      expect(result.current.card).not.toBeNull()
    } finally {
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        writable: true,
        value: originalMatchMedia,
      })
    }
  })
})
