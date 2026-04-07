import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  useAttemptRemediationConversionsQuery,
  useConvertAttemptRemediationQuestionsMutation,
  useGenerateRemediationQuizMutation
} from "../useQuizQueries"
import {
  convertAttemptRemediationQuestions,
  generateRemediationQuiz,
  listAttemptRemediationConversions
} from "@/services/quizzes"

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasQuizzes: true },
    loading: false
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/quizzes", async () => {
  const actual = await vi.importActual<typeof import("@/services/quizzes")>(
    "@/services/quizzes"
  )
  return {
    ...actual,
    listAttemptRemediationConversions: vi.fn(async () => ({
      attempt_id: 301,
      items: [
        {
          id: 71,
          attempt_id: 301,
          quiz_id: 21,
          question_id: 12,
          status: "active",
          orphaned: false,
          superseded_count: 1,
          target_deck_id: 9,
          target_deck_name_snapshot: "Renal Recovery",
          flashcard_count: 1,
          flashcard_uuids_json: ["fc-1"],
          source_ref_id: "quiz-attempt:301:question:12",
          created_at: "2026-03-13T09:00:00Z",
          last_modified: "2026-03-13T09:00:00Z",
          client_id: "test-client",
          version: 1
        }
      ],
      count: 1,
      superseded_count: 1
    })),
    convertAttemptRemediationQuestions: vi.fn(async () => ({
      attempt_id: 301,
      quiz_id: 21,
      target_deck: {
        id: 9,
        name: "Renal Recovery"
      },
      results: [
        {
          question_id: 12,
          status: "already_exists",
          conversion: {
            id: 71,
            attempt_id: 301,
            quiz_id: 21,
            question_id: 12,
            status: "active",
            orphaned: false,
            superseded_count: 1,
            target_deck_id: 9,
            target_deck_name_snapshot: "Renal Recovery",
            flashcard_count: 1,
            flashcard_uuids_json: ["fc-1"],
            source_ref_id: "quiz-attempt:301:question:12",
            created_at: "2026-03-13T09:00:00Z",
            last_modified: "2026-03-13T09:00:00Z",
            client_id: "test-client",
            version: 1
          },
          flashcard_uuids: ["fc-1"],
          error: null
        },
        {
            question_id: 19,
            status: "created",
            conversion: {
              id: 72,
              attempt_id: 301,
              quiz_id: 21,
              question_id: 19,
              status: "active",
              orphaned: false,
              superseded_count: 0,
              target_deck_id: 9,
            target_deck_name_snapshot: "Renal Recovery",
            flashcard_count: 1,
            flashcard_uuids_json: ["fc-2"],
            source_ref_id: "quiz-attempt:301:question:19",
            created_at: "2026-03-13T09:05:00Z",
            last_modified: "2026-03-13T09:05:00Z",
            client_id: "test-client",
            version: 1
          },
          flashcard_uuids: ["fc-2"],
          error: null
        }
      ],
      created_flashcard_uuids: ["fc-2"]
    })),
    generateRemediationQuiz: vi.fn(async () => ({
      quiz: {
        id: 21,
        name: "Quiz: Remediation",
        description: "Auto-generated remediation quiz from missed questions",
        workspace_tag: null,
        media_id: null,
        source_bundle_json: [
          { source_type: "quiz_attempt_question", source_id: "301:12" },
          { source_type: "quiz_attempt_question", source_id: "301:19" }
        ],
        total_questions: 2,
        deleted: false,
        client_id: "test-client",
        version: 1
      },
      questions: []
    }))
  }
})

const buildWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useGenerateRemediationQuizMutation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("generates remediation quizzes from selected missed questions", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    const { result } = renderHook(() => useGenerateRemediationQuizMutation(), {
      wrapper: buildWrapper(queryClient)
    })

    await act(async () => {
      await result.current.mutateAsync({
        attemptId: 301,
        questionIds: [12, 19],
        numQuestions: 4,
        difficulty: "medium",
        focusTopics: ["renal"],
        apiProvider: "openai",
        workspaceTag: "workspace:med-school"
      })
    })

    expect(generateRemediationQuiz).toHaveBeenCalledWith({
      attemptId: 301,
      questionIds: [12, 19],
      num_questions: 4,
      difficulty: "medium",
      focus_topics: ["renal"],
      api_provider: "openai",
      workspace_tag: "workspace:med-school"
    })
  })

  it("loads server-backed remediation conversion state for an attempt", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    const { result } = renderHook(
      () => useAttemptRemediationConversionsQuery(301),
      { wrapper: buildWrapper(queryClient) }
    )

    await waitFor(() => {
      expect(result.current.data?.items).toHaveLength(1)
    })

    expect(listAttemptRemediationConversions).toHaveBeenCalledWith(301, expect.any(Object))
    expect(result.current.data?.items[0]?.target_deck_name_snapshot).toBe("Renal Recovery")
  })

  it("converts remediation questions through the quiz-owned conversion endpoint", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    queryClient.setQueryData(["quizzes:attempt:remediation-conversions", 301], {
      attempt_id: 301,
      items: [
        {
          id: 71,
          attempt_id: 301,
          quiz_id: 21,
          question_id: 12,
          status: "active",
          orphaned: false,
          superseded_count: 1,
          target_deck_id: 9,
          target_deck_name_snapshot: "Renal Recovery",
          flashcard_count: 1,
          flashcard_uuids_json: ["fc-1"],
          source_ref_id: "quiz-attempt:301:question:12",
          created_at: "2026-03-13T09:00:00Z",
          last_modified: "2026-03-13T09:00:00Z",
          client_id: "test-client",
          version: 1
        }
      ],
      count: 1,
      superseded_count: 1
    })

    const { result } = renderHook(
      () => useConvertAttemptRemediationQuestionsMutation(),
      { wrapper: buildWrapper(queryClient) }
    )

    await act(async () => {
      await result.current.mutateAsync({
        attemptId: 301,
        request: {
          question_ids: [12, 19],
          target_deck_id: 9
        }
      })
    })

    expect(convertAttemptRemediationQuestions).toHaveBeenCalledWith(301, {
      question_ids: [12, 19],
      target_deck_id: 9
    }, undefined)

    await waitFor(() => {
      const cached = queryClient.getQueryData<any>(["quizzes:attempt:remediation-conversions", 301])
      expect(cached?.items).toHaveLength(2)
      expect(cached?.items.some((item: any) => item.question_id === 19)).toBe(true)
      expect(cached?.superseded_count).toBe(1)
      expect(
        cached?.items.find((item: any) => item.question_id === 12)?.superseded_count
      ).toBe(1)
    })
  })
})
