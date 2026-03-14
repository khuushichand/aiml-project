import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ResultsTab } from "../ResultsTab"
import {
  useAllAttemptsQuery,
  useAttemptQuery,
  useGenerateRemediationQuizMutation,
  useQuizAttemptQuestionAssistantQuery,
  useQuizAttemptQuestionAssistantRespondMutation,
  useQuizzesQuery
} from "../../hooks"
import {
  useCreateDeckMutation,
  useCreateFlashcardsBulkMutation,
  useCreateFlashcardMutation,
  useDecksQuery
} from "@/components/Flashcards/hooks/useFlashcardQueries"

const mocks = vi.hoisted(() => ({
  createDeck: vi.fn(),
  createFlashcard: vi.fn(),
  createFlashcardsBulk: vi.fn(),
  navigate: vi.fn(),
  remediationQuiz: vi.fn(),
  assistantRespond: vi.fn()
}))

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

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock("../../hooks", () => ({
  useAllAttemptsQuery: vi.fn(),
  useQuizzesQuery: vi.fn(),
  useAttemptQuery: vi.fn(),
  useGenerateRemediationQuizMutation: vi.fn(),
  useQuizAttemptQuestionAssistantQuery: vi.fn(),
  useQuizAttemptQuestionAssistantRespondMutation: vi.fn()
}))

vi.mock("@/components/Flashcards/hooks/useFlashcardQueries", () => ({
  useDecksQuery: vi.fn(),
  useCreateDeckMutation: vi.fn(),
  useCreateFlashcardMutation: vi.fn(),
  useCreateFlashcardsBulkMutation: vi.fn()
}))

vi.mock("@/hooks/useTTS", () => ({
  useTTS: () => ({
    speak: vi.fn(),
    cancel: vi.fn(),
    isSpeaking: false
  })
}))

vi.mock("@/hooks/useSpeechRecognition", () => ({
  useSpeechRecognition: () => ({
    supported: false,
    isListening: false,
    transcript: "",
    start: vi.fn(),
    stop: vi.fn(),
    resetTranscript: vi.fn()
  })
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ResultsTab remediation panel", () => {
  const onRetakeQuiz = vi.fn()
  let assistantQueryState: any
  const assistantRefetchMock = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    onRetakeQuiz.mockReset()
    assistantQueryState = null
    assistantRefetchMock.mockReset()

    mocks.createDeck.mockResolvedValue({ id: 99, name: "Recovery Deck" })
    mocks.createFlashcard.mockResolvedValue({ uuid: "new-card" })
    mocks.createFlashcardsBulk.mockResolvedValue([
      { uuid: "new-card-1" },
      { uuid: "new-card-2" }
    ])
    mocks.remediationQuiz.mockResolvedValue({
      quiz: {
        id: 55,
        name: "Quiz: Remediation"
      },
      questions: []
    })
    mocks.assistantRespond.mockResolvedValue({
      assistant_message: {
        id: 400,
        content: "Review the misconception in your own words."
      }
    })

    vi.mocked(useAllAttemptsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 101,
            quiz_id: 7,
            started_at: "2026-03-13T09:00:00Z",
            completed_at: "2026-03-13T09:12:00Z",
            score: 1,
            total_possible: 3,
            time_spent_seconds: 720,
            answers: []
          }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 7,
            name: "Renal Physiology",
            total_questions: 3,
            media_id: 42
          }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    vi.mocked(useAttemptQuery).mockReturnValue({
      data: {
        id: 101,
        quiz_id: 7,
        started_at: "2026-03-13T09:00:00Z",
        completed_at: "2026-03-13T09:12:00Z",
        score: 1,
        total_possible: 3,
        time_spent_seconds: 720,
        answers: [
          {
            question_id: 12,
            user_answer: "Bowman capsule",
            is_correct: false,
            correct_answer: "Glomerulus",
            explanation: "Filtration happens at the glomerulus."
          },
          {
            question_id: 13,
            user_answer: "Descending limb",
            is_correct: false,
            correct_answer: "Ascending limb",
            explanation: "The ascending limb reabsorbs sodium."
          },
          {
            question_id: 14,
            user_answer: "ADH",
            is_correct: true,
            correct_answer: "ADH",
            explanation: "Correct."
          }
        ],
        questions: [
          {
            id: 12,
            quiz_id: 7,
            question_type: "multiple_choice",
            question_text: "Which structure filters blood?",
            options: ["Bowman capsule", "Glomerulus", "Loop of Henle"],
            points: 1,
            order_index: 0,
            deleted: false,
            client_id: "test",
            version: 1
          },
          {
            id: 13,
            quiz_id: 7,
            question_type: "multiple_choice",
            question_text: "Which nephron segment reabsorbs sodium without water?",
            options: ["Descending limb", "Ascending limb", "Collecting duct"],
            points: 1,
            order_index: 1,
            deleted: false,
            client_id: "test",
            version: 1
          },
          {
            id: 14,
            quiz_id: 7,
            question_type: "multiple_choice",
            question_text: "Which hormone raises water reabsorption?",
            options: ["ADH", "Insulin", "Thyroxine"],
            points: 1,
            order_index: 2,
            deleted: false,
            client_id: "test",
            version: 1
          }
        ]
      },
      isLoading: false,
      isFetching: false
    } as any)

    vi.mocked(useGenerateRemediationQuizMutation).mockReturnValue({
      mutateAsync: mocks.remediationQuiz,
      isPending: false
    } as any)

    assistantRefetchMock.mockImplementation(async () => {
      const nextMessageId = 201 + (assistantQueryState.data?.messages?.length ?? 1)
      assistantQueryState = {
        ...assistantQueryState,
        data: {
          ...assistantQueryState.data,
          thread: {
            ...assistantQueryState.data.thread,
            version: 2,
            message_count: 2
          },
          messages: [
            ...(assistantQueryState.data?.messages ?? []),
            {
              id: nextMessageId,
              thread_id: 19,
              role: "assistant",
              action_type: "follow_up",
              input_modality: "text",
              content: "Latest remediation context",
              structured_payload: {},
              context_snapshot: {},
              provider: "openai",
              model: "gpt-5",
              created_at: "2026-03-13T09:14:00Z",
              client_id: "test"
            }
          ]
        }
      }
      return assistantQueryState
    })
    vi.mocked(useQuizAttemptQuestionAssistantQuery).mockImplementation(
      (_attemptId: number | null | undefined, questionId: number | null | undefined) => {
        if (questionId !== 12) {
          return {
            data: null,
            isLoading: false,
            isError: false,
            refetch: assistantRefetchMock
          } as any
        }

        if (!assistantQueryState) {
          assistantQueryState = {
            data: {
              thread: {
                id: 19,
                context_type: "quiz_attempt_question",
                quiz_attempt_id: 101,
                question_id: 12,
                message_count: 1,
                deleted: false,
                client_id: "test",
                version: 1
              },
              messages: [
                {
                  id: 201,
                  thread_id: 19,
                  role: "assistant",
                  action_type: "explain",
                  input_modality: "text",
                  content: "Review the misconception in your own words.",
                  structured_payload: {},
                  context_snapshot: {},
                  provider: "openai",
                  model: "gpt-5",
                  created_at: "2026-03-13T09:13:00Z",
                  client_id: "test"
                }
              ],
              context_snapshot: {},
              available_actions: ["explain", "follow_up", "freeform"]
            },
            isLoading: false,
            isError: false
          }
        }

        return {
          ...assistantQueryState,
          refetch: assistantRefetchMock
        } as any
      }
    )

    vi.mocked(useQuizAttemptQuestionAssistantRespondMutation).mockReturnValue({
      mutateAsync: mocks.assistantRespond,
      isPending: false
    } as any)

    vi.mocked(useDecksQuery).mockReturnValue({
      data: [{ id: 3, name: "Renal Recovery Deck" }],
      isLoading: false
    } as any)
    vi.mocked(useCreateDeckMutation).mockReturnValue({
      mutateAsync: mocks.createDeck,
      isPending: false
    } as any)
    vi.mocked(useCreateFlashcardMutation).mockReturnValue({
      mutateAsync: mocks.createFlashcard,
      isPending: false
    } as any)
    vi.mocked(useCreateFlashcardsBulkMutation).mockReturnValue({
      mutateAsync: mocks.createFlashcardsBulk,
      isPending: false
    } as any)
  })

  const openDetails = async () => {
    render(<ResultsTab onRetakeQuiz={onRetakeQuiz} />)
    fireEvent.click(screen.getByRole("button", { name: /view details/i }))
    await waitFor(() => {
      expect(screen.getByText("Attempt Details")).toBeInTheDocument()
    })
  }

  it("explains a missed question and shows question-scoped assistant history", async () => {
    await openDetails()

    fireEvent.click(screen.getByRole("button", { name: /explain mistake for question 12/i }))

    await waitFor(() => {
      expect(mocks.assistantRespond).toHaveBeenCalledWith({
        attemptId: 101,
        questionId: 12,
        request: { action: "explain" }
      })
    })
    expect(screen.getByText("Review the misconception in your own words.")).toBeInTheDocument()
  })

  it("generates remediation quizzes from selected missed questions", async () => {
    await openDetails()

    fireEvent.click(screen.getByLabelText(/select missed question 12/i))
    fireEvent.click(screen.getByLabelText(/select missed question 13/i))
    fireEvent.click(screen.getByRole("button", { name: /create remediation quiz/i }))

    await waitFor(() => {
      expect(mocks.remediationQuiz).toHaveBeenCalledWith({
        attemptId: 101,
        questionIds: [12, 13]
      })
    })
    await waitFor(() => {
      expect(onRetakeQuiz).toHaveBeenCalledWith(
        expect.objectContaining({
          startQuizId: 55,
          highlightQuizId: 55,
          sourceTab: "results",
          attemptId: 101
        })
      )
    })
  })

  it("opens remediation flashcards and preserves study handoff actions", async () => {
    await openDetails()

    fireEvent.click(screen.getByRole("button", { name: /create remediation flashcards/i }))

    await waitFor(() => {
      expect(screen.getByText("Destination deck")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: /study linked cards/i }))

    expect(mocks.navigate).toHaveBeenCalledWith(
      expect.stringContaining("/flashcards?tab=review&study_source=quiz&quiz_id=7&attempt_id=101")
    )
  })

  it("creates missed-question flashcards with one bulk mutation", async () => {
    await openDetails()

    fireEvent.click(screen.getByRole("button", { name: /create remediation flashcards/i }))

    await waitFor(() => {
      expect(screen.getByText("Destination deck")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: /^create flashcards$/i }))

    await waitFor(() => {
      expect(mocks.createFlashcardsBulk).toHaveBeenCalledWith([
        expect.objectContaining({
          deck_id: 3,
          front: "Which structure filters blood?",
          source_ref_id: "quiz-attempt:101:question:12"
        }),
        expect.objectContaining({
          deck_id: 3,
          front: "Which nephron segment reabsorbs sodium without water?",
          source_ref_id: "quiz-attempt:101:question:13"
        })
      ])
    })
    expect(mocks.createFlashcard).not.toHaveBeenCalled()
  })

  it("recovers remediation assistant conflicts in place", async () => {
    mocks.assistantRespond
      .mockRejectedValueOnce(Object.assign(new Error("Version mismatch"), { response: { status: 409 } }))
      .mockRejectedValueOnce(Object.assign(new Error("Version mismatch"), { response: { status: 409 } }))
      .mockResolvedValueOnce({
        assistant_message: {
          id: 401,
          content: "Retried remediation response"
        }
      })
    await openDetails()

    fireEvent.click(screen.getByRole("button", { name: /explain mistake for question 12/i }))

    await waitFor(() => {
      expect(assistantRefetchMock).toHaveBeenCalled()
      expect(screen.getByText("Latest remediation context")).toBeInTheDocument()
      expect(screen.getByText("Conversation changed elsewhere.")).toBeInTheDocument()
      expect(screen.getByText("Quiz #7, question 12")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole("button", { name: /explain mistake for question 12/i }))
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Retry my message" })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "Retry my message" }))

    await waitFor(() => {
      expect(mocks.assistantRespond).toHaveBeenNthCalledWith(3, {
        attemptId: 101,
        questionId: 12,
        request: { action: "explain" }
      })
    })
  }, 12000)
})
