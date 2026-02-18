import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ManageTab } from "../ManageTab"
import { clearSetting } from "@/services/settings/registry"
import { FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING } from "@/services/settings/ui-settings"
import type { Flashcard } from "@/services/flashcards"
import {
  useDecksQuery,
  useManageQuery,
  useUpdateFlashcardMutation,
  useResetFlashcardSchedulingMutation,
  useDeleteFlashcardMutation,
  useCardsKeyboardNav,
  useDebouncedFormField
} from "../../hooks"
import { FLASHCARDS_DRAWER_WIDTH_PX } from "../../constants"
import { getFlashcard, updateFlashcard } from "@/services/flashcards"

const showUndoNotificationMock = vi.fn()
const updateMutationMock = vi.fn()

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

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => ({
    showUndoNotification: showUndoNotificationMock
  })
}))

vi.mock("@/components/Common/confirm-danger", () => ({
  useConfirmDanger: () => vi.fn().mockResolvedValue(true)
}))

vi.mock("../../hooks", () => ({
  useDecksQuery: vi.fn(),
  useManageQuery: vi.fn(),
  useUpdateFlashcardMutation: vi.fn(),
  useResetFlashcardSchedulingMutation: vi.fn(),
  useDeleteFlashcardMutation: vi.fn(),
  useCardsKeyboardNav: vi.fn(),
  useDebouncedFormField: vi.fn(() => undefined)
}))

vi.mock("../../components", async () => {
  const actual = await vi.importActual<typeof import("../../components")>("../../components")
  return {
    ...actual,
    FlashcardActionsMenu: ({
      onEdit,
      onMove
    }: {
      onEdit: () => void
      onMove: () => void
    }) => (
      <div>
        <button onClick={onEdit}>Action Edit</button>
        <button onClick={onMove}>Action Move</button>
      </div>
    ),
    FlashcardCreateDrawer: () => null
  }
})

vi.mock("@/services/flashcards", async () => {
  const actual = await vi.importActual<typeof import("@/services/flashcards")>("@/services/flashcards")
  return {
    ...actual,
    getFlashcard: vi.fn(),
    updateFlashcard: vi.fn(),
    createFlashcard: vi.fn(),
    deleteFlashcard: vi.fn(),
    listFlashcards: vi.fn()
  }
})

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
  uuid: "card-undo-1",
  deck_id: 1,
  front: "Front prompt",
  back: "Back answer",
  notes: null,
  extra: null,
  is_cloze: false,
  tags: ["biology"],
  ef: 2.6,
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

describe("ManageTab stage3 undo controls", () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await clearSetting(FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING)

    vi.mocked(useDecksQuery).mockReturnValue({
      data: [
        {
          id: 1,
          name: "Deck 1",
          description: null,
          deleted: false,
          client_id: "test",
          version: 1
        },
        {
          id: 2,
          name: "Deck 2",
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
      mutateAsync: updateMutationMock,
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
    vi.mocked(useDebouncedFormField).mockReturnValue(undefined as any)
  })

  it("offers undo for single-card edits", async () => {
    vi.mocked(getFlashcard)
      .mockResolvedValueOnce({ ...sampleCard })
      .mockResolvedValueOnce({ ...sampleCard, version: 5, front: "Updated front" })
    updateMutationMock.mockResolvedValue(undefined)

    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    fireEvent.click(screen.getByText("Action Edit"))
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => {
      expect(showUndoNotificationMock).toHaveBeenCalledTimes(1)
    })

    const undoConfig = showUndoNotificationMock.mock.calls[0][0]
    expect(undoConfig.duration).toBe(30)
    expect(String(undoConfig.description)).toContain("Undo within 30s")

    await undoConfig.onUndo()

    expect(updateMutationMock).toHaveBeenCalledTimes(2)
    const undoCall = updateMutationMock.mock.calls[1][0]
    expect(undoCall.uuid).toBe(sampleCard.uuid)
    expect(undoCall.update.deck_id).toBe(1)
    expect(undoCall.update.front).toBe("Front prompt")
    expect(undoCall.update.expected_version).toBe(5)
  }, 15000)

  it("offers undo for move operations", async () => {
    vi.mocked(getFlashcard)
      .mockResolvedValueOnce({ ...sampleCard, version: 8, deck_id: 1 })
      .mockResolvedValueOnce({ ...sampleCard, version: 9, deck_id: 2 })
    vi.mocked(updateFlashcard).mockResolvedValue(undefined as any)

    render(
      <ManageTab
        onNavigateToImport={() => {}}
        onReviewCard={() => {}}
        isActive={false}
      />
    )

    fireEvent.click(screen.getByText("Action Move"))
    const moveWrapper = document.querySelector(".ant-drawer-content-wrapper") as HTMLElement | null
    expect(moveWrapper?.style.width).toBe(`${FLASHCARDS_DRAWER_WIDTH_PX}px`)

    const comboboxes = screen.getAllByRole("combobox")
    fireEvent.mouseDown(comboboxes[comboboxes.length - 1])
    fireEvent.click(screen.getByText("Deck 2"))
    fireEvent.click(screen.getByRole("button", { name: "Move" }))

    await waitFor(() => {
      expect(showUndoNotificationMock).toHaveBeenCalledTimes(1)
    })
    expect(updateFlashcard).toHaveBeenCalledTimes(1)
    expect(vi.mocked(updateFlashcard).mock.calls[0][1]).toMatchObject({
      deck_id: 2,
      expected_version: 8
    })

    const undoConfig = showUndoNotificationMock.mock.calls[0][0]
    expect(String(undoConfig.description)).toContain("Undo within 30s")
    await undoConfig.onUndo()

    expect(updateFlashcard).toHaveBeenCalledTimes(2)
    expect(vi.mocked(updateFlashcard).mock.calls[1][1]).toMatchObject({
      deck_id: 1,
      expected_version: 9
    })
  }, 15000)
})
