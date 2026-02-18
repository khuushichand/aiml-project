import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ImportExportTab } from "../ImportExportTab"
import {
  useDecksQuery,
  useImportFlashcardsMutation,
  useImportLimitsQuery
} from "../../hooks"
import { deleteFlashcard, getFlashcard } from "@/services/flashcards"

const messageSpies = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
  open: vi.fn(),
  destroy: vi.fn()
}
const showUndoNotificationMock = vi.fn()
const invalidateQueriesMock = vi.fn()

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query")
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: invalidateQueriesMock
    })
  }
})

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => messageSpies
}))

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => ({
    showUndoNotification: showUndoNotificationMock
  })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) {
        return defaultValueOrOptions.defaultValue.replace(
          /\{\{(\w+)\}\}/g,
          (_match, token: string) =>
            String((defaultValueOrOptions as Record<string, unknown>)[token] ?? `{{${token}}}`)
        )
      }
      return key
    }
  })
}))

vi.mock("../../hooks", () => ({
  useDecksQuery: vi.fn(),
  useImportFlashcardsMutation: vi.fn(),
  useImportLimitsQuery: vi.fn()
}))

vi.mock("@/services/flashcards", async () => {
  const actual = await vi.importActual<typeof import("@/services/flashcards")>("@/services/flashcards")
  return {
    ...actual,
    getFlashcard: vi.fn(),
    deleteFlashcard: vi.fn()
  }
})

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ImportExportTab import result details", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    invalidateQueriesMock.mockReset()
    vi.mocked(useDecksQuery).mockReturnValue({
      data: [],
      isLoading: false
    } as any)
    vi.mocked(useImportLimitsQuery).mockReturnValue({
      data: null
    } as any)
  })

  it("shows imported/skipped counts and line-level errors on partial imports", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      imported: 2,
      items: [
        { uuid: "u1", deck_id: 1 },
        { uuid: "u2", deck_id: 1 }
      ],
      errors: [{ line: 15, error: "Missing required field: Front" }]
    })
    vi.mocked(useImportFlashcardsMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)

    render(<ImportExportTab />)

    fireEvent.change(screen.getByTestId("flashcards-import-textarea"), {
      target: {
        value: "Deck\tFront\tBack\nBiology\tQuestion\tAnswer"
      }
    })
    fireEvent.click(screen.getByTestId("flashcards-import-button"))

    expect(await screen.findByText("Last import: 2 imported, 1 skipped")).toBeInTheDocument()
    expect(screen.getByText("Line 15")).toBeInTheDocument()
    expect(screen.getByText("Missing required field: Front")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Add a non-empty Front value on that row, or map your header to the Front column."
      )
    ).toBeInTheDocument()
    expect(messageSpies.warning).toHaveBeenCalledWith(
      "Imported 2 cards, skipped 1 rows (1 errors)."
    )
  }, 15000)

  it("shows preflight warning when selected delimiter does not match sample content", async () => {
    vi.mocked(useImportFlashcardsMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)

    render(<ImportExportTab />)

    fireEvent.change(screen.getByTestId("flashcards-import-textarea"), {
      target: {
        value: "Deck,Front,Back\nBiology,Question,Answer"
      }
    })

    expect(screen.getByTestId("flashcards-import-preflight-warning")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Selected delimiter (Tab) may be incorrect. This sample looks Comma-delimited."
      )
    ).toBeInTheDocument()
  })

  it("requires confirmation before importing very large batches", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      imported: 0,
      items: [],
      errors: []
    })
    vi.mocked(useImportFlashcardsMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)

    const rows = Array.from({ length: 301 }, (_, idx) => `Deck\tFront ${idx}\tBack ${idx}`).join("\n")

    render(<ImportExportTab />)

    fireEvent.change(screen.getByTestId("flashcards-import-textarea"), {
      target: {
        value: `Deck\tFront\tBack\n${rows}`
      }
    })
    fireEvent.click(screen.getByTestId("flashcards-import-button"))

    expect(screen.getByText("Confirm large import")).toBeInTheDocument()
    expect(mutateAsync).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId("flashcards-import-confirm-large"))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1)
    })
  })

  it("offers undo rollback for the latest import batch", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      imported: 2,
      items: [
        { uuid: "undo-u1", deck_id: 1 },
        { uuid: "undo-u2", deck_id: 1 }
      ],
      errors: []
    })
    vi.mocked(useImportFlashcardsMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)
    vi.mocked(getFlashcard)
      .mockResolvedValueOnce({ uuid: "undo-u1", version: 7 } as any)
      .mockResolvedValueOnce({ uuid: "undo-u2", version: 8 } as any)
    vi.mocked(deleteFlashcard).mockResolvedValue(undefined as any)

    render(<ImportExportTab />)

    fireEvent.change(screen.getByTestId("flashcards-import-textarea"), {
      target: {
        value: "Deck\tFront\tBack\nBiology\tQuestion\tAnswer"
      }
    })
    fireEvent.click(screen.getByTestId("flashcards-import-button"))

    await waitFor(() => {
      expect(showUndoNotificationMock).toHaveBeenCalledTimes(1)
    })
    const undoConfig = showUndoNotificationMock.mock.calls[0][0]
    expect(undoConfig.duration).toBe(30)
    expect(String(undoConfig.description)).toContain("Undo within 30s")

    await undoConfig.onUndo()

    expect(getFlashcard).toHaveBeenCalledTimes(2)
    expect(deleteFlashcard).toHaveBeenCalledWith("undo-u1", 7)
    expect(deleteFlashcard).toHaveBeenCalledWith("undo-u2", 8)
    expect(invalidateQueriesMock).toHaveBeenCalled()
  })
})
