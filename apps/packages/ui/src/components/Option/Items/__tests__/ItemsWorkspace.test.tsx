import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { message, Modal } from "antd"
import { ItemsWorkspace } from "../ItemsWorkspace"

const apiMock = vi.hoisted(() => ({
  getItems: vi.fn(),
  bulkUpdateItems: vi.fn(),
  getOutputTemplates: vi.fn(),
  generateOutput: vi.fn()
}))

const undoNotificationMock = vi.hoisted(() => ({
  showUndoNotification: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => apiMock
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => undoNotificationMock
}))

describe("ItemsWorkspace", () => {
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

    apiMock.getItems.mockResolvedValue({
      items: [
        {
          id: "101",
          title: "Shared Item",
          status: "reading",
          tags: ["research"],
          type: "watchlist"
        }
      ],
      total: 1,
      page: 1,
      size: 25
    })
    apiMock.getOutputTemplates.mockResolvedValue({
      items: [{ id: "77", name: "Briefing", format: "md" }],
      total: 1
    })
    apiMock.generateOutput.mockResolvedValue({ id: "501" })
  })

  afterEach(() => {
    Modal.destroyAll()
    message.destroy()
  })

  it("renders items from shared items endpoint", async () => {
    render(<ItemsWorkspace />)

    await waitFor(() => {
      expect(apiMock.getItems).toHaveBeenCalled()
    })
    expect(await screen.findByText("Shared Item")).toBeTruthy()
  })

  it("generates output from selected item ids", async () => {
    render(<ItemsWorkspace />)

    expect(await screen.findByText("Shared Item")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Select/i }))
    fireEvent.click(screen.getByLabelText("Toggle selection for Shared Item"))
    fireEvent.click(screen.getByRole("button", { name: /Generate output/i }))

    await waitFor(() => {
      expect(apiMock.getOutputTemplates).toHaveBeenCalled()
    })

    await screen.findByText("Generate output for selected items")
    const generateButtons = screen.getAllByRole("button", {
      name: /^Generate output$/i
    })
    expect(generateButtons.length).toBeGreaterThan(1)
    fireEvent.click(generateButtons[generateButtons.length - 1])

    await waitFor(() => {
      expect(apiMock.generateOutput).toHaveBeenCalledWith({
        template_id: "77",
        item_ids: ["101"],
        title: undefined
      })
    })
  })

  it("uses reversible delete by default and restores status via undo", async () => {
    apiMock.bulkUpdateItems
      .mockResolvedValueOnce({
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{ item_id: "101", success: true }]
      })
      .mockResolvedValueOnce({
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{ item_id: "101", success: true }]
      })

    render(<ItemsWorkspace />)
    expect(await screen.findByText("Shared Item")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Select/i }))
    fireEvent.click(screen.getByLabelText("Toggle selection for Shared Item"))
    fireEvent.click(screen.getAllByRole("button", { name: /^Delete$/i })[0])

    const deleteBody = await screen.findByText(
      /Selected items will be moved to archived\. You can undo this action\./i
    )
    const deleteDialog = deleteBody.closest('[role="dialog"]') as HTMLElement
    fireEvent.click(within(deleteDialog).getByRole("button", { name: /^Delete$/i }))

    await waitFor(() => {
      expect(apiMock.bulkUpdateItems).toHaveBeenCalledWith({
        item_ids: ["101"],
        action: "delete",
        hard: false
      })
    })
    expect(undoNotificationMock.showUndoNotification).toHaveBeenCalledTimes(1)

    const undoOptions = undoNotificationMock.showUndoNotification.mock.calls[0][0]
    await undoOptions.onUndo()

    await waitFor(() => {
      expect(apiMock.bulkUpdateItems).toHaveBeenCalledWith({
        item_ids: ["101"],
        action: "set_status",
        status: "reading"
      })
    })
  })

  it("supports deliberate hard delete as a secondary action", async () => {
    apiMock.bulkUpdateItems.mockResolvedValueOnce({
      total: 1,
      succeeded: 1,
      failed: 0,
      results: [{ item_id: "101", success: true }]
    })

    render(<ItemsWorkspace />)
    expect(await screen.findByText("Shared Item")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Select/i }))
    fireEvent.click(screen.getByLabelText("Toggle selection for Shared Item"))
    fireEvent.click(screen.getByRole("button", { name: /Delete permanently/i }))

    const deleteBody = await screen.findByText(
      /This permanently deletes selected items and cannot be undone\. Continue\?/i
    )
    const deleteDialog = deleteBody.closest('[role="dialog"]') as HTMLElement
    fireEvent.click(within(deleteDialog).getByRole("button", { name: /Delete permanently/i }))

    await waitFor(() => {
      expect(apiMock.bulkUpdateItems).toHaveBeenCalledWith({
        item_ids: ["101"],
        action: "delete",
        hard: true
      })
    })
    expect(undoNotificationMock.showUndoNotification).not.toHaveBeenCalled()
  })

  it("keeps undo scoped to successfully deleted items in mixed-result responses", async () => {
    apiMock.getItems.mockResolvedValue({
      items: [
        {
          id: "101",
          title: "Shared Item A",
          status: "reading",
          tags: ["research"],
          type: "watchlist"
        },
        {
          id: "202",
          title: "Shared Item B",
          status: "saved",
          tags: ["research"],
          type: "watchlist"
        }
      ],
      total: 2,
      page: 1,
      size: 25
    })
    apiMock.bulkUpdateItems
      .mockResolvedValueOnce({
        total: 2,
        succeeded: 1,
        failed: 1,
        results: [
          { item_id: "101", success: true },
          { item_id: "202", success: false, error: "item_not_found" }
        ]
      })
      .mockResolvedValueOnce({
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{ item_id: "101", success: true }]
      })

    render(<ItemsWorkspace />)
    expect(await screen.findByText("Shared Item A")).toBeTruthy()
    expect(await screen.findByText("Shared Item B")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Select/i }))
    fireEvent.click(screen.getByRole("checkbox", { name: /Select all on this page/i }))
    fireEvent.click(screen.getAllByRole("button", { name: /^Delete$/i })[0])

    const deleteBody = await screen.findByText(
      /Selected items will be moved to archived\. You can undo this action\./i
    )
    const deleteDialog = deleteBody.closest('[role="dialog"]') as HTMLElement
    fireEvent.click(within(deleteDialog).getByRole("button", { name: /^Delete$/i }))

    await waitFor(() => {
      expect(apiMock.bulkUpdateItems).toHaveBeenCalledWith({
        item_ids: ["101", "202"],
        action: "delete",
        hard: false
      })
    })
    expect(undoNotificationMock.showUndoNotification).toHaveBeenCalledTimes(1)

    const undoOptions = undoNotificationMock.showUndoNotification.mock.calls[0][0]
    await undoOptions.onUndo()

    await waitFor(() => {
      expect(apiMock.bulkUpdateItems).toHaveBeenCalledWith({
        item_ids: ["101"],
        action: "set_status",
        status: "reading"
      })
    })
  })
})
