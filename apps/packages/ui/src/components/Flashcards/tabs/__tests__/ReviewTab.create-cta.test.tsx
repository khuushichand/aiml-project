import { fireEvent, render, screen } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { ReviewTab } from "../ReviewTab"
import {
  useDecksQuery,
  useCramQueueQuery,
  useReviewQuery,
  useReviewFlashcardMutation,
  useUpdateFlashcardMutation,
  useResetFlashcardSchedulingMutation,
  useDeleteFlashcardMutation,
  useFlashcardShortcuts,
  useDebouncedFormField,
  useDueCountsQuery,
  useDeckDueCountsQuery,
  useReviewAnalyticsSummaryQuery,
  useHasCardsQuery,
  useNextDueQuery
} from "../../hooks"

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

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
    open: vi.fn(),
    destroy: vi.fn()
  })
}))

vi.mock("../../hooks", () => ({
  useDecksQuery: vi.fn(),
  useCramQueueQuery: vi.fn(),
  useReviewQuery: vi.fn(),
  useReviewFlashcardMutation: vi.fn(),
  useUpdateFlashcardMutation: vi.fn(),
  useResetFlashcardSchedulingMutation: vi.fn(),
  useDeleteFlashcardMutation: vi.fn(),
  useFlashcardShortcuts: vi.fn(),
  useDebouncedFormField: vi.fn(() => undefined),
  useDueCountsQuery: vi.fn(),
  useDeckDueCountsQuery: vi.fn(),
  useReviewAnalyticsSummaryQuery: vi.fn(),
  useHasCardsQuery: vi.fn(),
  useNextDueQuery: vi.fn()
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ReviewTab create CTA visibility", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    if (typeof window.matchMedia !== "function") {
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
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDecksQuery).mockReturnValue({
      data: [],
      isLoading: false
    } as any)
    vi.mocked(useCramQueueQuery).mockReturnValue({ data: [] } as any)
    vi.mocked(useReviewQuery).mockReturnValue({
      data: null
    } as any)
    vi.mocked(useReviewFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn()
    } as any)
    vi.mocked(useUpdateFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useResetFlashcardSchedulingMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useDeleteFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useFlashcardShortcuts).mockImplementation(() => undefined)
    vi.mocked(useDebouncedFormField).mockReturnValue(undefined as any)
    vi.mocked(useDueCountsQuery).mockReturnValue({
      data: { due: 0, new: 0, learning: 0, total: 0 }
    } as any)
    vi.mocked(useDeckDueCountsQuery).mockReturnValue({
      data: {}
    } as any)
    vi.mocked(useReviewAnalyticsSummaryQuery).mockReturnValue({
      data: null,
      isLoading: false
    } as any)
    vi.mocked(useHasCardsQuery).mockReturnValue({
      data: false
    } as any)
    vi.mocked(useNextDueQuery).mockReturnValue({
      data: null
    } as any)
  })

  it("renders an always-visible create action and routes to cards tab", () => {
    const onNavigateToCreate = vi.fn()

    render(
      <ReviewTab
        onNavigateToCreate={onNavigateToCreate}
        onNavigateToImport={() => {}}
        reviewDeckId={undefined}
        onReviewDeckChange={() => {}}
        isActive
      />
    )

    const createButton = screen.getByTestId("flashcards-review-create-cta")
    expect(createButton).toBeInTheDocument()

    fireEvent.click(createButton)
    expect(onNavigateToCreate).toHaveBeenCalledTimes(1)
  })

  it("shows due counts in deck selector labels when available", () => {
    vi.mocked(useDecksQuery).mockReturnValue({
      data: [{ id: 11, name: "Biology" }],
      isLoading: false
    } as any)
    vi.mocked(useDeckDueCountsQuery).mockReturnValue({
      data: {
        11: { due: 7, new: 3, learning: 2, total: 12 }
      }
    } as any)

    render(
      <ReviewTab
        onNavigateToCreate={() => {}}
        onNavigateToImport={() => {}}
        reviewDeckId={undefined}
        onReviewDeckChange={() => {}}
        isActive
      />
    )

    fireEvent.mouseDown(screen.getByRole("combobox"))
    expect(screen.getByText("Biology (7 due)")).toBeInTheDocument()
  })
})
