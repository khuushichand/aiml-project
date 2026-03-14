import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ManageTab } from "../ManageTab"
import { clearSetting } from "@/services/settings/registry"
import { FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING } from "@/services/settings/ui-settings"
import type { Flashcard } from "@/services/flashcards"
import {
  useUpdateFlashcardsBulkMutation,
  useDecksQuery,
  useFlashcardDocumentQuery,
  useManageQuery,
  useTagSuggestionsQuery,
  useUpdateFlashcardMutation,
  useResetFlashcardSchedulingMutation,
  useDeleteFlashcardMutation,
  useCardsKeyboardNav,
  getManageServerOrderBy
} from "../../hooks"

const { trackShortcutHintTelemetryMock } = vi.hoisted(() => ({
  trackShortcutHintTelemetryMock: vi.fn().mockResolvedValue(undefined)
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

vi.mock("@/utils/flashcards-shortcut-hint-telemetry", () => ({
  trackFlashcardsShortcutHintTelemetry: trackShortcutHintTelemetryMock
}))

vi.mock("../../hooks", () => ({
  DOCUMENT_VIEW_SUPPORTED_SORTS: ["due", "created"],
  getFlashcardDocumentQueryKey: vi.fn(() => ["flashcards:document", 1]),
  useDecksQuery: vi.fn(),
  useFlashcardDocumentQuery: vi.fn(),
  useManageQuery: vi.fn(),
  useTagSuggestionsQuery: vi.fn(),
  useUpdateFlashcardMutation: vi.fn(),
  useUpdateFlashcardsBulkMutation: vi.fn(),
  useResetFlashcardSchedulingMutation: vi.fn(),
  useDeleteFlashcardMutation: vi.fn(),
  useCardsKeyboardNav: vi.fn(),
  getManageServerOrderBy: vi.fn(() => "due_at")
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
  reverse: false,
  source_ref_type: "media",
  source_ref_id: "42"
}

describe("ManageTab scheduling metadata visibility", () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await clearSetting(FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING)
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
    vi.mocked(useFlashcardDocumentQuery).mockReturnValue({
      items: [sampleCard],
      isFetching: false,
      isLoading: false,
      isTruncated: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
      supportedSorts: ["due", "created"],
      data: {
        pages: [
          {
            items: [sampleCard],
            isTruncated: false,
            total: 1
          }
        ]
      }
    } as any)
    vi.mocked(useTagSuggestionsQuery).mockReturnValue({
      data: ["biology", "chemistry", "physics"],
      isLoading: false
    } as any)
    vi.mocked(useUpdateFlashcardMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
    vi.mocked(useUpdateFlashcardsBulkMutation).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({ results: [] }),
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
    vi.mocked(useCardsKeyboardNav).mockImplementation(() => undefined)
    vi.mocked(getManageServerOrderBy).mockReturnValue("due_at")
  })

  it("shows scheduling metadata in compact list rows", () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive
      />
    )

    expect(screen.getByText("Memory 2.70")).toBeInTheDocument()
    expect(screen.getByText("Next gap 5d")).toBeInTheDocument()
    expect(screen.getByText("Recall runs 3")).toBeInTheDocument()
    expect(screen.getByText("Relearns 1")).toBeInTheDocument()
    expect(screen.getByText("Media #42")).toBeInTheDocument()
    expect(screen.getByTestId("flashcards-manage-shortcut-chips")).toBeInTheDocument()
    expect(screen.getByText("Sort: Due date")).toBeInTheDocument()
  }, 15000)

  it("shows scheduling metadata in expanded list rows", () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    fireEvent.click(screen.getByTestId("flashcards-density-toggle"))

    expect(screen.getByText("Memory strength 2.70")).toBeInTheDocument()
    expect(screen.getByText("Next review gap 5d")).toBeInTheDocument()
    expect(screen.getByText("Recall runs 3")).toBeInTheDocument()
    expect(screen.getByText("Relearns 1")).toBeInTheDocument()
    expect(screen.getByText("Media #42")).toBeInTheDocument()
  }, 15000)

  it("does not render source badges for manual cards", () => {
    vi.mocked(useManageQuery).mockReturnValue({
      data: {
        items: [
          {
            ...sampleCard,
            uuid: "card-manual-1",
            source_ref_type: "manual",
            source_ref_id: null
          }
        ],
        count: 1,
        total: 1
      },
      isFetching: false
    } as any)

    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    expect(screen.queryByText(/Media #/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Note #/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Message #/)).not.toBeInTheDocument()
    expect(screen.queryByText(/source unavailable/i)).not.toBeInTheDocument()
  }, 15000)

  it("cycles shortcut hint density and persists the choice", async () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    const toggle = screen.getByTestId("flashcards-manage-shortcut-hints-toggle")
    expect(toggle).toHaveTextContent("Compact hints")
    expect(screen.getByText("J/K Navigate")).toBeInTheDocument()

    fireEvent.click(toggle)
    await waitFor(() => {
      expect(screen.getByText("J/K · Enter · Space · Delete")).toBeInTheDocument()
    })
    expect(screen.getByTestId("flashcards-manage-shortcut-hints-toggle")).toHaveTextContent(
      "Hide hints"
    )

    fireEvent.click(screen.getByTestId("flashcards-manage-shortcut-hints-toggle"))
    await waitFor(() => {
      expect(screen.getByTestId("flashcards-manage-shortcut-hints-toggle")).toHaveTextContent(
        "Show hints"
      )
    })
    expect(trackShortcutHintTelemetryMock).toHaveBeenCalledWith({
      type: "flashcards_shortcut_hints_dismissed",
      surface: "cards",
      from_density: "compact"
    })
    expect(screen.queryByText("J/K · Enter · Space · Delete")).not.toBeInTheDocument()
    expect(screen.queryByText("J/K Navigate")).not.toBeInTheDocument()
    await waitFor(() => {
      expect(window.localStorage.getItem("tldw:flashcards:shortcutHintDensity")).toBe(
        "hidden"
      )
    })
  }, 15000)

  it("supports multi-tag filter chips with suggestions", async () => {
    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "More" }))
    const input = screen.getByTestId("flashcards-manage-tag-input")
    fireEvent.change(input, { target: { value: "chemistry" } })
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" })

    await waitFor(() => {
      expect(screen.getByTestId("flashcards-manage-active-tag-filters")).toHaveTextContent(
        "chemistry"
      )
    })

    fireEvent.click(screen.getByRole("button", { name: "biology" }))

    await waitFor(() => {
      const lastManageCall = vi.mocked(useManageQuery).mock.calls.at(-1)
      expect(lastManageCall?.[0]).toMatchObject({
        tags: ["chemistry", "biology"]
      })
    })
  }, 15000)
})
