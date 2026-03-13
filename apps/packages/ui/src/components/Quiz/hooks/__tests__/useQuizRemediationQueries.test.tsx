import React from "react"
import { act, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useGenerateRemediationQuizMutation } from "../useQuizQueries"
import { generateRemediationQuiz } from "@/services/quizzes"

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
        workspaceTag: "workspace:med-school"
      })
    })

    expect(generateRemediationQuiz).toHaveBeenCalledWith({
      attemptId: 301,
      questionIds: [12, 19],
      num_questions: 4,
      difficulty: "medium",
      focus_topics: ["renal"],
      workspace_tag: "workspace:med-school"
    })
  })
})
