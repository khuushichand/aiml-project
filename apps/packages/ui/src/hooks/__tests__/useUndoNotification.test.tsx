import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { useUndoNotification } from "../useUndoNotification"

const mocks = vi.hoisted(() => ({
  notificationOpen: vi.fn(),
  notificationDestroy: vi.fn(),
  notificationSuccess: vi.fn(),
  notificationError: vi.fn(),
}))

vi.mock("antd", () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
  }),
}))

vi.mock("../useAntdNotification", () => ({
  useAntdNotification: () => ({
    open: mocks.notificationOpen,
    destroy: mocks.notificationDestroy,
    success: mocks.notificationSuccess,
    error: mocks.notificationError,
  }),
}))

describe("useUndoNotification", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("runs onDismiss when notification closes without undo", () => {
    const onDismiss = vi.fn()
    const onUndo = vi.fn()

    const { result } = renderHook(() => useUndoNotification())
    let key = ""

    act(() => {
      key = result.current.showUndoNotification({
        title: "Deleted",
        description: "Undo available for 10 seconds.",
        duration: 10,
        onUndo,
        onDismiss,
      })
    })

    expect(key).toContain("undo-")
    expect(mocks.notificationOpen).toHaveBeenCalledTimes(1)
    const notificationConfig = mocks.notificationOpen.mock.calls[0][0]
    expect(notificationConfig.duration).toBe(10)

    act(() => {
      notificationConfig.onClose?.()
    })

    expect(onDismiss).toHaveBeenCalledTimes(1)
    expect(onUndo).not.toHaveBeenCalled()
  })

  it("executes undo callback and suppresses onDismiss after undo click", async () => {
    const onDismiss = vi.fn()
    const onUndo = vi.fn(async () => undefined)

    const { result } = renderHook(() => useUndoNotification())
    let key = ""

    act(() => {
      key = result.current.showUndoNotification({
        title: "Deleted",
        onUndo,
        onDismiss,
      })
    })

    const notificationConfig = mocks.notificationOpen.mock.calls[0][0]
    await act(async () => {
      await notificationConfig.btn.props.onClick()
    })

    expect(onUndo).toHaveBeenCalledTimes(1)
    expect(mocks.notificationDestroy).toHaveBeenCalledWith(key)
    expect(mocks.notificationSuccess).toHaveBeenCalledTimes(1)
    expect(mocks.notificationError).not.toHaveBeenCalled()

    act(() => {
      notificationConfig.onClose?.()
    })
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it("shows error notification when undo callback fails", async () => {
    const onUndo = vi.fn(async () => {
      throw new Error("Restore failed")
    })

    const { result } = renderHook(() => useUndoNotification())

    act(() => {
      result.current.showUndoNotification({
        title: "Deleted",
        onUndo,
      })
    })

    const notificationConfig = mocks.notificationOpen.mock.calls[0][0]
    await act(async () => {
      await notificationConfig.btn.props.onClick()
    })

    expect(mocks.notificationError).toHaveBeenCalledTimes(1)
    expect(mocks.notificationSuccess).not.toHaveBeenCalled()
  })
})
