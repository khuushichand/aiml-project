import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useCollectionsStore } from "@/store/collections"
import { ImportExportPanel } from "../ImportExportPanel"

const apiMock = vi.hoisted(() => ({
  getReadingList: vi.fn(),
  getReadingItem: vi.fn(),
  getHighlights: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) => {
  if (!values) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = values[token]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string } | Record<string, unknown>,
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return interpolate(fallbackOrOptions, maybeOptions)
      }
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        const maybeDefault = (fallbackOrOptions as { defaultValue?: string }).defaultValue
        if (typeof maybeDefault === "string") {
          return interpolate(maybeDefault, maybeOptions)
        }
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => apiMock
}))

describe("ImportExportPanel filename hints", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    if (!window.matchMedia) {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn()
        }))
      })
    }

    useCollectionsStore.getState().resetStore()

    apiMock.getReadingList.mockResolvedValue({
      items: [
        {
          id: "item-1",
          title: "Article A",
          favorite: false,
          tags: []
        }
      ],
      total: 1,
      page: 1,
      size: 200
    })
  })

  it("shows selection filename hint when export items are selected", async () => {
    render(<ImportExportPanel />)

    const option = await screen.findByRole("option", { name: /Article A/i })
    fireEvent.click(option)

    await waitFor(() => {
      const hint = screen.getByTestId("export-filename-hint")
      expect(hint.textContent).toContain("reading_export_selection.jsonl")
      expect(hint.textContent).toContain("Scope: selected items")
    })
  })

  it("shows filtered jsonl filename hint when date filters are active", async () => {
    useCollectionsStore.getState().setFilterDateRange("2026-01-01", "2026-01-31")

    render(<ImportExportPanel />)

    await waitFor(() => {
      const hint = screen.getByTestId("export-filename-hint")
      expect(hint.textContent).toContain("reading_export_filtered.jsonl")
      expect(hint.textContent).toContain("Scope: filtered list")
    })
  })

  it("shows timestamped zip filename hint when zip format is selected", async () => {
    useCollectionsStore.getState().setExportFormat("zip")

    render(<ImportExportPanel />)

    await waitFor(() => {
      const hint = screen.getByTestId("export-filename-hint")
      expect(hint.textContent).toContain("reading_export_<timestamp>.zip")
      expect(hint.textContent).toContain("Scope: filtered list")
    })
  })

  it("renders top import errors and truncates overflow with a summary line", async () => {
    useCollectionsStore.getState().setImportWizardStep("result")
    useCollectionsStore.getState().setImportResult({
      imported: 3,
      updated: 1,
      skipped: 2,
      errors: [
        "bad row 1",
        "bad row 2",
        "bad row 3",
        "bad row 4",
        "bad row 5",
        "bad row 6",
        "bad row 7"
      ]
    })

    render(<ImportExportPanel />)

    expect(await screen.findByText("Top import errors")).toBeTruthy()
    expect(screen.getByText("bad row 1")).toBeTruthy()
    expect(screen.getByText("bad row 5")).toBeTruthy()
    expect(screen.queryByText("bad row 6")).toBeNull()
    expect(screen.getByText("+2 more errors")).toBeTruthy()
  })
})
