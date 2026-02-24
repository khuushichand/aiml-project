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

const getRenderedRowOrder = (): number[] =>
  screen
    .getAllByTestId(/watchlists-item-row-\d+/)
    .map((element) => Number(element.getAttribute("data-testid")?.split("-").at(-1)))

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

    fireEvent.click(screen.getByTestId("watchlists-items-smart-feed-reviewed"))
    await waitFor(() => {
      expect(useWatchlistsStore.getState().itemsSmartFilter).toBe("reviewed")
    })

    const sortSelect = screen.getByTestId("watchlists-items-sort-select")
    fireEvent.mouseDown(sortSelect)
    fireEvent.click(await screen.findByText("Unread first"))

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
      expect(raw).toContain("\"sortMode\":\"unreadFirst\"")
    })

    fireEvent.click(screen.getByTestId("watchlists-items-smart-feed-all"))
    await waitFor(() => {
      expect(useWatchlistsStore.getState().itemsSmartFilter).toBe("all")
    })

    fireEvent.change(searchInput, { target: { value: "beta" } })
    fireEvent.mouseDown(sortSelect)
    fireEvent.click(await screen.findByText("Newest first"))

    const presetsSelect = screen.getByTestId("watchlists-items-view-presets-select")
    fireEvent.mouseDown(presetsSelect)
    fireEvent.click(await screen.findByText("Triage Alpha"))
    expect(searchInput).toHaveValue("alpha")
    expect(sortSelect).toHaveTextContent("Unread first")
    expect(useWatchlistsStore.getState().itemsSmartFilter).toBe("reviewed")

    fireEvent.click(screen.getByTestId("watchlists-items-view-delete"))
    await waitFor(() => {
      const raw = window.localStorage.getItem(ITEMS_VIEW_PRESETS_STORAGE_KEY)
      expect(raw).toContain("system-unread-today")
      expect(raw).toContain("system-high-priority")
      expect(raw).toContain("system-needs-review")
      expect(raw).not.toContain("Triage Alpha")
    })
  })

  it("reorders rows when sort mode changes", async () => {
    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(getRenderedRowOrder()).toEqual([103, 102, 101])
    })

    const sortSelect = screen.getByTestId("watchlists-items-sort-select")
    fireEvent.mouseDown(sortSelect)
    fireEvent.click(await screen.findByText("Unread first"))
    await waitFor(() => {
      expect(getRenderedRowOrder()).toEqual([102, 101, 103])
    })

    fireEvent.mouseDown(sortSelect)
    fireEvent.click(await screen.findByText("Oldest first"))
    await waitFor(() => {
      expect(getRenderedRowOrder()).toEqual([101, 102, 103])
    })

    fireEvent.mouseDown(sortSelect)
    fireEvent.click(await screen.findByText("Reviewed first"))
    await waitFor(() => {
      expect(getRenderedRowOrder()).toEqual([103, 102, 101])
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

  it("keeps include-in-briefing action stateful as items transition to ingested", async () => {
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
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-item-row-101"))
    expect(screen.getByTestId("watchlists-item-include-briefing")).toBeDisabled()

    fireEvent.click(screen.getByTestId("watchlists-item-row-103"))
    const includeButton = screen.getByTestId("watchlists-item-include-briefing")
    expect(includeButton).not.toBeDisabled()
    fireEvent.click(includeButton)

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(103, { status: "ingested" })
    })
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith("Added to the next briefing queue.")
    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-include-briefing")).toBeDisabled()
    })
  })

  it("marks all filtered items as reviewed with scoped confirmation messaging", async () => {
    const largeUnreadSet = Array.from({ length: 45 }, (_value, index) => ({
      id: 500 + index,
      run_id: 9,
      job_id: 3,
      source_id: 1,
      url: `https://example.com/${500 + index}`,
      title: `Bulk Item ${500 + index}`,
      summary: `Summary ${500 + index}`,
      tags: ["ops"],
      status: "ingested",
      reviewed: false,
      created_at: "2026-02-18T10:00:00Z",
      published_at: "2026-02-18T10:00:00Z"
    }))
    setupFetchScrapedItemsMock(largeUnreadSet)
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number) => ({
      id: itemId,
      reviewed: true
    }))

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-500")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-items-mark-all-filtered"))

    await waitFor(() => {
      expect(uiMocks.modalConfirm).toHaveBeenCalled()
    })
    const confirmConfig = uiMocks.modalConfirm.mock.calls[0]?.[0] as Record<string, unknown>
    expect(confirmConfig?.title).toBe("Mark all filtered items as reviewed?")
    expect(confirmConfig?.content).toBe(
      "Scope: all filtered items. This will mark 45 items as reviewed."
    )

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledTimes(45)
    })
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith(
      "Marked 45 all filtered items as reviewed."
    )
  })

  it("shows partial-failure feedback and keeps failed selections for retry", async () => {
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number) => {
      if (itemId === 102) {
        throw new Error("update failed")
      }
      return { id: itemId, reviewed: true }
    })

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-item-select-101"))
    fireEvent.click(screen.getByTestId("watchlists-item-select-102"))
    fireEvent.click(screen.getByTestId("watchlists-items-mark-selected"))

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(101, { reviewed: true })
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(102, { reviewed: true })
    })

    expect(uiMocks.messageWarning).toHaveBeenCalledWith(
      "Marked 1 selected item as reviewed; 1 failed."
    )
    expect(screen.getByTestId("watchlists-item-row-review-state-101")).toHaveTextContent("Reviewed")
    expect(screen.getByTestId("watchlists-item-row-review-state-102")).toHaveTextContent("Unread")
    expect(screen.getByTestId("watchlists-items-selected-count")).toHaveTextContent("1 selected")
  })

  it("handles high-volume all-filtered review operations", async () => {
    const largeUnreadSet = Array.from({ length: 240 }, (_value, index) => ({
      id: 800 + index,
      run_id: 9,
      job_id: 3,
      source_id: 1,
      url: `https://example.com/${800 + index}`,
      title: `Large Item ${800 + index}`,
      summary: `Summary ${800 + index}`,
      tags: ["ops"],
      status: "ingested",
      reviewed: false,
      created_at: "2026-02-18T10:00:00Z",
      published_at: "2026-02-18T10:00:00Z"
    }))
    setupFetchScrapedItemsMock(largeUnreadSet)
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number) => ({
      id: itemId,
      reviewed: true
    }))

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-800")).toBeInTheDocument()
    })

    const start = performance.now()
    fireEvent.click(screen.getByTestId("watchlists-items-mark-all-filtered"))

    await waitFor(
      () => {
        expect(serviceMocks.updateScrapedItem).toHaveBeenCalledTimes(240)
      },
      { timeout: 15000 }
    )
    expect(uiMocks.messageSuccess).toHaveBeenCalledWith(
      "Marked 240 all filtered items as reviewed."
    )
    expect(performance.now() - start).toBeLessThan(15000)
  })

  it("surfaces in-progress batch status and completion summary for high-volume operations", async () => {
    const largeUnreadSet = Array.from({ length: 45 }, (_value, index) => ({
      id: 900 + index,
      run_id: 9,
      job_id: 3,
      source_id: 1,
      url: `https://example.com/${900 + index}`,
      title: `Progress Item ${900 + index}`,
      summary: `Summary ${900 + index}`,
      tags: ["ops"],
      status: "ingested",
      reviewed: false,
      created_at: "2026-02-18T10:00:00Z",
      published_at: "2026-02-18T10:00:00Z"
    }))
    setupFetchScrapedItemsMock(largeUnreadSet)

    let callCount = 0
    const firstChunkResolvers: Array<() => void> = []
    serviceMocks.updateScrapedItem.mockImplementation((itemId: number) => {
      callCount += 1
      if (callCount <= 20) {
        return new Promise((resolve) => {
          firstChunkResolvers.push(() => resolve({ id: itemId, reviewed: true }))
        })
      }
      return Promise.resolve({ id: itemId, reviewed: true })
    })

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-900")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-items-mark-all-filtered"))

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledTimes(20)
    })

    expect(screen.getByTestId("watchlists-items-batch-progress-panel")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-items-batch-progress-count")).toHaveTextContent("0 / 45")
    expect(screen.getByTestId("watchlists-items-batch-progress-summary")).toHaveTextContent(
      "Running all filtered items..."
    )

    firstChunkResolvers.forEach((resolve) => resolve())

    await waitFor(
      () => {
        expect(serviceMocks.updateScrapedItem).toHaveBeenCalledTimes(45)
      },
      { timeout: 15000 }
    )
    await waitFor(() => {
      expect(screen.getByTestId("watchlists-items-batch-progress-summary")).toHaveTextContent(
        "Completed 45 of 45. 0 failed."
      )
    })
  })

  it("offers retry for failed batch items and reconciles selection after successful retry", async () => {
    let shouldFail102 = true
    serviceMocks.updateScrapedItem.mockImplementation(async (itemId: number) => {
      if (itemId === 102 && shouldFail102) {
        shouldFail102 = false
        throw new Error("update failed")
      }
      return { id: itemId, reviewed: true }
    })

    render(<ItemsTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-101")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-item-select-101"))
    fireEvent.click(screen.getByTestId("watchlists-item-select-102"))
    fireEvent.click(screen.getByTestId("watchlists-items-mark-selected"))

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(101, { reviewed: true })
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(102, { reviewed: true })
    })

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-items-batch-progress-summary")).toHaveTextContent(
        "Completed 1 of 2. 1 failed."
      )
    })

    const retryButton = screen.getByTestId("watchlists-items-batch-retry-failed")
    fireEvent.click(retryButton)

    await waitFor(() => {
      expect(serviceMocks.updateScrapedItem).toHaveBeenCalledWith(102, { reviewed: true })
    })
    await waitFor(() => {
      expect(screen.getByTestId("watchlists-item-row-review-state-102")).toHaveTextContent(
        "Reviewed"
      )
    })

    expect(screen.getByTestId("watchlists-items-selected-count")).toHaveTextContent("0 selected")
    expect(screen.getByTestId("watchlists-items-batch-progress-summary")).toHaveTextContent(
      "Completed 1 of 1. 0 failed."
    )
  })
})
