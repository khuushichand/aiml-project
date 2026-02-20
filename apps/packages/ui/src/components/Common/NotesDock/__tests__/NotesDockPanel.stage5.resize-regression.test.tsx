import React from "react"
import { act, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NotesDockPanel } from "../NotesDockPanel"
import { useNotesDockStore } from "@/store/notes-dock"

const {
  mockBgRequest,
  mockNavigate,
  stableTranslate,
  stableMessageApi
} = vi.hoisted(() => ({
  mockBgRequest: vi.fn(),
  mockNavigate: vi.fn(),
  stableTranslate: (
    key: string,
    defaultValueOrOptions?:
      | string
      | {
          defaultValue?: string
          [key: string]: unknown
        }
  ) => {
    if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
    if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
    return key
  },
  stableMessageApi: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: stableTranslate
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasNotes: true },
    loading: false
  })
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => stableMessageApi
}))

class ResizeObserverMock {
  static instance: ResizeObserverMock | null = null
  callback: ResizeObserverCallback
  target: Element | null = null

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
    ResizeObserverMock.instance = this
  }

  observe(target: Element) {
    this.target = target
  }

  unobserve() {}

  disconnect() {}

  emit(entry: {
    contentWidth: number
    contentHeight: number
    borderWidth: number
    borderHeight: number
  }) {
    if (!this.target) return
    const payload = {
      target: this.target,
      contentRect: {
        width: entry.contentWidth,
        height: entry.contentHeight
      },
      borderBoxSize: [
        {
          inlineSize: entry.borderWidth,
          blockSize: entry.borderHeight
        }
      ]
    } as unknown as ResizeObserverEntry
    this.callback([payload], this as unknown as ResizeObserver)
  }
}

describe("NotesDockPanel stage 5 resize regression", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ResizeObserverMock.instance = null
    vi.stubGlobal("ResizeObserver", ResizeObserverMock as any)
    mockBgRequest.mockResolvedValue({ items: [], pagination: { total_items: 0, total_pages: 1 } })

    useNotesDockStore.setState({
      isOpen: true,
      position: { x: 24, y: 80 },
      size: { width: 640, height: 520 },
      notes: [],
      activeNoteId: null
    })
  })

  afterEach(() => {
    useNotesDockStore.setState({
      isOpen: false,
      notes: [],
      activeNoteId: null
    })
    vi.unstubAllGlobals()
  })

  it("does not shrink to content-box dimensions on initial observer callback", async () => {
    render(<NotesDockPanel />)

    await waitFor(() => {
      expect(ResizeObserverMock.instance).not.toBeNull()
    })

    act(() => {
      ResizeObserverMock.instance?.emit({
        contentWidth: 638,
        contentHeight: 518,
        borderWidth: 640,
        borderHeight: 520
      })
    })

    await waitFor(() => {
      expect(useNotesDockStore.getState().size).toEqual({ width: 640, height: 520 })
    })
  })
})
