import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequestClient: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequestClient: (...args: unknown[]) => mocks.bgRequestClient(...args)
}))

import {
  continueChatWorkflowRun,
  createChatWorkflowTemplate,
  deleteChatWorkflowTemplate,
  listChatWorkflowTemplates,
  respondChatWorkflowRound,
  startChatWorkflowRun
} from "../chat-workflows"

describe("chat workflows service client", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("lists workflow templates from the chat workflows API", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce([{ id: 1, title: "Discovery" }])

    const out = await listChatWorkflowTemplates()

    expect(out).toEqual([{ id: 1, title: "Discovery" }])
    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/chat-workflows/templates",
        method: "GET"
      })
    )
  })

  it("creates templates with the provided payload", async () => {
    const payload = {
      title: "Discovery",
      description: "Collect context",
      steps: [
        {
          id: "goal",
          step_index: 0,
          base_question: "What is your goal?",
          question_mode: "stock" as const,
          context_refs: []
        }
      ]
    }
    mocks.bgRequestClient.mockResolvedValueOnce({ id: 3, ...payload, version: 1 })

    await createChatWorkflowTemplate(payload)

    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/chat-workflows/templates",
        method: "POST",
        body: payload
      })
    )
  })

  it("starts a run and continues to free chat through the run lifecycle endpoints", async () => {
    const startPayload = {
      template_id: 11,
      selected_context_refs: [{ kind: "note", id: "n-1" }]
    }
    mocks.bgRequestClient
      .mockResolvedValueOnce({ run_id: "run-42", status: "active" })
      .mockResolvedValueOnce({ conversation_id: "conv-9" })

    const started = await startChatWorkflowRun(startPayload)
    const continued = await continueChatWorkflowRun("run-42")

    expect(started.run_id).toBe("run-42")
    expect(continued.conversation_id).toBe("conv-9")
    expect(mocks.bgRequestClient).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/chat-workflows/runs",
        method: "POST",
        body: startPayload
      })
    )
    expect(mocks.bgRequestClient).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/chat-workflows/runs/run-42/continue-chat",
        method: "POST"
      })
    )
  })

  it("deletes templates through the template resource path", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce(undefined)

    await deleteChatWorkflowTemplate(22)

    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/chat-workflows/templates/22",
        method: "DELETE"
      })
    )
  })

  it("submits dialogue rounds through the round response endpoint", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce({ run_id: "run-42", status: "active" })

    await respondChatWorkflowRound("run-42", 1, {
      user_message: "Here is my defense.",
      idempotency_key: "round-2"
    })

    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/chat-workflows/runs/run-42/rounds/1/respond",
        method: "POST",
        body: {
          user_message: "Here is my defense.",
          idempotency_key: "round-2"
        }
      })
    )
  })
})
