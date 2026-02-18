import { act, fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SourcesPane } from "../SourcesPane"
import { WORKSPACE_SOURCE_DRAG_TYPE } from "../drag-source"

const mockToggleSourceSelection = vi.fn()
const mockSelectAllSources = vi.fn()
const mockDeselectAllSources = vi.fn()
const mockSetSourceSearchQuery = vi.fn()
const mockOpenAddSourceModal = vi.fn()
const mockRemoveSource = vi.fn()
const mockClearSourceFocusTarget = vi.fn()

const workspaceStoreState = {
  sources: [
    {
      id: "s1",
      mediaId: 1,
      title: "Source One",
      type: "pdf" as const,
      status: "ready" as const,
      addedAt: new Date("2026-02-18T00:00:00.000Z")
    },
    {
      id: "s2",
      mediaId: 2,
      title: "Source Two",
      type: "video" as const,
      status: "processing" as const,
      addedAt: new Date("2026-02-18T00:00:00.000Z")
    }
  ],
  selectedSourceIds: [] as string[],
  sourceSearchQuery: "",
  sourceFocusTarget: null as { sourceId: string; token: number } | null,
  toggleSourceSelection: mockToggleSourceSelection,
  selectAllSources: mockSelectAllSources,
  deselectAllSources: mockDeselectAllSources,
  setSourceSearchQuery: mockSetSourceSearchQuery,
  clearSourceFocusTarget: mockClearSourceFocusTarget,
  openAddSourceModal: mockOpenAddSourceModal,
  removeSource: mockRemoveSource
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return _key
    }
  })
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof workspaceStoreState) => unknown
  ) => selector(workspaceStoreState)
}))

vi.mock("../SourcesPane/AddSourceModal", () => ({
  AddSourceModal: () => <div data-testid="add-source-modal" />
}))

describe("SourcesPane Stage 2 source highlighting", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workspaceStoreState.sourceSearchQuery = ""
    workspaceStoreState.sourceFocusTarget = null

    mockSetSourceSearchQuery.mockImplementation((value: string) => {
      workspaceStoreState.sourceSearchQuery = value
    })
    mockClearSourceFocusTarget.mockImplementation(() => {
      workspaceStoreState.sourceFocusTarget = null
    })
  })

  it("scrolls to and highlights a focused source target", () => {
    vi.useFakeTimers()
    const scrollSpy = vi.fn()
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView
    HTMLElement.prototype.scrollIntoView = scrollSpy

    try {
      workspaceStoreState.sourceFocusTarget = { sourceId: "s2", token: 1 }

      const { container } = render(<SourcesPane />)

      act(() => {
        vi.advanceTimersByTime(0)
      })

      expect(scrollSpy).toHaveBeenCalledTimes(1)
      expect(mockClearSourceFocusTarget).toHaveBeenCalledTimes(1)
      expect(
        container
          .querySelector('[data-source-id="s2"]')
          ?.getAttribute("data-highlighted")
      ).toBe("true")

      act(() => {
        vi.advanceTimersByTime(1800)
      })
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView
      vi.useRealTimers()
    }
  })

  it("clears active source search when focused source is filtered out", () => {
    workspaceStoreState.sourceSearchQuery = "no-match"
    workspaceStoreState.sourceFocusTarget = { sourceId: "s1", token: 2 }

    render(<SourcesPane />)

    expect(mockSetSourceSearchQuery).toHaveBeenCalledWith("")
  })

  it("marks source rows as draggable and sets workspace drag payload", () => {
    render(<SourcesPane />)

    const sourceRow = screen
      .getByText("Source One")
      .closest('[data-source-id="s1"]') as HTMLElement
    expect(sourceRow).toBeTruthy()
    expect(sourceRow).toHaveAttribute("draggable", "true")

    const setData = vi.fn()
    fireEvent.dragStart(sourceRow, {
      dataTransfer: {
        effectAllowed: "",
        setData
      }
    })

    expect(setData).toHaveBeenCalledWith(
      WORKSPACE_SOURCE_DRAG_TYPE,
      expect.stringContaining('"sourceId":"s1"')
    )
    expect(setData).toHaveBeenCalledWith("text/plain", "Source One")
  })

  it("applies touch-friendly hit areas for source selection controls", () => {
    render(<SourcesPane />)

    const checkboxHitArea = screen.getByTestId("source-checkbox-hitarea-s1")
    expect(checkboxHitArea.className).toContain("[@media(hover:none)]:min-h-11")
    expect(checkboxHitArea.className).toContain("[@media(hover:none)]:min-w-11")
  })

  it("keeps remove action visible for keyboard focus and touch devices", () => {
    render(<SourcesPane />)

    const removeButton = screen.getByTestId("remove-source-s1")
    expect(removeButton.className).toContain("focus-visible:opacity-100")
    expect(removeButton.className).toContain("[@media(hover:none)]:opacity-100")
  })

  it("shows processing status and disables selection for non-ready sources", () => {
    render(<SourcesPane />)

    expect(screen.getByText("Processing")).toBeInTheDocument()

    const processingHitArea = screen.getByTestId("source-checkbox-hitarea-s2")
    const checkboxInput = processingHitArea.querySelector(
      "input[type='checkbox']"
    ) as HTMLInputElement | null
    expect(checkboxInput).toBeTruthy()
    expect(checkboxInput?.disabled).toBe(true)
  })
})
