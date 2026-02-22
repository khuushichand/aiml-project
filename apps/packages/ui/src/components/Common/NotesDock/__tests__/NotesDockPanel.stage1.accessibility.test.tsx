import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe("NotesDockPanel stage 1 accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("ResizeObserver", ResizeObserverMock as any)
    mockBgRequest.mockResolvedValue({ items: [], pagination: { total_items: 0, total_pages: 1 } })

    useNotesDockStore.setState({
      isOpen: true,
      position: { x: 24, y: 80 },
      size: { width: 640, height: 520 },
      notes: [
        {
          localId: "local-1",
          title: "Dirty dock note",
          content: "Unsaved content",
          keywords: [],
          version: null,
          snapshot: null,
          isDirty: true
        }
      ],
      activeNoteId: "local-1"
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

  it("closes unsaved modal with Cancel and restores focus to dock close trigger", async () => {
    render(<NotesDockPanel />)

    const closeButton = screen.getByTestId("notes-dock-close-button")
    closeButton.focus()
    fireEvent.click(closeButton)

    await screen.findByTestId("notes-dock-unsaved-modal-body")
    fireEvent.click(screen.getByTestId("notes-dock-unsaved-cancel-button"))

    const unsavedDialog = screen.getByRole("dialog", { name: "Unsaved notes" })
    await waitFor(() => {
      expect(unsavedDialog.className).toContain("ant-zoom-leave")
    })
    await waitFor(() => {
      expect(closeButton).toHaveFocus()
    })
  })
})
