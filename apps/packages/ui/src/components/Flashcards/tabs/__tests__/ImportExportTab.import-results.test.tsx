import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ImportExportTab } from "../ImportExportTab"
import {
  useDecksQuery,
  useImportFlashcardsMutation,
  useImportLimitsQuery
} from "../../hooks"

const messageSpies = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
  open: vi.fn(),
  destroy: vi.fn()
}

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => messageSpies
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
    expect(messageSpies.warning).toHaveBeenCalledWith(
      "Imported 2 cards, skipped 1 rows (1 errors)."
    )
  }, 15000)
})
