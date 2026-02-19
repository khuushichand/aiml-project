import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  useAttemptsQuery,
  useCreateQuizMutation,
  useDeleteQuizMutation,
  useQuizzesQuery,
  useUpdateQuizMutation
} from "../useQuizQueries"

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasQuizzes: true },
    loading: false
  })
}))

vi.mock("@/services/quizzes", () => ({
  listQuizzes: vi.fn(async () => ({ items: [], count: 0 })),
  createQuiz: vi.fn(async () => ({
    id: 1,
    name: "Generated",
    description: null,
    workspace_tag: null,
    media_id: null,
    total_questions: 0,
    time_limit_seconds: null,
    passing_score: null,
    deleted: false,
    client_id: "test",
    version: 1
  })),
  getQuiz: vi.fn(async () => null),
  updateQuiz: vi.fn(async () => undefined),
  deleteQuiz: vi.fn(async () => undefined),
  listQuestions: vi.fn(async () => ({ items: [], count: 0 })),
  createQuestion: vi.fn(async () => undefined),
  updateQuestion: vi.fn(async () => undefined),
  deleteQuestion: vi.fn(async () => undefined),
  startAttempt: vi.fn(async () => undefined),
  submitAttempt: vi.fn(async () => undefined),
  listAttempts: vi.fn(async () => ({ items: [], count: 0 })),
  getAttempt: vi.fn(async () => undefined),
  generateQuiz: vi.fn(async () => undefined)
}))

describe("useQuizQueries performance configuration", () => {
  const queryClientMock = {
    cancelQueries: vi.fn(async () => undefined),
    getQueriesData: vi.fn(() => [[ ["quizzes:list", {}], { items: [], count: 0 } ]]),
    getQueryData: vi.fn(() => undefined),
    setQueryData: vi.fn(),
    setQueriesData: vi.fn(),
    invalidateQueries: vi.fn(),
    removeQueries: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useQueryClient).mockReturnValue(queryClientMock as any)
    vi.mocked(useMutation).mockImplementation((options: any) => options)
    vi.mocked(useQuery).mockImplementation((options: any) => options)
  })

  it("applies explicit stale and refetch policy for quizzes and attempts", () => {
    renderHook(() => useQuizzesQuery({ limit: 10, offset: 0 }))
    expect(vi.mocked(useQuery).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        staleTime: 30_000,
        refetchOnWindowFocus: false
      })
    )

    renderHook(() => useAttemptsQuery({ limit: 10, offset: 0 }))
    expect(vi.mocked(useQuery).mock.calls[1][0]).toEqual(
      expect.objectContaining({
        staleTime: 30_000,
        refetchOnWindowFocus: false
      })
    )
  })

  it("configures optimistic lifecycle handlers for create, update, and delete quiz mutations", async () => {
    const create = renderHook(() => useCreateQuizMutation()).result.current as any
    const update = renderHook(() => useUpdateQuizMutation()).result.current as any
    const remove = renderHook(() => useDeleteQuizMutation()).result.current as any

    expect(create.onMutate).toBeTypeOf("function")
    expect(create.onError).toBeTypeOf("function")
    expect(update.onMutate).toBeTypeOf("function")
    expect(update.onError).toBeTypeOf("function")
    expect(remove.onMutate).toBeTypeOf("function")
    expect(remove.onError).toBeTypeOf("function")

    await create.onMutate({ name: "Quick Quiz" })
    expect(queryClientMock.cancelQueries).toHaveBeenCalledWith({ queryKey: ["quizzes:list"] })
    expect(queryClientMock.getQueriesData).toHaveBeenCalledWith({ queryKey: ["quizzes:list"] })
  })
})
