import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { FlashcardsManager } from "../FlashcardsManager"

const mocks = vi.hoisted(() => ({
  navigate: vi.fn()
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

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock("../tabs", () => ({
  ReviewTab: (props: {
    onNavigateToCreate: () => void
    reviewDeckId?: number | null
    onReviewDeckChange: (deckId: number | null | undefined) => void
  }) => (
    <div data-testid="mock-review-tab">
      <button onClick={props.onNavigateToCreate}>Route Create</button>
      <button onClick={() => props.onReviewDeckChange(12)}>Select Deck 12</button>
      <span data-testid="mock-review-deck-id">{String(props.reviewDeckId ?? "")}</span>
    </div>
  ),
  ManageTab: (props: {
    onNavigateToImport: () => void
    openCreateSignal?: number
  }) => (
    <div data-testid="mock-manage-tab">
      <button onClick={props.onNavigateToImport}>Route Import</button>
      <span data-testid="mock-open-create-signal">{String(props.openCreateSignal ?? 0)}</span>
    </div>
  ),
  ImportExportTab: () => <div data-testid="mock-transfer-tab">Transfer panel</div>,
  SchedulerTab: (props: { onDirtyChange?: (dirty: boolean) => void }) => (
    <div data-testid="mock-scheduler-tab">
      Scheduler panel
      <button onClick={() => props.onDirtyChange?.(true)}>Mark Scheduler Dirty</button>
      <button onClick={() => props.onDirtyChange?.(false)}>Mark Scheduler Clean</button>
    </div>
  )
}))

vi.mock("../components", () => ({
  KeyboardShortcutsModal: () => null
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("FlashcardsManager consistency standards", () => {
  it("hydrates review deck and quiz context from quiz-study handoff params", () => {
    window.history.replaceState(
      {},
      "",
      "/flashcards?tab=review&study_source=quiz&quiz_id=21&attempt_id=88&deck_id=4"
    )

    render(<FlashcardsManager />)

    expect(screen.getByTestId("mock-review-deck-id")).toHaveTextContent("4")
    fireEvent.click(screen.getByTestId("flashcards-to-quiz-cta"))

    expect(mocks.navigate).toHaveBeenCalledWith(
      expect.stringContaining(
        "/quiz?tab=take&source=flashcards&start_quiz_id=21&highlight_quiz_id=21&deck_id=4&source_attempt_id=88"
      )
    )
  })

  it("opens Transfer tab first when URL contains generate intent", () => {
    window.history.replaceState(
      {},
      "",
      "/flashcards?generate=1&generate_text=Study%20notes"
    )

    render(<FlashcardsManager />)

    expect(screen.getByTestId("mock-transfer-tab")).toBeInTheDocument()
  })

  it("uses Study/Manage/Transfer/Scheduler tab labels", () => {
    window.history.replaceState({}, "", "/flashcards")
    render(<FlashcardsManager />)

    expect(screen.getByText("Study")).toBeInTheDocument()
    expect(screen.getByText("Manage")).toBeInTheDocument()
    expect(screen.getByText("Transfer")).toBeInTheDocument()
    expect(screen.getByText("Scheduler")).toBeInTheDocument()
  })

  it("routes secondary create CTA to the Manage tab create entry point", () => {
    window.history.replaceState({}, "", "/flashcards")
    render(<FlashcardsManager />)

    fireEvent.click(screen.getByText("Route Create"))
    expect(screen.getByTestId("mock-manage-tab")).toBeInTheDocument()
    expect(screen.getByTestId("mock-open-create-signal")).toHaveTextContent("1")
  })

  it("keeps quiz CTA usable when handoff IDs are invalid", () => {
    window.history.replaceState(
      {},
      "",
      "/flashcards?study_source=quiz&quiz_id=abc&attempt_id=-1&deck_id=0"
    )
    render(<FlashcardsManager />)

    fireEvent.click(screen.getByTestId("flashcards-to-quiz-cta"))

    expect(mocks.navigate).toHaveBeenCalledWith("/quiz?tab=take&source=flashcards")
  })

  it("prompts before leaving the Scheduler tab when its draft is dirty", () => {
    const confirmSpy = vi.spyOn(window, "confirm")
    confirmSpy.mockReturnValue(false)

    window.history.replaceState({}, "", "/flashcards")
    render(<FlashcardsManager />)

    fireEvent.click(screen.getByText("Scheduler"))
    expect(screen.getByTestId("mock-scheduler-tab")).toBeInTheDocument()

    fireEvent.click(screen.getByText("Mark Scheduler Dirty"))
    fireEvent.click(screen.getByText("Manage"))

    expect(confirmSpy).toHaveBeenCalled()
    expect(screen.getByTestId("mock-scheduler-tab")).toBeInTheDocument()

    confirmSpy.mockReturnValue(true)
    fireEvent.click(screen.getByText("Manage"))
    expect(screen.getByTestId("mock-manage-tab")).toBeInTheDocument()

    confirmSpy.mockRestore()
  })
})
