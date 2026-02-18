import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ManageTab } from "../ManageTab"
import {
  useCreateQuestionMutation,
  useDeleteQuestionMutation,
  useDeleteQuizMutation,
  useQuestionsQuery,
  useQuizzesQuery,
  useUpdateQuestionMutation,
  useUpdateQuizMutation
} from "../../hooks"

const interpolate = (template: string, values: Record<string, unknown> | undefined) => {
  return template.replace(/\{\{\s*([^\s}]+)\s*\}\}/g, (_, key: string) => {
    const value = values?.[key]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      const defaultValue = defaultValueOrOptions?.defaultValue
      if (typeof defaultValue === "string") {
        return interpolate(defaultValue, defaultValueOrOptions)
      }
      return key
    }
  })
}))

vi.mock("../../hooks", () => ({
  useQuizzesQuery: vi.fn(),
  useQuestionsQuery: vi.fn(),
  useDeleteQuizMutation: vi.fn(),
  useUpdateQuizMutation: vi.fn(),
  useCreateQuestionMutation: vi.fn(),
  useUpdateQuestionMutation: vi.fn(),
  useDeleteQuestionMutation: vi.fn()
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ManageTab undo accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 7,
            name: "Biology Basics",
            description: "Cell structures and functions",
            total_questions: 3,
            passing_score: 75,
            media_id: null,
            time_limit_seconds: 600,
            deleted: false,
            client_id: "test",
            version: 1
          }
        ],
        count: 1
      },
      isLoading: false,
      refetch: vi.fn()
    } as any)

    vi.mocked(useQuestionsQuery).mockReturnValue({
      data: { items: [], count: 0 },
      isLoading: false,
      refetch: vi.fn()
    } as any)

    vi.mocked(useDeleteQuizMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => undefined)
    } as any)

    vi.mocked(useUpdateQuizMutation).mockReturnValue({ mutateAsync: vi.fn() } as any)
    vi.mocked(useCreateQuestionMutation).mockReturnValue({ mutateAsync: vi.fn() } as any)
    vi.mocked(useUpdateQuestionMutation).mockReturnValue({ mutateAsync: vi.fn() } as any)
    vi.mocked(useDeleteQuestionMutation).mockReturnValue({ mutateAsync: vi.fn() } as any)
  })

  it("shows a focusable inline undo banner after delete", async () => {
    render(
      <ManageTab
        onNavigateToCreate={() => {}}
        onNavigateToGenerate={() => {}}
        onStartQuiz={() => {}}
      />
    )

    expect(screen.getByText("Biology Basics")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /delete/i }))
    await waitFor(() => {
      expect(screen.queryByText("Biology Basics")).not.toBeInTheDocument()
    })

    const undoButton = screen.getByRole("button", { name: /undo/i })
    undoButton.focus()
    expect(undoButton).toHaveFocus()

    fireEvent.click(undoButton)
    await waitFor(() => {
      expect(screen.getByText("Biology Basics")).toBeInTheDocument()
    })
  })

  it("returns focus to the edit trigger after the edit modal closes", async () => {
    render(
      <ManageTab
        onNavigateToCreate={() => {}}
        onNavigateToGenerate={() => {}}
        onStartQuiz={() => {}}
      />
    )

    const editTrigger = screen.getByTestId("quiz-edit-7")
    editTrigger.focus()
    expect(editTrigger).toHaveFocus()

    fireEvent.click(editTrigger)
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }))

    await waitFor(() => {
      expect(editTrigger).toHaveFocus()
    })
  })

  it("links inline validation errors and restores focus when question modal closes", async () => {
    render(
      <ManageTab
        onNavigateToCreate={() => {}}
        onNavigateToGenerate={() => {}}
        onStartQuiz={() => {}}
      />
    )

    fireEvent.click(screen.getByTestId("quiz-edit-7"))

    const addQuestionButton = await screen.findByTestId("manage-add-question")
    addQuestionButton.focus()
    expect(addQuestionButton).toHaveFocus()

    fireEvent.click(addQuestionButton)

    const questionInput = await screen.findByPlaceholderText("Enter your question...")
    const questionModal = questionInput.closest(".ant-modal")
    const questionModalQueries = questionModal ? within(questionModal as HTMLElement) : screen

    fireEvent.click(questionModalQueries.getByRole("button", { name: /^save$/i }))

    await waitFor(() => {
      expect(screen.getByText("Question text is required.")).toBeInTheDocument()
    })
    expect(screen.getByText("Please provide at least two options.")).toBeInTheDocument()

    expect(questionInput).toHaveAttribute("aria-describedby", "manage-question-text-error")

    const optionOneInput = questionModalQueries.getByPlaceholderText("Option 1")
    expect(optionOneInput).toHaveAttribute("aria-describedby", "manage-question-options-error")

    fireEvent.click(questionModalQueries.getByRole("button", { name: /cancel/i }))

    await waitFor(() => {
      expect(addQuestionButton).toHaveFocus()
    })
  })
})
