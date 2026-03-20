import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  useFlashcardAssistantQuery,
  useFlashcardAssistantRespondMutation
} from "../useFlashcardQueries"
import {
  getFlashcardAssistant,
  respondFlashcardAssistant,
  type StudyAssistantContextResponse,
  type StudyAssistantRespondResponse
} from "@/services/flashcards"

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasFlashcards: true },
    loading: false
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/flashcards", async () => {
  const actual = await vi.importActual<typeof import("@/services/flashcards")>(
    "@/services/flashcards"
  )
  return {
    ...actual,
    getFlashcardAssistant: vi.fn(),
    respondFlashcardAssistant: vi.fn()
  }
})

const baseAssistantContext: StudyAssistantContextResponse = {
  thread: {
    id: 7,
    context_type: "flashcard",
    flashcard_uuid: "card-1",
    quiz_attempt_id: null,
    question_id: null,
    last_message_at: "2026-03-13T08:00:00Z",
    message_count: 0,
    deleted: false,
    client_id: "test-client",
    version: 1,
    created_at: "2026-03-13T08:00:00Z",
    last_modified: "2026-03-13T08:00:00Z"
  },
  messages: [],
  context_snapshot: {
    flashcard: {
      uuid: "card-1",
      front: "Front",
      back: "Back"
    }
  },
  available_actions: ["explain", "mnemonic", "follow_up", "fact_check", "freeform"]
}

const buildAssistantResponse = (): StudyAssistantRespondResponse => ({
  thread: {
    ...baseAssistantContext.thread,
    message_count: 2,
    version: 3,
    last_message_at: "2026-03-13T08:05:00Z",
    last_modified: "2026-03-13T08:05:00Z"
  },
  user_message: {
    id: 11,
    thread_id: 7,
    role: "user",
    action_type: "explain",
    input_modality: "text",
    content: "Explain this card",
    structured_payload: {},
    context_snapshot: baseAssistantContext.context_snapshot,
    provider: null,
    model: null,
    created_at: "2026-03-13T08:05:00Z",
    client_id: "test-client"
  },
  assistant_message: {
    id: 12,
    thread_id: 7,
    role: "assistant",
    action_type: "explain",
    input_modality: "text",
    content: "Here is the explanation.",
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

describe("useFlashcardAssistantQuery + useFlashcardAssistantRespondMutation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches flashcard assistant history for the active card", async () => {
    vi.mocked(getFlashcardAssistant).mockResolvedValue(baseAssistantContext)
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false }
      }
    })

    const { result } = renderHook(() => useFlashcardAssistantQuery("card-1"), {
      wrapper: buildWrapper(queryClient)
    })

    await waitFor(() => {
      expect(result.current.data?.thread.id).toBe(7)
    })

    expect(getFlashcardAssistant).toHaveBeenCalledWith(
      "card-1",
      expect.objectContaining({
        signal: expect.any(AbortSignal)
      })
    )
    expect(result.current.data?.available_actions).toContain("fact_check")
  })

  it("posts assistant actions and updates the cached conversation", async () => {
    vi.mocked(getFlashcardAssistant).mockResolvedValue(baseAssistantContext)
    vi.mocked(respondFlashcardAssistant).mockResolvedValue(buildAssistantResponse())
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })

    const wrapper = buildWrapper(queryClient)
    const query = renderHook(() => useFlashcardAssistantQuery("card-1"), {
      wrapper
    })

    await waitFor(() => {
      expect(query.result.current.data?.thread.id).toBe(7)
    })

    const mutation = renderHook(() => useFlashcardAssistantRespondMutation(), {
      wrapper
    })

    await act(async () => {
      await mutation.result.current.mutateAsync({
        cardUuid: "card-1",
        request: {
          action: "explain",
          message: "Explain this card"
        }
      })
    })

    expect(respondFlashcardAssistant).toHaveBeenCalledWith(
      "card-1",
      {
        action: "explain",
        message: "Explain this card",
        expected_thread_version: 1
      },
      undefined
    )

    const cached = queryClient.getQueryData<StudyAssistantContextResponse>([
      "flashcards:assistant",
      "card-1"
    ])
    expect(cached?.thread.version).toBe(3)
    expect(cached?.messages.map((message) => message.role)).toEqual(["user", "assistant"])
    expect(cached?.messages[1]?.content).toBe("Here is the explanation.")
  })
})
