import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  useQuizAttemptQuestionAssistantQuery,
  useQuizAttemptQuestionAssistantRespondMutation
} from "../useQuizQueries"
import {
  getQuizAttemptQuestionAssistant,
  respondQuizAttemptQuestionAssistant
} from "@/services/quizzes"
import type {
  StudyAssistantContextResponse,
  StudyAssistantRespondResponse
} from "@/services/flashcards"

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
    getQuizAttemptQuestionAssistant: vi.fn(),
    respondQuizAttemptQuestionAssistant: vi.fn()
  }
})

const baseAssistantContext: StudyAssistantContextResponse = {
  thread: {
    id: 19,
    context_type: "quiz_attempt_question",
    flashcard_uuid: null,
    quiz_attempt_id: 301,
    question_id: 12,
    last_message_at: "2026-03-13T08:00:00Z",
    message_count: 0,
    deleted: false,
    client_id: "test-client",
    version: 4,
    created_at: "2026-03-13T08:00:00Z",
    last_modified: "2026-03-13T08:00:00Z"
  },
  messages: [],
  context_snapshot: {
    quiz_attempt_id: 301,
    question_id: 12
  },
  available_actions: ["explain", "follow_up", "freeform"]
}

const buildAssistantResponse = (): StudyAssistantRespondResponse => ({
  thread: {
    ...baseAssistantContext.thread,
    message_count: 2,
    version: 6,
    last_message_at: "2026-03-13T08:05:00Z",
    last_modified: "2026-03-13T08:05:00Z"
  },
  user_message: {
    id: 51,
    thread_id: 19,
    role: "user",
    action_type: "explain",
    input_modality: "text",
    content: "Explain this miss",
    structured_payload: {},
    context_snapshot: baseAssistantContext.context_snapshot,
    provider: null,
    model: null,
    created_at: "2026-03-13T08:05:00Z",
    client_id: "test-client"
  },
  assistant_message: {
    id: 52,
    thread_id: 19,
    role: "assistant",
    action_type: "explain",
    input_modality: "text",
    content: "Here's where the reasoning broke down.",
    structured_payload: {},
    context_snapshot: baseAssistantContext.context_snapshot,
    provider: "openai",
    model: "gpt-5",
    created_at: "2026-03-13T08:05:02Z",
    client_id: "test-client"
  },
  structured_payload: {},
  context_snapshot: baseAssistantContext.context_snapshot
})

const buildWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useQuizAttemptQuestionAssistantQuery + useQuizAttemptQuestionAssistantRespondMutation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("posts quiz assistant actions with the cached thread version", async () => {
    vi.mocked(getQuizAttemptQuestionAssistant).mockResolvedValue(baseAssistantContext)
    vi.mocked(respondQuizAttemptQuestionAssistant).mockResolvedValue(buildAssistantResponse())

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    const wrapper = buildWrapper(queryClient)
    const query = renderHook(
      () => useQuizAttemptQuestionAssistantQuery(301, 12),
      { wrapper }
    )

    await waitFor(() => {
      expect(query.result.current.data?.thread.id).toBe(19)
    })

    const mutation = renderHook(() => useQuizAttemptQuestionAssistantRespondMutation(), {
      wrapper
    })

    await act(async () => {
      await mutation.result.current.mutateAsync({
        attemptId: 301,
        questionId: 12,
        request: {
          action: "explain",
          message: "Explain this miss"
        }
      })
    })

    expect(respondQuizAttemptQuestionAssistant).toHaveBeenCalledWith(
      301,
      12,
      {
        action: "explain",
        message: "Explain this miss",
        expected_thread_version: 4
      },
      undefined
    )

    const cached = queryClient.getQueryData<StudyAssistantContextResponse>([
      "quizzes:assistant",
      301,
      12
    ])
    expect(cached?.thread.version).toBe(6)
    expect(cached?.messages.map((message) => message.role)).toEqual(["user", "assistant"])
  })
})
