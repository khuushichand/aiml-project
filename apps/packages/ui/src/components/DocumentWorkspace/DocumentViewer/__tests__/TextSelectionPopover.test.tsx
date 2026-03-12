import React from "react"
import { act, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { TextSelectionPopover } from "../TextSelectionPopover"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

const { rafState, messageApi } = vi.hoisted(() => ({
  rafState: {
    callbacks: new Map<number, FrameRequestCallback>(),
    nextId: 1
  },
  messageApi: {
    success: vi.fn(),
    error: vi.fn()
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

vi.mock("@/hooks/document-workspace/useTranslate", () => ({
  useTranslate: () => ({
    mutateAsync: vi.fn(),
    isPending: false
  })
}))

vi.mock("@/hooks/document-workspace/useDocumentTTS", () => ({
  useDocumentTTS: () => ({
    speak: vi.fn(),
    stop: vi.fn(),
    state: {
      isPlaying: false,
      currentText: "",
      isLoading: false
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => false
}))

vi.mock("antd", () => ({
  Button: ({ children, icon, className, loading: _loading, ...props }: any) => (
    <button className={className} {...props}>
      {icon}
      {children}
    </button>
  ),
  Dropdown: ({ children }: any) => <div>{children}</div>,
  Modal: ({ open, children }: any) => (open ? <div>{children}</div> : null),
  Spin: () => <div>Loading</div>,
  Select: ({ value, onChange, options = [] }: any) => (
    <select value={value} onChange={(event) => onChange?.(event.target.value)}>
      {options.map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
  message: messageApi
}))

function flushAnimationFrames() {
  const callbacks = [...rafState.callbacks.values()]
  rafState.callbacks.clear()
  callbacks.forEach((callback) => callback(performance.now()))
}

describe("TextSelectionPopover", () => {
  beforeEach(() => {
    rafState.callbacks.clear()
    rafState.nextId = 1
    messageApi.success.mockReset()
    messageApi.error.mockReset()
    useDocumentWorkspaceStore.getState().reset()

    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      const id = rafState.nextId++
      rafState.callbacks.set(id, callback)
      return id
    })
    vi.stubGlobal("cancelAnimationFrame", (id: number) => {
      rafState.callbacks.delete(id)
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("hides the desktop popover again until the next position calculation is ready", () => {
    const onClose = vi.fn()
    const { container, rerender } = render(
      <TextSelectionPopover
        text="Selected text"
        position={{ x: 120, y: 80 }}
        onClose={onClose}
      />
    )

    const popover = container.querySelector("[data-selection-popover]") as HTMLDivElement

    act(() => {
      flushAnimationFrames()
    })

    expect(popover.style.opacity).toBe("1")
    expect(popover.style.pointerEvents).toBe("auto")

    rerender(
      <TextSelectionPopover
        text="Selected text"
        position={{ x: 260, y: 140 }}
        onClose={onClose}
      />
    )

    expect(popover.style.opacity).toBe("0")
    expect(popover.style.pointerEvents).toBe("none")

    act(() => {
      flushAnimationFrames()
    })

    expect(popover.style.opacity).toBe("1")
    expect(popover.style.pointerEvents).toBe("auto")
    expect(popover.style.left).toBe("260px")
    expect(popover.style.top).toBe("140px")
  })
})
