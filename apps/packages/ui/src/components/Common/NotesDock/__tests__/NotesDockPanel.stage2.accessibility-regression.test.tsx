import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import axe from "axe-core"
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

const runA11yRules = async (context: Element, ruleIds: string[]) =>
  axe.run(context, {
    runOnly: {
      type: "rule",
      values: ruleIds
    },
    resultTypes: ["violations"]
  })

const CORE_RULES = [
  "aria-required-attr",
  "aria-valid-attr",
  "aria-valid-attr-value",
  "button-name",
  "link-name"
]

const DIALOG_RULES = [...CORE_RULES, "aria-dialog-name"]

describe("NotesDockPanel stage 2 accessibility regression", () => {
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
          keywords: ["research"],
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

  it("has no core aria/name violations in baseline dock and unsaved-modal states", async () => {
    const { container } = render(<NotesDockPanel />)

    const dockResults = await runA11yRules(container, CORE_RULES)
    expect(dockResults.violations).toEqual([])

    fireEvent.click(screen.getByTestId("notes-dock-close-button"))
    const modalBody = await screen.findByTestId("notes-dock-unsaved-modal-body")
    const modalRoot = modalBody.closest(".ant-modal-root") || document.body

    const modalResults = await runA11yRules(modalRoot, DIALOG_RULES)
    expect(modalResults.violations).toEqual([])

    fireEvent.click(screen.getByTestId("notes-dock-unsaved-cancel-button"))
    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: "Unsaved notes" }).className).toContain(
        "ant-zoom-leave"
      )
    })
  })
})
