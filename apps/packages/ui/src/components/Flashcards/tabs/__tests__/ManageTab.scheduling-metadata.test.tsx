import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ManageTab } from "../ManageTab"
import type { Flashcard } from "@/services/flashcards"
import {
  useDecksQuery,
  useManageQuery,
  useUpdateFlashcardMutation,
  useDeleteFlashcardMutation,
  useCardsKeyboardNav
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

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query")
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: vi.fn()
    })
  }
})

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

vi.mock("@/components/Common/confirm-danger", () => ({
  useConfirmDanger: () => vi.fn().mockResolvedValue(true)
}))

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => ({
    showUndoNotification: vi.fn()
  })
}))

vi.mock("../../hooks", () => ({
  useDecksQuery: vi.fn(),
  useManageQuery: vi.fn(),
  useUpdateFlashcardMutation: vi.fn(),
  useDeleteFlashcardMutation: vi.fn(),
  useCardsKeyboardNav: vi.fn()
}))

vi.mock("../../components", () => ({
  MarkdownWithBoundary: ({ content }: { content: string }) => <div>{content}</div>,
  FlashcardActionsMenu: () => <div />,
  FlashcardEditDrawer: () => null,
  FlashcardCreateDrawer: () => null
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
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

const sampleCard: Flashcard = {
  uuid: "card-meta-1",
  deck_id: 1,
  front: "Front prompt",
  back: "Back answer",
  notes: null,
  extra: null,
  is_cloze: false,
  tags: ["biology"],
  ef: 2.7,
  interval_days: 5,
  repetitions: 3,
  lapses: 1,
  due_at: null,
  last_reviewed_at: null,
  last_modified: null,
  deleted: false,
  client_id: "test",
  version: 4,
  model_type: "basic",
  reverse: false
}

describe("ManageTab scheduling metadata visibility", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDecksQuery).mockReturnValue({
      data: [
        {
          id: 1,
          name: "Biology",
          description: null,
          deleted: false,
          client_id: "test",
          version: 1
        }
      ],
      isLoading: false
    } as any)
    vi.mocked(useManageQuery).mockReturnValue({
      data: {
        items: [sampleCard],
        count: 1,
        total: 1
      },
      isFetching: false
    } as any)
    vi.mocked(useUpdateFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useDeleteFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useCardsKeyboardNav).mockImplementation(() => undefined)
  })

  it("shows scheduling metadata in compact list rows", () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    expect(screen.getByText("EF 2.70")).toBeInTheDocument()
    expect(screen.getByText("Int 5d")).toBeInTheDocument()
    expect(screen.getByText("Reps 3")).toBeInTheDocument()
    expect(screen.getByText("Lapses 1")).toBeInTheDocument()
  })

  it("shows scheduling metadata in expanded list rows", () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    fireEvent.click(screen.getByTestId("flashcards-density-toggle"))

    expect(screen.getByText("Ease 2.70")).toBeInTheDocument()
    expect(screen.getByText("Interval 5d")).toBeInTheDocument()
    expect(screen.getByText("Reps 3")).toBeInTheDocument()
    expect(screen.getByText("Lapses 1")).toBeInTheDocument()
  })
})
