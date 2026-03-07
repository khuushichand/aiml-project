import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useLayoutMode } from "../hooks/useLayoutMode"
import type { LayoutMode } from "../hooks/useLayoutMode"

const STORAGE_KEY = "knowledge_qa_layout_mode"

describe("useLayoutMode", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // ── Requirement 1: defaults to "simple" when localStorage is empty ──

  it("defaults to simple mode when localStorage is empty", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.mode).toBe("simple")
  })

  // ── Requirement 2: reads persisted mode from localStorage ──

  it.each<LayoutMode>(["simple", "research", "expert"])(
    "reads persisted mode '%s' from localStorage",
    (persisted) => {
      localStorage.setItem(STORAGE_KEY, persisted)
      const { result } = renderHook(() =>
        useLayoutMode({ messageCount: 0 })
      )
      expect(result.current.mode).toBe(persisted)
    }
  )

  // ── Requirement 3: ignores invalid localStorage values ──

  it("ignores invalid localStorage values and defaults to simple", () => {
    localStorage.setItem(STORAGE_KEY, "bogus")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.mode).toBe("simple")
  })

  it("ignores empty string in localStorage and defaults to simple", () => {
    localStorage.setItem(STORAGE_KEY, "")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.mode).toBe("simple")
  })

  // ── Requirement 4: setLayoutMode updates mode and persists ──

  it("setLayoutMode updates mode and persists to localStorage", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )

    act(() => {
      result.current.setLayoutMode("research")
    })

    expect(result.current.mode).toBe("research")
    expect(localStorage.getItem(STORAGE_KEY)).toBe("research")
  })

  it("setLayoutMode to expert persists expert", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )

    act(() => {
      result.current.setLayoutMode("expert")
    })

    expect(result.current.mode).toBe("expert")
    expect(localStorage.getItem(STORAGE_KEY)).toBe("expert")
  })

  // ── Requirement 5: isSimple and isResearch derived booleans ──

  it("isSimple is true and isResearch is false in simple mode", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.isSimple).toBe(true)
    expect(result.current.isResearch).toBe(false)
  })

  it("isSimple is false and isResearch is true in research mode", () => {
    localStorage.setItem(STORAGE_KEY, "research")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.isSimple).toBe(false)
    expect(result.current.isResearch).toBe(true)
  })

  it("isSimple is false and isResearch is true in expert mode", () => {
    localStorage.setItem(STORAGE_KEY, "expert")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 0 })
    )
    expect(result.current.isSimple).toBe(false)
    expect(result.current.isResearch).toBe(true)
  })

  // ── Requirement 6: shows promotion toast when messageCount >= 6 in simple mode ──

  it("shows promotion toast when messageCount >= 6 in simple mode", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 6 })
    )
    expect(result.current.showPromotionToast).toBe(true)
  })

  it("shows promotion toast when messageCount is well above 6", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 20 })
    )
    expect(result.current.showPromotionToast).toBe(true)
  })

  it("does not show promotion toast when messageCount < 6 in simple mode", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 5 })
    )
    expect(result.current.showPromotionToast).toBe(false)
  })

  it("shows promotion toast when messageCount transitions from below to at threshold", () => {
    const { result, rerender } = renderHook(
      ({ messageCount }) => useLayoutMode({ messageCount }),
      { initialProps: { messageCount: 4 } }
    )
    expect(result.current.showPromotionToast).toBe(false)

    rerender({ messageCount: 6 })
    expect(result.current.showPromotionToast).toBe(true)
  })

  // ── Requirement 7: does NOT show promotion toast in research mode ──

  it("does not show promotion toast in research mode", () => {
    localStorage.setItem(STORAGE_KEY, "research")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 10 })
    )
    expect(result.current.showPromotionToast).toBe(false)
  })

  it("does not show promotion toast in expert mode", () => {
    localStorage.setItem(STORAGE_KEY, "expert")
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 10 })
    )
    expect(result.current.showPromotionToast).toBe(false)
  })

  // ── Requirement 8: does NOT show promotion toast after dismissed ──

  it("does not show promotion toast after it has been dismissed", () => {
    const { result, rerender } = renderHook(
      ({ messageCount }) => useLayoutMode({ messageCount }),
      { initialProps: { messageCount: 6 } }
    )
    expect(result.current.showPromotionToast).toBe(true)

    act(() => {
      result.current.dismissPromotion()
    })
    expect(result.current.showPromotionToast).toBe(false)

    // Even increasing message count should not re-show
    rerender({ messageCount: 20 })
    expect(result.current.showPromotionToast).toBe(false)
  })

  // ── Requirement 9: dismissPromotion hides toast and prevents future toasts ──

  it("dismissPromotion hides toast and prevents future toasts", () => {
    const { result, rerender } = renderHook(
      ({ messageCount }) => useLayoutMode({ messageCount }),
      { initialProps: { messageCount: 6 } }
    )
    expect(result.current.showPromotionToast).toBe(true)

    act(() => {
      result.current.dismissPromotion()
    })

    expect(result.current.showPromotionToast).toBe(false)

    // Re-render with even higher count - still no toast
    rerender({ messageCount: 100 })
    expect(result.current.showPromotionToast).toBe(false)
  })

  // ── Requirement 10: acceptPromotion switches to research and persists ──

  it("acceptPromotion switches to research mode and persists", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 6 })
    )
    expect(result.current.showPromotionToast).toBe(true)

    act(() => {
      result.current.acceptPromotion()
    })

    expect(result.current.mode).toBe("research")
    expect(result.current.isResearch).toBe(true)
    expect(result.current.isSimple).toBe(false)
    expect(result.current.showPromotionToast).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBe("research")
  })

  it("acceptPromotion prevents future promotion toasts", () => {
    const { result, rerender } = renderHook(
      ({ messageCount }) => useLayoutMode({ messageCount }),
      { initialProps: { messageCount: 6 } }
    )

    act(() => {
      result.current.acceptPromotion()
    })

    // Switch back to simple manually
    act(() => {
      result.current.setLayoutMode("simple")
    })

    // Even though we are back in simple mode with high message count,
    // promotionDismissed is true so no toast
    rerender({ messageCount: 100 })
    expect(result.current.showPromotionToast).toBe(false)
  })

  // ── Edge case: setLayoutMode clears the promotion toast ──

  it("setLayoutMode clears the promotion toast", () => {
    const { result } = renderHook(() =>
      useLayoutMode({ messageCount: 6 })
    )
    expect(result.current.showPromotionToast).toBe(true)

    act(() => {
      result.current.setLayoutMode("expert")
    })

    expect(result.current.showPromotionToast).toBe(false)
  })
})
