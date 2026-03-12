import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useResizablePanel } from "@/hooks/document-workspace/useResizablePanel"

describe("useResizablePanel", () => {
  beforeEach(() => {
    vi.spyOn(Storage.prototype, "getItem").mockReturnValue(null)
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("inverts drag direction for left-edge handles", () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        key: "right-panel",
        defaultWidth: 320,
        min: 240,
        max: 480,
        edge: "left"
      })
    )

    act(() => {
      result.current.handleMouseDown({
        preventDefault: vi.fn(),
        clientX: 400
      } as unknown as React.MouseEvent)
    })

    act(() => {
      document.dispatchEvent(new MouseEvent("mousemove", { clientX: 360 }))
    })

    expect(result.current.width).toBe(360)

    act(() => {
      document.dispatchEvent(new MouseEvent("mousemove", { clientX: 440 }))
    })

    expect(result.current.width).toBe(280)

    act(() => {
      document.dispatchEvent(new MouseEvent("mouseup"))
    })
  })

  it("applies updated edge configuration after rerender", () => {
    const { result, rerender } = renderHook(
      ({ edge }: { edge: "left" | "right" }) =>
        useResizablePanel({
          key: "panel",
          defaultWidth: 300,
          min: 200,
          max: 400,
          edge
        }),
      {
        initialProps: { edge: "right" as const }
      }
    )

    rerender({ edge: "left" })

    act(() => {
      result.current.handleMouseDown({
        preventDefault: vi.fn(),
        clientX: 250
      } as unknown as React.MouseEvent)
    })

    act(() => {
      document.dispatchEvent(new MouseEvent("mousemove", { clientX: 230 }))
    })

    expect(result.current.width).toBe(320)
  })

  it("warns when reading the persisted width from localStorage fails", () => {
    const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined)
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage blocked")
    })

    const { result } = renderHook(() =>
      useResizablePanel({
        key: "left-panel",
        defaultWidth: 280,
        min: 240,
        max: 480
      })
    )

    expect(result.current.width).toBe(280)
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "Failed to read panel width from localStorage for document-workspace-panel-left-panel:",
      expect.any(Error)
    )
  })

  it("warns when persisting the width to localStorage fails", () => {
    const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined)
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded")
    })

    renderHook(() =>
      useResizablePanel({
        key: "right-panel",
        defaultWidth: 320,
        min: 240,
        max: 480
      })
    )

    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "Failed to persist panel width to localStorage for document-workspace-panel-right-panel:",
      expect.any(Error)
    )
  })
})
