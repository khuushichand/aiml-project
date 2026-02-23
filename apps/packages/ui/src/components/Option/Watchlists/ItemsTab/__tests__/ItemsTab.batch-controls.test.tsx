// @vitest-environment jsdom

import React from "react"
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { ItemsTab } from "../ItemsTab"
import { useWatchlistsStore } from "@/store/watchlists"
import { ITEMS_PAGE_SIZE_STORAGE_KEY, ITEMS_VIEW_PRESETS_STORAGE_KEY } from "../items-utils"

const serviceMocks = vi.hoisted(() => ({
  fetchWatchlistSources: vi.fn(),
  fetchScrapedItems: vi.fn(),
  updateScrapedItem: vi.fn()
}))

const uiMocks = vi.hoisted(() => ({
  modalConfirm: vi.fn(),
  messageSuccess: vi.fn(),
  messageInfo: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) => {
  if (!values) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = values[token]
    return value == null ? "" : String(value)
  })
}

const stableTranslate = (
  key: string,
  fallbackOrOptions?: string | { defaultValue?: string },
  maybeOptions?: Record<string, unknown>
) => {
  if (typeof fallbackOrOptions === "string") {
    return interpolate(fallbackOrOptions, maybeOptions)
  }
  if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
    const maybeDefault = fallbackOrOptions.defaultValue
    if (typeof maybeDefault === "string") {
      return interpolate(maybeDefault, maybeOptions)
    }
  }
  return key
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: stableTranslate
  })
}))

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd")
  const mockedModal = Object.assign(actual.Modal, {
    confirm: (config: Record<string, unknown>) => uiMocks.modalConfirm(config)
  })
  return {
    ...actual,
    Modal: mockedModal,
    message: {
      success: (...args: unknown[]) => uiMocks.messageSuccess(...args),
      info: (...args: unknown[]) => uiMocks.messageInfo(...args),
      warning: (...args: unknown[]) => uiMocks.messageWarning(...args),
      error: (...args: unknown[]) => uiMocks.messageError(...args)
    }
  }
})

vi.mock("@/services/watchlists", () => ({
  fetchWatchlistSources: (...args: unknown[]) => serviceMocks.fetchWatchlistSources(...args),
  fetchScrapedItems: (...args: unknown[]) => serviceMocks.fetchScrapedItems(...args),
  updateScrapedItem: (...args: unknown[]) => serviceMocks.updateScrapedItem(...args)
}))

const makeItems = () => ([
  {
    id: 101,
    run_id: 1,
    job_id: 1,
    source_id: 1,
    url: "https://example.com/one",
    title: "Item One",
    summary: "Summary one",
    tags: ["tech"],
    status: "ingested",
    reviewed: false,
    created_at: "2026-02-18T08:00:00Z",
    published_at: "2026-02-18T08:00:00Z"
  },
  {
    id: 102,
    run_id: 1,
    job_id: 1,
    source_id: 1,
    url: "https://example.com/two",
    title: "Item Two",
    summary: "Summary two",
    tags: ["tech"],
    status: "ingested",
    reviewed: false,
    created_at: "2026-02-18T08:10:00Z",
    published_at: "2026-02-18T08:10:00Z"
  },
  {
    id: 103,
    run_id: 1,
    job_id: 1,
    source_id: 1,
    url: "https://example.com/three",
    title: "Item Three",
    summary: "Summary three",
    tags: ["tech"],
    status: "filtered",
    reviewed: true,
    created_at: "2026-02-18T08:20:00Z",
    published_at: "2026-02-18T08:20:00Z"
  }
])

const setupFetchScrapedItemsMock = (listItems = makeItems()) => {
  ;(serviceMocks.fetchScrapedItems as Mock).mockImplementation(async (params?: Record<string, unknown>) => {
    if (params?.size === 1) {
      if (params?.reviewed === false) return { items: [], total: 2, page: 1, size: 1, has_more: false }
      if (params?.reviewed === true) return { items: [], total: 1, page: 1, size: 1, has_more: false }
      return { items: [], total: 3, page: 1, size: 1, has_more: false }
    }

    if (params?.reviewed === false && params?.size === 200) {
      return {
        items: listItems.filter((item) => !item.reviewed),
        total: listItems.filter((item) => !item.reviewed).length,
        page: Number(params?.page || 1),
        size: 200,
        has_more: false
      }
    }

    const pageSize = Number(params?.size || 25)
    return {
      items: listItems,
      total: listItems.length,
      page: Number(params?.page || 1),
      size: pageSize,
      has_more: false
    }
  })
}

describe("ItemsTab batch throughput controls", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    useWatchlistsStore.getState().resetStore()

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

    serviceMocks.fetchWatchlistSources.mockResolvedValue({
      items: [
        {
          id: 1,
          name: "Tech Daily",
          url: "https://example.com/rss.xml",
          source_type: "rss",
          active: true,
          tags: ["tech"],
          created_at: "2026-02-18T07:00:00Z",
          updated_at: "2026-02-18T07:00:00Z",
          last_scraped_at: "2026-02-18T08:00:00Z",
          status: "healthy"
        }
      ],
      total: 1,
      page: 1,
      size: 200,
      has_more: false
    })

    setupFetchScrapedItemsMock()
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number) => ({
      id: itemId,
      reviewed: true
    }))

    uiMocks.modalConfirm.mockImplementation((config: Record<string, unknown>) => {
      const onOk = config?.onOk
      if (typeof onOk === "function") {
        return Promise.resolve(onOk())
      }
      return undefined
    })
  })

  it("enables mark-selected only when selection exists and confirms before applying", async () => {
    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    expect(screen.getByTestId("watchlists-item-row-review-state-101")).toHaveTextContent("Unread")
    expect(screen.getByTestId("watchlists-item-row-review-state-103")).toHaveTextContent("Reviewed")

    expect(screen.getByTestId("watchlists-items-batch-scope-summary")).toHaveTextContent(
      "Selected: 0 unread"
    )

    const markSelectedButton = screen.getByTestId("watchlists-items-mark-selected")
    expect(markSelectedButton).toBeDisabled()
    expect(screen.getByTestId("watchlists-items-selected-count")).toHaveTextContent("0 selected")

    fireEvent.click(screen.getByTestId("watchlists-item-select-101"))
    expect(markSelectedButton).not.toBeDisabled()
    expect(screen.getByTestId("watchlists-items-selected-count")).toHaveTextContent("1 selected")

    fireEvent.click(markSelectedButton)

    await waitFor(() => {
      expect(uiMocks.modalConfirm).toHaveBeenCalled()
    })

    const confirmConfig = uiMocks.modalConfirm.mock.calls[0]?.[0] as Record<string, unknown>
    expect(confirmConfig?.title).toBe("Mark selected items as reviewed?")
    expect(confirmConfig?.content).toBe(
      "Scope: selected item. This will mark 1 item as reviewed."
    )

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(101, { reviewed: true })
    })
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith("Marked 1 selected item as reviewed.")
  })

  it("respects persisted page-size, supports mark-page, and persists changed size", async () => {
    window.localStorage.setItem(ITEMS_PAGE_SIZE_STORAGE_KEY, "50")
    render(<ItemsTab />)

    await waitFor(() => {
      expect(serviceMocks.fetchScrapedItems).toHaveBeenCalled()
    })

    expect(serviceMocks.fetchScrapedItems).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        size: 50
      })
    )

    fireEvent.click(screen.getByTestId("watchlists-items-mark-page"))
    await waitFor(() => {
      expect(uiMocks.modalConfirm).toHaveBeenCalled()
    })

    const confirmConfig = uiMocks.modalConfirm.mock.calls[0]?.[0] as Record<string, unknown>
    expect(confirmConfig?.title).toBe("Mark this page as reviewed?")
    expect(confirmConfig?.content).toBe(
      "Scope: items on this page. This will mark 2 items as reviewed."
    )

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(101, { reviewed: true })
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(102, { reviewed: true })
    })
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith(
      "Marked 2 items on this page as reviewed."
    )

    const pageSizeSelect = screen.getByTestId("watchlists-items-page-size-select")
    fireEvent.mouseDown(pageSizeSelect)
    fireEvent.click(await screen.findByText("20 / page"))

    await waitFor(() => {
      expect(serviceMocks.fetchScrapedItems).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          size: 20
        })
      )
    })

    expect(window.localStorage.getItem(ITEMS_PAGE_SIZE_STORAGE_KEY)).toBe("20")
  })

  it("supports saved view preset save, apply, and delete", async () => {
    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText("Search feed items...")
    fireEvent.change(searchInput, { target: { value: "alpha" } })

    fireEvent.click(screen.getByTestId("watchlists-items-view-save"))
    const nameInput = await screen.findByTestId("watchlists-items-view-name-input")
    fireEvent.change(nameInput, { target: { value: "Triage Alpha" } })
    const saveButtons = screen.getAllByRole("button", { name: "Save view" })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => {
      const raw = window.localStorage.getItem(ITEMS_VIEW_PRESETS_STORAGE_KEY)
      expect(raw).toContain("Triage Alpha")
    })

    fireEvent.change(searchInput, { target: { value: "beta" } })
    const presetsSelect = screen.getByTestId("watchlists-items-view-presets-select")
    fireEvent.mouseDown(presetsSelect)
    fireEvent.click(await screen.findByText("Triage Alpha"))
    expect(searchInput).toHaveValue("alpha")

    fireEvent.click(screen.getByTestId("watchlists-items-view-delete"))
    await waitFor(() => {
      const raw = window.localStorage.getItem(ITEMS_VIEW_PRESETS_STORAGE_KEY)
      expect(raw).toContain("system-unread-today")
      expect(raw).toContain("system-high-priority")
      expect(raw).toContain("system-needs-review")
      expect(raw).not.toContain("Triage Alpha")
    })
  })

  it("supports item handoff to monitor/run/reports and include-next-briefing action", async () => {
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number, updates?: Record<string, unknown>) => {
      const item = makeItems().find((entry) => entry.id === itemId)
      return {
        ...(item || { id: itemId }),
        reviewed: Boolean(updates?.reviewed ?? item?.reviewed),
        status: typeof updates?.status === "string" ? updates.status : item?.status
      }
    })

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-103")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-item-row-103"))
    fireEvent.click(screen.getByTestId("watchlists-item-include-briefing"))

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(103, { status: "ingested" })
    })
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith("Added to the next briefing queue.")

    fireEvent.click(screen.getByTestId("watchlists-item-jump-monitor"))
    expect(useWatchlistsStore.getState().activeTab).toBe("jobs")
    expect(useWatchlistsStore.getState().jobFormOpen).toBe(true)
    expect(useWatchlistsStore.getState().jobFormEditId).toBe(1)

    fireEvent.click(screen.getByTestId("watchlists-item-jump-run"))
    expect(useWatchlistsStore.getState().activeTab).toBe("runs")
    expect(useWatchlistsStore.getState().runsJobFilter).toBe(1)
    expect(useWatchlistsStore.getState().runDetailOpen).toBe(true)
    expect(useWatchlistsStore.getState().selectedRunId).toBe(1)

    fireEvent.click(screen.getByTestId("watchlists-item-jump-outputs"))
    expect(useWatchlistsStore.getState().activeTab).toBe("outputs")
    expect(useWatchlistsStore.getState().outputsJobFilter).toBe(1)
    expect(useWatchlistsStore.getState().outputsRunFilter).toBe(1)
  })
})
