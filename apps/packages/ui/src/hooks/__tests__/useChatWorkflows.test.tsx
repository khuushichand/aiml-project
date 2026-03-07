import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

const serviceMocks = vi.hoisted(() => ({
  createChatWorkflowTemplate: vi.fn(),
  listChatWorkflowTemplates: vi.fn(),
  submitChatWorkflowAnswer: vi.fn(),
  respondChatWorkflowRound: vi.fn()
}))

vi.mock("@/services/tldw/chat-workflows", () => ({
  createChatWorkflowTemplate: (...args: unknown[]) =>
    serviceMocks.createChatWorkflowTemplate(...args),
  listChatWorkflowTemplates: (...args: unknown[]) =>
    serviceMocks.listChatWorkflowTemplates(...args),
  submitChatWorkflowAnswer: (...args: unknown[]) =>
    serviceMocks.submitChatWorkflowAnswer(...args),
  respondChatWorkflowRound: (...args: unknown[]) =>
    serviceMocks.respondChatWorkflowRound(...args)
}))

import {
  chatWorkflowQueryKeys,
  useChatWorkflowTemplates,
  useCreateChatWorkflowTemplate,
  useSubmitChatWorkflowRound,
  useSubmitChatWorkflowAnswer
} from "@/hooks/useChatWorkflows"

const buildWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe("useChatWorkflows", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("loads chat workflow templates through React Query", async () => {
    serviceMocks.listChatWorkflowTemplates.mockResolvedValueOnce([
      {
        id: 1,
        title: "Discovery",
        description: "Collect context",
        version: 1,
        status: "active",
        steps: []
      }
    ])
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    })

    const { result } = renderHook(() => useChatWorkflowTemplates(), {
      wrapper: buildWrapper(queryClient)
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toHaveLength(1)
    expect(serviceMocks.listChatWorkflowTemplates).toHaveBeenCalledTimes(1)
  })

  it("invalidates template queries after creating a template", async () => {
    serviceMocks.createChatWorkflowTemplate.mockResolvedValueOnce({
      id: 2,
      title: "Builder",
      version: 1,
      status: "active",
      steps: []
    })
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    })
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(() => useCreateChatWorkflowTemplate(), {
      wrapper: buildWrapper(queryClient)
    })

    await act(async () => {
      await result.current.mutateAsync({
        title: "Builder",
        steps: []
      })
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: chatWorkflowQueryKeys.templates()
      })
    })
  })

  it("invalidates the run and transcript queries after answering a step", async () => {
    serviceMocks.submitChatWorkflowAnswer.mockResolvedValueOnce({
      run_id: "run-1",
      status: "active",
      current_step_index: 1,
      template_version: 1,
      answers: []
    })
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    })
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(() => useSubmitChatWorkflowAnswer("run-1"), {
      wrapper: buildWrapper(queryClient)
    })

    await act(async () => {
      await result.current.mutateAsync({
        step_index: 0,
        answer_text: "Ship a feature"
      })
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: chatWorkflowQueryKeys.run("run-1")
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: chatWorkflowQueryKeys.transcript("run-1")
    })
  })

  it("invalidates the run and transcript queries after responding to a dialogue round", async () => {
    serviceMocks.respondChatWorkflowRound.mockResolvedValueOnce({
      run_id: "run-2",
      status: "active",
      current_step_index: 0,
      current_round_index: 1,
      current_step_kind: "dialogue_round_step",
      current_prompt: "Defend your evidence.",
      template_version: 1,
      rounds: []
    })
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    })
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(() => useSubmitChatWorkflowRound("run-2", 0), {
      wrapper: buildWrapper(queryClient)
    })

    await act(async () => {
      await result.current.mutateAsync({
        user_message: "Here is my defense."
      })
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: chatWorkflowQueryKeys.run("run-2")
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: chatWorkflowQueryKeys.transcript("run-2")
    })
  })
})
