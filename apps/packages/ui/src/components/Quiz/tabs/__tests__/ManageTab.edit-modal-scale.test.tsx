import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ManageTab } from "../ManageTab"
import {
  useCreateQuizMutation,
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
  useCreateQuizMutation: vi.fn(),
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

describe("ManageTab edit modal scale", () => {
  const updateQuestionMutateAsync = vi.fn(async () => undefined)

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 12,
            name: "Stage 2 Quiz",
            description: "Long quiz editing",
            total_questions: 2,
            passing_score: 70,
            media_id: null,
            time_limit_seconds: 900,
            deleted: false,
            client_id: "test",
            version: 3
          }
        ],
        count: 1
      },
      isLoading: false,
      refetch: vi.fn()
    } as any)

    vi.mocked(useQuestionsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 101,
            quiz_id: 12,
            question_type: "multiple_choice",
            question_text: "First prompt",
            options: ["A", "B", "C", "D"],
            correct_answer: 0,
            explanation: "",
            points: 1,
            order_index: 0,
            deleted: false,
            client_id: "test",
            version: 1
          },
          {
            id: 102,
            quiz_id: 12,
            question_type: "multiple_choice",
            question_text: "Second prompt",
            options: ["A", "B", "C", "D"],
            correct_answer: 1,
            explanation: "",
            points: 1,
            order_index: 1,
            deleted: false,
            client_id: "test",
            version: 1
          }
        ],
        count: 2
      },
      isLoading: false,
      refetch: vi.fn()
    } as any)

    vi.mocked(useDeleteQuizMutation).mockReturnValue({ mutateAsync: vi.fn(async () => undefined) } as any)
    vi.mocked(useCreateQuizMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({ id: 1012 }))
    } as any)
    vi.mocked(useUpdateQuizMutation).mockReturnValue({ mutateAsync: vi.fn(async () => undefined), isPending: false } as any)
    vi.mocked(useCreateQuestionMutation).mockReturnValue({ mutateAsync: vi.fn(async () => undefined) } as any)
    vi.mocked(useUpdateQuestionMutation).mockReturnValue({
      mutateAsync: updateQuestionMutateAsync,
      isPending: false
    } as any)
    vi.mocked(useDeleteQuestionMutation).mockReturnValue({ mutateAsync: vi.fn(async () => undefined) } as any)
  })

  it("uses scroll layout in edit modal and persists reorder swaps", async () => {
    render(
      <ManageTab
        onNavigateToCreate={() => {}}
        onNavigateToGenerate={() => {}}
        onStartQuiz={() => {}}
      />
    )

    fireEvent.click(screen.getByTestId("quiz-edit-12"))

    const modalTitle = await screen.findByText("Edit Quiz")
    const editModal = modalTitle.closest(".ant-modal") ?? document.querySelector(".ant-modal")
    expect(editModal).not.toBeNull()
    if (!editModal) return
    const modalQueries = within(editModal)

    expect(modalQueries.getByTestId("manage-questions-scroll-container")).toBeInTheDocument()
    expect(modalQueries.queryByText(/items\/page/i)).not.toBeInTheDocument()

    fireEvent.click(modalQueries.getByRole("button", { name: /Move question 1 down/i }))

    await waitFor(() => {
      expect(updateQuestionMutateAsync).toHaveBeenCalledTimes(2)
    })

    expect(updateQuestionMutateAsync).toHaveBeenNthCalledWith(1, {
      quizId: 12,
      questionId: 101,
      update: {
        order_index: 1
      }
    })
    expect(updateQuestionMutateAsync).toHaveBeenNthCalledWith(2, {
      quizId: 12,
      questionId: 102,
      update: {
        order_index: 0
      }
    })
  }, 20000)
})
